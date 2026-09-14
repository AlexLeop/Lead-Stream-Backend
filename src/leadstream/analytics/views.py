from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from django.core.cache import cache
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from leadstream.batches.models import Batch, BatchItem
from leadstream.common.api import resolve_tenant
from leadstream.entities.models import (
    Company,
    ContactPoint,
    Establishment,
    Person,
    Relationship,
    SocialProfile,
)
from leadstream.entities.normalization import only_digits
from leadstream.evidence.models import Observation
from leadstream.integrations.models import CRMConnection
from leadstream.intelligence.cnae import KNOWN_CNAES
from leadstream.providers.live_enrichment import enrich_company_live
from leadstream.providers.live_enrichment_person import enrich_person_live
from leadstream.security.authentication import CombinedAuthentication
from leadstream.security.models import SecurityAuditLog
from leadstream.security.permissions import TenantAccessPermission


def _get_payload(request: Request) -> dict[str, Any]:
    return request.data if isinstance(request.data, dict) else {}


def _percent(part: int, total: int) -> int:
    return round((part / total) * 100) if total else 0


VALIDATED_CONTACT_STATUSES = (
    ContactPoint.Status.CAPABILITY_VALID,
    ContactPoint.Status.CONFIRMED,
)


def _evidence_status(contact: ContactPoint | None) -> str:
    if contact is None:
        return "ABSENT"
    if contact.status == ContactPoint.Status.CONFIRMED:
        return "CONFIRMED"
    if contact.status in {
        ContactPoint.Status.DOMAIN_VALID,
        ContactPoint.Status.CAPABILITY_VALID,
    }:
        return "TECHNICALLY_VALIDATED"
    if contact.status in {
        ContactPoint.Status.INVALID,
        ContactPoint.Status.EXPIRED,
        ContactPoint.Status.SUPPRESSED,
    }:
        return "REJECTED"
    return "OBSERVED"


def _email_status(contact: ContactPoint | None) -> str:
    if contact is None:
        return "Não verificado"
    if contact.status in VALIDATED_CONTACT_STATUSES:
        return "Verificado"
    if contact.status == ContactPoint.Status.INVALID:
        return "Inválido"
    return "Não verificado"


def _preferred_contact(entity_id: uuid.UUID, kinds: tuple[str, ...]) -> ContactPoint | None:
    return (
        ContactPoint.objects.filter(owner_id=entity_id, kind__in=kinds)
        .exclude(status__in=(ContactPoint.Status.SUPPRESSED, ContactPoint.Status.EXPIRED))
        .order_by("-last_observed_at", "-created_at")
        .first()
    )


def _preferred_social(entity_id: uuid.UUID, network: str) -> SocialProfile | None:
    return (
        SocialProfile.objects.filter(owner_id=entity_id, network=network)
        .exclude(status__in=(ContactPoint.Status.SUPPRESSED, ContactPoint.Status.EXPIRED))
        .order_by("-last_observed_at", "-created_at")
        .first()
    )


def _freshness_score(contact: ContactPoint | None) -> int:
    if contact is None or contact.last_observed_at is None:
        return 0
    age_days = max((timezone.now() - contact.last_observed_at).days, 0)
    if age_days <= 30:
        return 100
    if age_days <= 90:
        return 80
    if age_days <= 180:
        return 60
    return 30


def _contact_confidence(*contacts: ContactPoint | None) -> int:
    scores: dict[str, int] = {
        ContactPoint.Status.CONFIRMED: 100,
        ContactPoint.Status.CAPABILITY_VALID: 85,
        ContactPoint.Status.DOMAIN_VALID: 65,
        ContactPoint.Status.OBSERVED: 50,
    }
    present = [scores.get(contact.status, 0) for contact in contacts if contact is not None]
    return round(sum(present) / len(present)) if present else 0


def _relationship_lead(relationship: Relationship) -> dict[str, Any]:
    person = relationship.person
    company = relationship.company
    entity_id = person.entity_id
    email = _preferred_contact(entity_id, (ContactPoint.Kind.EMAIL,))
    phone = _preferred_contact(
        entity_id,
        (ContactPoint.Kind.WHATSAPP, ContactPoint.Kind.PHONE),
    )
    linkedin = _preferred_social(entity_id, SocialProfile.Network.LINKEDIN)
    establishment = company.establishments.order_by("-is_headquarters", "created_at").first()
    observed_at = max(
        [
            value
            for value in (
                email.last_observed_at if email else None,
                phone.last_observed_at if phone else None,
                linkedin.last_observed_at if linkedin else None,
            )
            if value is not None
        ],
        default=None,
    )
    seniority_label = dict(Relationship.Seniority.choices).get(
        relationship.seniority,
        "Não informado",
    )
    return {
        "id": str(entity_id),
        "leadType": "PF",
        "name": person.full_name,
        "title": relationship.observed_title,
        "seniority": seniority_label,
        "company": company.legal_name,
        "domain": "",
        "location": "",
        "city": "",
        "state": "",
        "country": "Brasil",
        "email": email.normalized_value if email else "",
        "phone": phone.normalized_value if phone else "",
        "status": _email_status(email),
        "companySize": "",
        "employeeCount": 0,
        "industry": "",
        "annualRevenue": "",
        "fundingStage": "",
        "technologies": [],
        "intentScore": 0,
        "fitScore": 0,
        "opportunityScore": 0,
        "dataConfidenceScore": _contact_confidence(email, phone),
        "freshnessScore": max(_freshness_score(email), _freshness_score(phone)),
        "intentTopic": "",
        "initials": "".join(part[:1] for part in person.full_name.split()[:2]).upper(),
        "linkedinUrl": linkedin.normalized_url if linkedin else "",
        "enriched": bool(email or phone or linkedin),
        "identityEvidenceStatus": "OBSERVED",
        "emailEvidenceStatus": _evidence_status(email),
        "phoneEvidenceStatus": _evidence_status(phone),
        "whatsappEvidenceStatus": (
            _evidence_status(phone)
            if phone and phone.kind == ContactPoint.Kind.WHATSAPP
            else "ABSENT"
        ),
        "cpf": person.cpf_masked,
        "cnpj": establishment.cnpj if establishment else company.cnpj_root,
        "razaoSocial": company.legal_name,
        "nomeFantasia": company.trade_name,
        "situacaoCadastral": company.registration_status,
        "papelCompra": relationship.buying_role,
        "observedAt": observed_at.isoformat() if observed_at else None,
        "createdAt": person.created_at.isoformat(),
        "updatedAt": person.updated_at.isoformat(),
    }


def _company_lead(company: Company) -> dict[str, Any]:
    entity_id = company.entity_id
    email = _preferred_contact(entity_id, (ContactPoint.Kind.EMAIL,))
    phone = _preferred_contact(
        entity_id,
        (ContactPoint.Kind.WHATSAPP, ContactPoint.Kind.PHONE),
    )
    linkedin = _preferred_social(entity_id, SocialProfile.Network.LINKEDIN)
    establishment = company.establishments.order_by("-is_headquarters", "created_at").first()
    return {
        "id": str(entity_id),
        "leadType": "PJ",
        "name": company.trade_name or company.legal_name,
        "title": "",
        "seniority": "Não informado",
        "company": company.legal_name,
        "domain": "",
        "location": "",
        "city": "",
        "state": "",
        "country": "Brasil",
        "email": email.normalized_value if email else "",
        "phone": phone.normalized_value if phone else "",
        "status": _email_status(email),
        "companySize": "",
        "employeeCount": 0,
        "industry": "",
        "annualRevenue": "",
        "fundingStage": "",
        "technologies": [],
        "intentScore": 0,
        "fitScore": 0,
        "opportunityScore": 0,
        "dataConfidenceScore": _contact_confidence(email, phone),
        "freshnessScore": max(_freshness_score(email), _freshness_score(phone)),
        "intentTopic": "",
        "initials": (company.trade_name or company.legal_name)[:2].upper(),
        "linkedinUrl": linkedin.normalized_url if linkedin else "",
        "enriched": bool(email or phone or linkedin),
        "identityEvidenceStatus": "OBSERVED",
        "emailEvidenceStatus": _evidence_status(email),
        "phoneEvidenceStatus": _evidence_status(phone),
        "whatsappEvidenceStatus": (
            _evidence_status(phone)
            if phone and phone.kind == ContactPoint.Kind.WHATSAPP
            else "ABSENT"
        ),
        "cnpj": establishment.cnpj if establishment else company.cnpj_root,
        "razaoSocial": company.legal_name,
        "nomeFantasia": company.trade_name,
        "situacaoCadastral": company.registration_status,
        "dataAbertura": company.opened_on.isoformat() if company.opened_on else None,
        "createdAt": company.created_at.isoformat(),
        "updatedAt": company.updated_at.isoformat(),
    }


class DashboardView(APIView):
    """Retorna o consolidado executivo do Dashboard para gestores e administradores."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (TenantAccessPermission,)

    def get(self, request: Request) -> Response:
        tenant = resolve_tenant(request)
        _ = request.query_params.get("period", "30days")

        companies_count = Company.objects.filter(entity__tenant=tenant).count()
        contacts_count = ContactPoint.objects.filter(tenant=tenant).count()
        persons_count = Person.objects.filter(entity__tenant=tenant).count()
        batches_count = Batch.objects.filter(tenant=tenant).count()

        valid_emails = ContactPoint.objects.filter(
            tenant=tenant,
            kind=ContactPoint.Kind.EMAIL,
            status__in=VALIDATED_CONTACT_STATUSES,
        ).count()
        phones = ContactPoint.objects.filter(
            tenant=tenant,
            kind__in=(ContactPoint.Kind.PHONE, ContactPoint.Kind.WHATSAPP),
            status__in=VALIDATED_CONTACT_STATUSES,
        ).count()

        # Métricas reais da base operacional
        deliverability_rate = (
            round(
                (
                    valid_emails
                    / max(
                        ContactPoint.objects.filter(
                            tenant=tenant, kind=ContactPoint.Kind.EMAIL
                        ).count(),
                        1,
                    )
                )
                * 100,
                1,
            )
            if valid_emails > 0
            else 0.0
        )

        start_date = timezone.now() - timedelta(days=14)
        history_rows: dict[Any, Any] = {
            row["day"]: row
            for row in Batch.objects.filter(tenant=tenant, created_at__gte=start_date)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(
                leads=Sum("total_rows"),
                validados=Sum("processed_rows"),
                enriquecidos=Sum("succeeded_rows"),
            )
        }
        chart_data: list[dict[str, object]] = []
        today = timezone.now().date()
        for i in range(14, -1, -1):
            day_date = today - timedelta(days=i)
            current: dict[str, Any] = history_rows.get(day_date, {})
            chart_data.append(
                {
                    "day": day_date.strftime("%d/%m"),
                    "leads": int(current.get("leads") or 0),
                    "validados": int(current.get("validados") or 0),
                    "enriquecidos": int(current.get("enriquecidos") or 0),
                }
            )

        industry_breakdown: list[dict[str, object]] = []
        seniority_rows = list(
            Relationship.objects.filter(tenant=tenant, ended_on__isnull=True)
            .values("seniority")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        seniority_total = sum(int(row["count"]) for row in seniority_rows)
        seniority_breakdown = [
            {
                "name": dict(Relationship.Seniority.choices).get(
                    str(row["seniority"]), "Não informado"
                ),
                "value": _percent(int(row["count"]), seniority_total),
                "count": int(row["count"]),
            }
            for row in seniority_rows
        ]

        return Response(
            {
                "summary": {
                    "contacts": persons_count + contacts_count,
                    "companies": companies_count,
                    "datasets": batches_count,
                    "lists": 0,
                    "validEmails": valid_emails,
                    "deliverabilityRate": deliverability_rate,
                    "phones": phones,
                    "inMarketAccounts": 0,
                    "actionableRecords": ContactPoint.objects.filter(
                        tenant=tenant,
                        status__in=VALIDATED_CONTACT_STATUSES,
                    )
                    .values("owner_id")
                    .distinct()
                    .count(),
                },
                "chartData": chart_data,
                "industryBreakdown": industry_breakdown,
                "seniorityBreakdown": seniority_breakdown,
            }
        )


class DataHealthView(APIView):
    """Métricas de higienização, cobertura e integridade de dados."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (TenantAccessPermission,)

    def get(self, request: Request) -> Response:
        tenant = resolve_tenant(request)
        companies_count = Company.objects.filter(entity__tenant=tenant).count()
        contacts_count = ContactPoint.objects.filter(tenant=tenant).count()
        persons_count = Person.objects.filter(entity__tenant=tenant).count()
        total_entities = companies_count + persons_count
        validated_contacts = ContactPoint.objects.filter(
            tenant=tenant,
            status__in=VALIDATED_CONTACT_STATUSES,
        )
        actionable_records = validated_contacts.values("owner_id").distinct().count()
        stale_records = ContactPoint.objects.filter(
            tenant=tenant,
            status__in=(ContactPoint.Status.STALE, ContactPoint.Status.EXPIRED),
        ).count()
        invalid_records = ContactPoint.objects.filter(
            tenant=tenant,
            status__in=(ContactPoint.Status.INVALID, ContactPoint.Status.SUPPRESSED),
        ).count()
        incomplete_records = max(total_entities - actionable_records, 0)
        qsa_count = (
            Company.objects.filter(
                entity__tenant=tenant,
                relationships__ended_on__isnull=True,
            )
            .distinct()
            .count()
        )
        email_count = validated_contacts.filter(kind=ContactPoint.Kind.EMAIL).count()
        phone_count = validated_contacts.filter(
            kind__in=(ContactPoint.Kind.PHONE, ContactPoint.Kind.WHATSAPP)
        ).count()
        linkedin_count = SocialProfile.objects.filter(
            tenant=tenant,
            network=SocialProfile.Network.LINKEDIN,
            status__in=VALIDATED_CONTACT_STATUSES,
        ).count()
        lineage_count = (
            Observation.objects.filter(tenant=tenant).values("target_id").distinct().count()
        )
        identity_score = _percent(companies_count + persons_count, total_entities)
        contactability_score = _percent(actionable_records, total_entities)
        profile_score = _percent(linkedin_count, persons_count)
        verification_score = _percent(validated_contacts.count(), contacts_count)
        lineage_score = _percent(lineage_count, total_entities)
        overall_score = round(
            (
                identity_score
                + contactability_score
                + profile_score
                + verification_score
                + lineage_score
            )
            / 5
        )
        issues: list[dict[str, object]] = []
        if incomplete_records:
            issues.append(
                {
                    "id": "missing-actionable-contact",
                    "label": "Registros sem contato validado",
                    "count": incomplete_records,
                    "severity": "high",
                    "description": (
                        "Entidades sem e-mail, telefone ou WhatsApp tecnicamente validado."
                    ),
                    "actionRoute": "enrichment",
                }
            )
        if stale_records:
            issues.append(
                {
                    "id": "stale-contact",
                    "label": "Contatos desatualizados",
                    "count": stale_records,
                    "severity": "medium",
                    "description": "Contatos que ultrapassaram a janela de atualização.",
                    "actionRoute": "data-health",
                }
            )
        if invalid_records:
            issues.append(
                {
                    "id": "rejected-contact",
                    "label": "Contatos inválidos ou suprimidos",
                    "count": invalid_records,
                    "severity": "high",
                    "description": "Registros que não podem ser utilizados para ativação.",
                    "actionRoute": "data-health",
                }
            )

        return Response(
            {
                "generatedAt": timezone.now().isoformat(),
                "summary": {
                    "overallScore": overall_score,
                    "companies": companies_count,
                    "contacts": contacts_count,
                    "totalEntities": total_entities,
                    "actionableRecords": actionable_records,
                    "incompleteRecords": incomplete_records,
                    "staleRecords": stale_records,
                    "duplicateCandidates": 0,
                    "lineageCoverage": lineage_score,
                },
                "coverage": [
                    {
                        "id": "cnpj",
                        "label": "CNPJ & Razão Social",
                        "value": _percent(companies_count, companies_count),
                        "count": companies_count,
                        "total": max(companies_count, 1),
                    },
                    {
                        "id": "qsa",
                        "label": "Quadro Societário (QSA)",
                        "value": _percent(qsa_count, companies_count),
                        "count": qsa_count,
                        "total": max(companies_count, 1),
                    },
                    {
                        "id": "email",
                        "label": "E-mail Corporativo RFC 5321",
                        "value": _percent(email_count, total_entities),
                        "count": email_count,
                        "total": max(total_entities, 1),
                    },
                    {
                        "id": "phone",
                        "label": "Telefone / WhatsApp Atribuível",
                        "value": _percent(phone_count, total_entities),
                        "count": phone_count,
                        "total": max(total_entities, 1),
                    },
                    {
                        "id": "linkedin",
                        "label": "Perfil Público Decisor",
                        "value": _percent(linkedin_count, persons_count),
                        "count": linkedin_count,
                        "total": max(persons_count, 1),
                    },
                ],
                "issues": issues,
                "distribution": {
                    "healthy": actionable_records,
                    "attention": incomplete_records,
                    "critical": invalid_records,
                },
                "dimensions": {
                    "identityScore": identity_score,
                    "contactabilityScore": contactability_score,
                    "profileScore": profile_score,
                    "verificationScore": verification_score,
                    "lineageScore": lineage_score,
                },
                "quarantine": {
                    "quarantined": BatchItem.objects.filter(
                        tenant=tenant,
                        hygiene_state=BatchItem.HygieneState.INVALID,
                    ).count(),
                    "pendingReview": BatchItem.objects.filter(
                        tenant=tenant,
                        status=BatchItem.Status.PENDING,
                    ).count(),
                    "released": 0,
                    "lastClassifiedAt": timezone.now().isoformat(),
                },
            }
        )

    def post(self, request: Request) -> Response:
        """Recusa sucesso sintético enquanto a rotina assíncrona não estiver disponível."""
        return Response(
            {
                "code": "DATA_REPAIR_NOT_CONFIGURED",
                "detail": (
                    "A correção automática ainda não está configurada. "
                    "Nenhum registro foi alterado."
                ),
            },
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )


class DatasetsCollectionView(APIView):
    """Gerenciamento dos Conjuntos de Dados / Lotes de Prospecção."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (TenantAccessPermission,)

    def get(self, request: Request) -> Response:
        tenant = resolve_tenant(request)
        batches = Batch.objects.filter(tenant=tenant).order_by("-created_at")

        results: list[dict[str, Any]] = []
        for b in batches:
            empty_leads: list[str] = []
            status_labels: dict[str, str] = {
                Batch.Status.COMPLETED: "Enriquecido",
                Batch.Status.PARTIAL: "Parcial",
                Batch.Status.FAILED: "Falhou",
                Batch.Status.CANCELLED: "Cancelado",
            }
            display_status = status_labels.get(b.status, "Processando")
            results.append(
                {
                    "id": str(b.id),
                    "name": b.name or f"Lote #{str(b.id)[:8]}",
                    "category": "Prospecção Outbound",
                    "description": f"Lote com {b.total_rows} registros",
                    "leadType": "MISTO",
                    "totalLeads": b.total_rows,
                    "enrichedFields": [],
                    "status": display_status,
                    "enrichmentRate": _percent(b.succeeded_rows, b.total_rows),
                    "createdAt": b.created_at.isoformat(),
                    "leadIds": empty_leads,
                    "fileOriginName": b.input_original_name,
                    "costCredits": b.cost_cents,
                    "lastUpdated": b.updated_at.isoformat(),
                }
            )
        return Response(results)

    def post(self, request: Request) -> Response:
        tenant = resolve_tenant(request)
        payload = _get_payload(request)
        name = payload.get("name", "Novo Conjunto de Leads")
        category = payload.get("category", "Prospecção Outbound")

        batch = Batch.objects.create(
            tenant=tenant,
            name=name,
            source_type=Batch.SourceType.DISCOVERY,
            status=Batch.Status.RECEIVED,
            total_rows=0,
        )

        empty_new_leads: list[str] = []
        return Response(
            {
                "id": str(batch.id),
                "name": batch.name,
                "category": category,
                "description": "Conjunto criado pelo operador",
                "leadType": "MISTO",
                "totalLeads": 0,
                "enrichedFields": [],
                "status": "Processando",
                "enrichmentRate": 0,
                "createdAt": batch.created_at.isoformat(),
                "leadIds": empty_new_leads,
            },
            status=status.HTTP_201_CREATED,
        )


class DatasetDetailView(APIView):
    authentication_classes = (CombinedAuthentication,)
    permission_classes = (TenantAccessPermission,)

    def delete(self, request: Request, dataset_id: str) -> Response:
        tenant = resolve_tenant(request)
        try:
            batch_uuid = uuid.UUID(dataset_id)
        except (ValueError, TypeError):
            return Response(
                {"detail": "Identificador de conjunto inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        deleted, _ = Batch.objects.filter(tenant=tenant, id=batch_uuid).delete()
        if deleted == 0:
            return Response(
                {"detail": "Conjunto não encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class LeadsCollectionView(APIView):
    """Consulta de Leads unificados."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (TenantAccessPermission,)

    def get(self, request: Request) -> Response:
        tenant = resolve_tenant(request)
        relationships = list(
            Relationship.objects.filter(tenant=tenant, ended_on__isnull=True)
            .select_related("person__entity", "company__entity")
            .order_by("-updated_at")[:50]
        )
        leads_list = [_relationship_lead(relationship) for relationship in relationships]
        if len(leads_list) < 50:
            represented_company_ids = {relationship.company_id for relationship in relationships}
            companies = (
                Company.objects.filter(entity__tenant=tenant)
                .exclude(entity_id__in=represented_company_ids)
                .select_related("entity")
                .order_by("-updated_at")[: 50 - len(leads_list)]
            )
            leads_list.extend(_company_lead(company) for company in companies)
        return Response(leads_list)


class ListsCollectionView(APIView):
    """Listas de Campanhas e Exportação."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (TenantAccessPermission,)

    def get(self, request: Request) -> Response:
        resolve_tenant(request)
        return Response([])

    def post(self, request: Request) -> Response:
        resolve_tenant(request)
        return Response(
            {
                "code": "ACTIVATION_LISTS_NOT_CONFIGURED",
                "detail": (
                    "Listas de ativação ainda não estão configuradas. Nenhuma lista foi criada."
                ),
            },
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )


class ActivitiesCollectionView(APIView):
    """Log de atividades e auditoria corporativa."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (TenantAccessPermission,)

    def get(self, request: Request) -> Response:
        tenant = resolve_tenant(request)
        logs = SecurityAuditLog.objects.filter(tenant=tenant).order_by("-timestamp")[:20]

        items = []
        for item in logs:
            items.append(
                {
                    "id": str(item.id),
                    "type": item.action,
                    "title": item.action.replace("_", " ").title(),
                    "subtitle": f"{item.resource_accessed} ({item.actor_type})",
                    "time": item.timestamp.strftime("%H:%M"),
                    "badgeColor": "emerald" if item.status_code < 400 else "rose",
                }
            )

        return Response(items)


class CrmConnectionsView(APIView):
    """Conectores de CRM disponíveis."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (TenantAccessPermission,)

    def get(self, request: Request) -> Response:
        tenant = resolve_tenant(request)
        status_labels = {
            "UNTESTED": "Não testado",
            "HEALTHY": "Conectado",
            "DEGRADED": "Instável",
            "FAILED": "Falha",
        }
        connections = CRMConnection.objects.filter(tenant=tenant).order_by("name")
        return Response(
            [
                {
                    "id": str(connection.id),
                    "name": connection.name,
                    "code": connection.connector_type.lower(),
                    "iconBg": "bg-slate-700",
                    "status": status_labels.get(connection.last_status, "Não testado"),
                    "lastTestedAt": (
                        connection.last_tested_at.isoformat()
                        if connection.last_tested_at
                        else None
                    ),
                    "lastError": connection.last_error_message,
                }
                for connection in connections
            ]
        )


class PixStatusView(APIView):
    """Status de prontidão para checagem de titularidade Pix."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (TenantAccessPermission,)

    def get(self, request: Request) -> Response:
        return Response(
            {
                "enabled": True,
                "termsApproved": True,
                "purpose": "Consulta cadastral de titularidade pública de chave Pix",
                "payerConfigured": False,
                "lookupReady": False,
                "automaticEligibility": "ONLY_EXPLICIT_PUBLIC_PIX_KEY",
                "providers": [{"name": "Open Finance / DICT", "priority": 1, "configured": False}],
            }
        )


class EnrichmentStatusView(APIView):
    """Status do motor de enriquecimento e provedores cadastrais."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (TenantAccessPermission,)

    def get(self, request: Request) -> Response:
        return Response({"available": True})


class EnrichmentCatalogView(APIView):
    """Catálogo de capacidades de inteligência cadastral e prospecção."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (TenantAccessPermission,)

    def get(self, request: Request) -> Response:
        return Response(
            {
                "groups": [
                    {
                        "id": "company",
                        "label": "Dados Corporativos",
                        "description": "CNPJ, QSA, endereço e porte",
                    },
                    {
                        "id": "sales",
                        "label": "Contato & Decisores",
                        "description": "E-mails validados e WhatsApp",
                    },
                    {
                        "id": "operations",
                        "label": "Tecnologia & Operações",
                        "description": "Stack e maturidade técnica",
                    },
                    {
                        "id": "risk",
                        "label": "Compliance & Risco",
                        "description": "PGFN, Simples e regularidade fiscal",
                    },
                ],
                "capabilities": [
                    {
                        "id": "cnpj_qsa",
                        "groupId": "company",
                        "label": "CNPJ & Quadro Societário",
                        "description": (
                            "Receita Federal com sócios, cargos e participações societárias"
                        ),
                        "highlights": ["Razão Social", "CNAE", "Sócios & Administradores"],
                        "depth": "Essencial",
                    },
                    {
                        "id": "emails_smtp",
                        "groupId": "sales",
                        "label": "E-mails Validados RFC 5321",
                        "description": "Validação técnica conforme o provedor configurado",
                        "highlights": [
                            "Sintaxe",
                            "Domínio",
                            "Capacidade técnica quando disponível",
                        ],
                        "depth": "Dependente do provedor",
                    },
                    {
                        "id": "phones_whatsapp",
                        "groupId": "sales",
                        "label": "Telefone e WhatsApp Atribuível",
                        "description": "Localização de linhas móveis vinculadas aos decisores",
                        "highlights": [
                            "Formato E.164",
                            "Link Direto WhatsApp",
                            "Evidência Atribuível",
                        ],
                        "depth": "Detalhado",
                    },
                    {
                        "id": "cpf_cadastral",
                        "groupId": "company",
                        "label": "CPF & Dados Cadastrais PF",
                        "description": "Validação oficial Módulo 11 da RFB e identificação civil",
                        "highlights": ["Nome Civil", "Data de Nascimento", "Situação do CPF"],
                        "depth": "Essencial",
                    },
                    {
                        "id": "phones_whatsapp_probe",
                        "groupId": "sales",
                        "label": "Sinal técnico de WhatsApp (Probe)",
                        "description": (
                            "Consulta técnica quando houver provedor autorizado configurado"
                        ),
                        "highlights": [
                            "Probe em Tempo Real",
                            "Foto de Perfil",
                            "Resultado com horário e origem",
                        ],
                        "depth": "Dependente do provedor",
                    },
                    {
                        "id": "consignado_core",
                        "groupId": "operations",
                        "label": "Core Consignado & Margens (35% + 5% + 5%)",
                        "description": (
                            "Benefício INSS, Espécie, SIAPE e cálculo de margem (Lei 14.431/2022)"
                        ),
                        "highlights": ["Margem Total 45%", "NB & Espécie INSS", "Vínculo SIAPE"],
                        "depth": "Especializado",
                    },
                    {
                        "id": "filtro_perda_obito",
                        "groupId": "risk",
                        "label": "Filtro de Perda & Expurgo de Óbito",
                        "description": "Detecção conforme sinais fornecidos por fonte autorizada",
                        "highlights": [
                            "Detector de Óbito",
                            "Resultado inconclusivo explícito",
                            "Proteção de Carteira",
                        ],
                        "depth": "Essencial",
                    },
                    {
                        "id": "nao_me_perturbe",
                        "groupId": "risk",
                        "label": "Conformidade Não Me Perturbe (Anatel)",
                        "description": (
                            "Higienização contra multas do Procon/Febraban no Não Me Perturbe"
                        ),
                        "highlights": [
                            "Blindagem a Multas",
                            "Lista Anatel/Febraban",
                            "Score de Conformidade",
                        ],
                        "depth": "Conformidade",
                    },
                    {
                        "id": "mailing_top3_discagem",
                        "groupId": "sales",
                        "label": "Priorização de até 3 celulares",
                        "description": (
                            "Top 3 celulares com operadora, WhatsApp ativo e score de discagem"
                        ),
                        "highlights": [
                            "Top 3 Celulares",
                            "Operadoras (Claro/Vivo/TIM)",
                            "Score de Discagem",
                        ],
                        "depth": "Dependente do provedor",
                    },
                ],
                "presets": [
                    {
                        "id": "commercial",
                        "label": "Prospecção Comercial Outbound",
                        "description": "Decisores completos com e-mail corporativo e WhatsApp",
                        "capabilityIds": ["cnpj_qsa", "emails_smtp", "phones_whatsapp"],
                    },
                    {
                        "id": "pf_whatsapp",
                        "label": "Higienização de CPF e sinal de WhatsApp",
                        "description": "Validação de CPF com checagem de conta ativa no WhatsApp",
                        "capabilityIds": ["cpf_cadastral", "phones_whatsapp_probe"],
                    },
                    {
                        "id": "consignado_premium",
                        "label": "Crédito Consignado & Conformidade Total",
                        "description": (
                            "Dossiê: margens INSS/SIAPE, filtro de óbito, NMP e Top 3 WhatsApp"
                        ),
                        "capabilityIds": [
                            "cpf_cadastral",
                            "consignado_core",
                            "filtro_perda_obito",
                            "nao_me_perturbe",
                            "mailing_top3_discagem",
                            "phones_whatsapp_probe",
                        ],
                    },
                ],
            }
        )


class EnrichmentRunsView(APIView):
    authentication_classes = (CombinedAuthentication,)
    permission_classes = (TenantAccessPermission,)

    def get(self, request: Request) -> Response:
        tenant = resolve_tenant(request)
        runs = cache.get(f"enrichment_runs:{tenant.pk}", [])
        return Response(runs if isinstance(runs, list) else [])


class DiscoveryCnaesView(APIView):
    """Busca inteligente de atividades econômicas (CNAE)."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (TenantAccessPermission,)

    def get(self, request: Request) -> Response:
        query = request.query_params.get("q", "").lower().strip()
        limit = int(request.query_params.get("limit", 30))

        results = []
        for code, details in KNOWN_CNAES.items():
            desc = details.get("descricao", "")
            setor = details.get("setor", "")
            if not query or query in code or query in desc.lower() or query in setor.lower():
                results.append(
                    {
                        "code": code,
                        "codeRaw": code,
                        "codigo": code,
                        "description": desc,
                        "descricao": desc,
                        "section": "",
                        "sectionDescription": setor,
                        "division": code[:2],
                        "group": code[:3],
                        "industry": setor,
                        "typicalPorte": None,
                        "averageTicket": None,
                        "defaultBuyingGroup": [],
                    }
                )
                if len(results) >= limit:
                    break

        return Response(results)


class DiscoverySearchView(APIView):
    """Compatibilidade explícita para a busca antiga que produzia estimativas sintéticas."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (TenantAccessPermission,)

    def post(self, request: Request) -> Response:
        resolve_tenant(request)
        return Response(
            {
                "code": "LEGACY_DISCOVERY_REMOVED",
                "detail": (
                    "A busca antiga foi desativada porque estimava volume e custo sem consultar "
                    "o provedor. Use POST /api/v1/descobertas/ com Idempotency-Key; acompanhe "
                    "o job e leia a prévia persistida em /resultados/."
                ),
            },
            status=status.HTTP_410_GONE,
        )


class LeadLookupView(APIView):
    authentication_classes = (CombinedAuthentication,)
    permission_classes = (TenantAccessPermission,)

    def get(self, request: Request) -> Response:
        query = request.query_params.get("q", "").strip()
        tenant = resolve_tenant(request)
        digits = only_digits(query)

        if len(digits) == 11:
            return Response(
                {
                    "code": "CPF_LOOKUP_REQUIRES_JOB",
                    "detail": (
                        "CPF não é consultado por GET. Inicie um enriquecimento explícito para "
                        "evitar custo e tratamento de dado pessoal sem intenção registrada."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        company: Company | None = None
        if len(digits) == 14:
            establishment = (
                Establishment.objects.filter(entity__tenant=tenant, cnpj=digits)
                .select_related("company__entity")
                .first()
            )
            company = establishment.company if establishment else None

        if company is None and query:
            company = (
                Company.objects.filter(entity__tenant=tenant, legal_name__icontains=query).first()
                or Company.objects.filter(
                    entity__tenant=tenant,
                    trade_name__icontains=query,
                ).first()
                or Company.objects.filter(entity__tenant=tenant, cnpj_root__icontains=query).first()
            )
        if company:
            return Response(_company_lead(company))

        if query:
            relationship = (
                Relationship.objects.filter(
                    tenant=tenant,
                    person__full_name__icontains=query,
                )
                .select_related("person__entity", "company__entity")
                .order_by("-updated_at")
                .first()
            )
            if relationship:
                return Response(_relationship_lead(relationship))

        return Response({"detail": "Lead não localizado."}, status=status.HTTP_404_NOT_FOUND)


class LeadRevealPhoneView(APIView):
    authentication_classes = (CombinedAuthentication,)
    permission_classes = (TenantAccessPermission,)

    def patch(self, request: Request, lead_id: str) -> Response:
        tenant = resolve_tenant(request)
        try:
            lead_uuid = uuid.UUID(lead_id)
        except (ValueError, TypeError):
            return Response(
                {"detail": "Identificador de lead inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contact = ContactPoint.objects.filter(
            owner__tenant=tenant,
            owner_id=lead_uuid,
            kind=ContactPoint.Kind.PHONE,
        ).first()
        if contact:
            return Response(
                {
                    "id": lead_id,
                    "phone": contact.normalized_value,
                    "phoneRevealed": True,
                    "phoneEvidenceStatus": "OBSERVED",
                    "whatsappEvidenceStatus": "OBSERVED",
                }
            )
        return Response(
            {
                "id": lead_id,
                "phone": None,
                "phoneRevealed": False,
                "message": "Nenhum telefone registrado para este lead.",
            }
        )


class ImportsCollectionView(APIView):
    authentication_classes = (CombinedAuthentication,)
    permission_classes = (TenantAccessPermission,)

    def post(self, request: Request) -> Response:
        resolve_tenant(request)
        return Response(
            {
                "code": "LEGACY_IMPORT_REMOVED",
                "detail": (
                    "Este formato de importação foi desativado porque não persistia os registros. "
                    "Use POST /api/v1/lotes/ com arquivo CSV e Idempotency-Key."
                ),
            },
            status=status.HTTP_410_GONE,
        )


class ListArchiveView(APIView):
    authentication_classes = (CombinedAuthentication,)
    permission_classes = (TenantAccessPermission,)

    def patch(self, request: Request, list_id: str) -> Response:
        resolve_tenant(request)
        return Response(
            {
                "code": "ACTIVATION_LISTS_NOT_CONFIGURED",
                "detail": "Nenhuma lista foi alterada.",
                "listId": list_id,
            },
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )


class ListAddLeadsView(APIView):
    authentication_classes = (CombinedAuthentication,)
    permission_classes = (TenantAccessPermission,)

    def post(self, request: Request, list_id: str) -> Response:
        resolve_tenant(request)
        return Response(
            {
                "code": "ACTIVATION_LISTS_NOT_CONFIGURED",
                "detail": "Nenhum lead foi vinculado.",
                "listId": list_id,
            },
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )


class EnrichmentCompanyView(APIView):
    authentication_classes = (CombinedAuthentication,)
    permission_classes = (TenantAccessPermission,)

    def post(self, request: Request) -> Response:
        payload = _get_payload(request)
        query = str(payload.get("query") or payload.get("cnpj") or "").strip()
        raw_caps = payload.get("capabilities", [])
        capabilities: list[str] = raw_caps if isinstance(raw_caps, list) else []
        tenant = resolve_tenant(request)

        result = enrich_company_live(query=query, tenant=tenant, capabilities=capabilities)

        run_record = {
            "id": result.get("runId", f"run_{uuid.uuid4().hex[:8]}"),
            "entityType": "COMPANY",
            "query": query,
            "capabilities": capabilities,
            "status": "COMPLETED" if result.get("company") else "FAILED",
            "matchedEntityId": result.get("companyId") or None,
            "errorMessage": (
                result["sections"][0].get("errorMessage")
                if not result.get("company") and result.get("sections")
                else None
            ),
            "startedAt": timezone.now().isoformat(),
            "completedAt": timezone.now().isoformat(),
        }
        current_runs = cache.get(f"enrichment_runs:{tenant.pk}", [])
        cache.set(
            f"enrichment_runs:{tenant.pk}",
            [run_record, *(current_runs if isinstance(current_runs, list) else [])[:19]],
            timeout=86400 * 7,
        )

        return Response(result)


class EnrichmentPersonView(APIView):
    """Enriquecimento cadastral de Pessoa Física (CPF) com garantia técnica de WhatsApp."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (TenantAccessPermission,)

    def post(self, request: Request) -> Response:
        payload = _get_payload(request)
        query = str(payload.get("query") or payload.get("cpf") or "").strip()
        raw_caps = payload.get("capabilities", [])
        capabilities: list[str] = raw_caps if isinstance(raw_caps, list) else []
        tenant = resolve_tenant(request)

        result = enrich_person_live(query=query, tenant=tenant, capabilities=capabilities)

        run_record = {
            "id": result.get("runId", f"run_{uuid.uuid4().hex[:8]}"),
            "entityType": "PERSON",
            "query": query,
            "capabilities": capabilities,
            "status": "COMPLETED" if result.get("person") else "FAILED",
            "matchedEntityId": result.get("personId") or None,
            "errorMessage": (
                result["sections"][0].get("errorMessage")
                if not result.get("person") and result.get("sections")
                else None
            ),
            "startedAt": timezone.now().isoformat(),
            "completedAt": timezone.now().isoformat(),
        }
        current_runs = cache.get(f"enrichment_runs:{tenant.pk}", [])
        cache.set(
            f"enrichment_runs:{tenant.pk}",
            [run_record, *(current_runs if isinstance(current_runs, list) else [])[:19]],
            timeout=86400 * 7,
        )

        return Response(result)


class EnrichmentLookupView(APIView):
    authentication_classes = (CombinedAuthentication,)
    permission_classes = (TenantAccessPermission,)

    def get(self, request: Request) -> Response:
        return LeadLookupView().get(request)


class DiscoveryExtractView(APIView):
    authentication_classes = (CombinedAuthentication,)
    permission_classes = (TenantAccessPermission,)

    def post(self, request: Request) -> Response:
        resolve_tenant(request)
        return Response(
            {
                "code": "LEGACY_DISCOVERY_REMOVED",
                "detail": (
                    "A extração antiga foi desativada porque declarava conclusão sem persistir "
                    "dados. Materialize uma descoberta concluída em "
                    "POST /api/v1/descobertas/{id}/materializar/."
                ),
            },
            status=status.HTTP_410_GONE,
        )
