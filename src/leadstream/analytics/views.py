from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.http import Http404, StreamingHttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from leadstream.batches.models import Batch, BatchItem
from leadstream.common.api import reject_tenant_override, resolve_tenant
from leadstream.entities.models import (
    Company,
    ContactPoint,
    Entity,
    Establishment,
    Person,
    Relationship,
    SocialProfile,
)
from leadstream.entities.normalization import only_digits
from leadstream.evidence.models import Observation
from leadstream.integrations.models import CRMConnection
from leadstream.intelligence.cnae import KNOWN_CNAES
from leadstream.providers.enrichment_jobs import create_enrichment_job
from leadstream.providers.models import EnrichmentJob
from leadstream.providers.serializers import (
    EnrichmentJobSerializer,
    IndividualEnrichmentRequestSerializer,
)
from leadstream.security.authentication import CombinedAuthentication
from leadstream.security.models import SecurityAuditLog
from leadstream.security.permissions import TenantAccessPermission

from .exporter import stream_activation_list_csv
from .models import ActivationList, ActivationListMember


def _get_payload(request: Request) -> dict[str, Any]:
    return request.data if isinstance(request.data, dict) else {}


def _percent(part: int, total: int) -> int:
    return round((part / total) * 100) if total else 0


VALIDATED_CONTACT_STATUSES = (
    ContactPoint.Status.CAPABILITY_VALID,
    ContactPoint.Status.CONFIRMED,
)


def _activation_lists_for_tenant(tenant: Any) -> Any:
    return ActivationList.objects.filter(tenant=tenant).annotate(
        lead_count=Count("members", distinct=True),
        valid_count=Count(
            "members__entity",
            filter=Q(
                members__entity__contact_points__kind=ContactPoint.Kind.EMAIL,
                members__entity__contact_points__status__in=VALIDATED_CONTACT_STATUSES,
            ),
            distinct=True,
        ),
        catch_all_count=Count(
            "members__entity",
            filter=Q(
                members__entity__contact_points__kind=ContactPoint.Kind.EMAIL,
                members__entity__contact_points__capabilities__catch_all=True,
            ),
            distinct=True,
        ),
        invalid_count=Count(
            "members__entity",
            filter=Q(
                members__entity__contact_points__kind=ContactPoint.Kind.EMAIL,
                members__entity__contact_points__status=ContactPoint.Status.INVALID,
            ),
            distinct=True,
        ),
    )


def _activation_list_payload(activation_list: ActivationList) -> dict[str, Any]:
    lead_ids = [str(value) for value in activation_list.members.values_list("entity_id", flat=True)]
    return {
        "id": str(activation_list.pk),
        "name": activation_list.name,
        "description": activation_list.description,
        "leadCount": int(getattr(activation_list, "lead_count", len(lead_ids))),
        "lastSynced": "Nunca sincronizada",
        "crmTarget": activation_list.crm_target or "Não configurado",
        "crmStatus": "Arquivada" if activation_list.archived_at else "Pronta para ativação",
        "validCount": int(getattr(activation_list, "valid_count", 0)),
        "catchAllCount": int(getattr(activation_list, "catch_all_count", 0)),
        "invalidCount": int(getattr(activation_list, "invalid_count", 0)),
        "leadIds": lead_ids,
        "createdAt": activation_list.created_at.isoformat(),
        "updatedAt": activation_list.updated_at.isoformat(),
        "isArchived": activation_list.archived_at is not None,
    }


def _validated_lead_ids(payload: dict[str, Any]) -> list[uuid.UUID]:
    values = payload.get("leadIds", [])
    if not isinstance(values, list) or len(values) > 10_000:
        raise ValidationError({"leadIds": "Informe uma lista com até 10 mil leads."})
    try:
        return list(dict.fromkeys(uuid.UUID(str(value)) for value in values))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValidationError(
            {"leadIds": "Um ou mais identificadores de lead são inválidos."}
        ) from exc


def _add_entities_to_activation_list(
    *, activation_list: ActivationList, lead_ids: list[uuid.UUID]
) -> None:
    if not lead_ids:
        return
    entities = list(Entity.objects.filter(tenant=activation_list.tenant, pk__in=lead_ids))
    if len(entities) != len(lead_ids):
        raise ValidationError(
            {"leadIds": "Um ou mais leads não existem ou pertencem a outro workspace."}
        )
    ActivationListMember.objects.bulk_create(
        [
            ActivationListMember(
                tenant=activation_list.tenant,
                activation_list=activation_list,
                entity=entity,
            )
            for entity in entities
        ],
        ignore_conflicts=True,
    )
    activation_list.save(update_fields=("updated_at",))


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


def _lead_for_entity(entity: Entity) -> dict[str, Any] | None:
    if entity.kind == Entity.Kind.COMPANY:
        company = Company.objects.filter(entity=entity).select_related("entity").first()
        return _company_lead(company) if company else None
    if entity.kind == Entity.Kind.PERSON:
        relationship = (
            Relationship.objects.filter(
                tenant=entity.tenant,
                person__entity=entity,
                ended_on__isnull=True,
            )
            .select_related("person__entity", "company__entity")
            .order_by("-updated_at")
            .first()
        )
        return _relationship_lead(relationship) if relationship else None
    return None


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
        lists_count = ActivationList.objects.filter(tenant=tenant, archived_at__isnull=True).count()

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
                    "lists": lists_count,
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
        """Aplica somente expiração determinística; não promove nem inventa evidência."""
        tenant = resolve_tenant(request)
        reject_tenant_override(_get_payload(request))
        now = timezone.now()
        active_statuses = (
            ContactPoint.Status.OBSERVED,
            ContactPoint.Status.DOMAIN_VALID,
            ContactPoint.Status.CAPABILITY_VALID,
            ContactPoint.Status.CONFIRMED,
        )
        expired_contacts = ContactPoint.objects.filter(
            tenant=tenant,
            status__in=active_statuses,
            expires_at__lte=now,
        ).update(status=ContactPoint.Status.EXPIRED, updated_at=now)
        stale_contacts = ContactPoint.objects.filter(
            tenant=tenant,
            status__in=active_statuses,
            stale_at__lte=now,
        ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now)).update(
            status=ContactPoint.Status.STALE,
            updated_at=now,
        )
        expired_profiles = SocialProfile.objects.filter(
            tenant=tenant,
            status__in=active_statuses,
            expires_at__lte=now,
        ).update(status=ContactPoint.Status.EXPIRED, updated_at=now)
        health = self.get(request).data
        return Response(
            {
                "success": True,
                "repairedContacts": expired_contacts + stale_contacts + expired_profiles,
                "boostedScores": 0,
                "health": health,
            }
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
        tenant = resolve_tenant(request)
        return Response(
            [
                _activation_list_payload(activation_list)
                for activation_list in _activation_lists_for_tenant(tenant)
            ]
        )

    def post(self, request: Request) -> Response:
        tenant = resolve_tenant(request)
        payload = _get_payload(request)
        reject_tenant_override(payload)
        name = str(payload.get("name", "")).strip()
        description = str(payload.get("description", "")).strip()
        crm_target = str(payload.get("crmTarget", "")).strip()
        if not name or len(name) > 160:
            raise ValidationError({"name": "Informe um nome de até 160 caracteres."})
        if len(description) > 500:
            raise ValidationError({"description": "Use no máximo 500 caracteres."})
        if len(crm_target) > 80:
            raise ValidationError({"crmTarget": "Use no máximo 80 caracteres."})
        lead_ids = _validated_lead_ids(payload)
        with transaction.atomic():
            activation_list = ActivationList.objects.create(
                tenant=tenant,
                name=name,
                description=description,
                crm_target=crm_target,
            )
            _add_entities_to_activation_list(
                activation_list=activation_list,
                lead_ids=lead_ids,
            )
        activation_list = _activation_lists_for_tenant(tenant).get(pk=activation_list.pk)
        return Response(_activation_list_payload(activation_list), status=status.HTTP_201_CREATED)


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
                        "description": "Sinais de conformidade disponíveis nas fontes configuradas",
                    },
                ],
                "capabilities": [
                    {
                        "id": "cnpj_qsa",
                        "groupId": "company",
                        "label": "CNPJ & Quadro Societário",
                        "description": (
                            "Dados cadastrais e societários conforme fontes configuradas"
                        ),
                        "highlights": ["Razão Social", "CNAE", "Sócios & Administradores"],
                        "depth": "Essencial",
                    },
                    {
                        "id": "emails_smtp",
                        "groupId": "sales",
                        "label": "E-mails e sinais técnicos",
                        "description": "Sintaxe, domínio e validações realmente executadas",
                        "highlights": [
                            "Sintaxe",
                            "Domínio",
                            "Resultado inconclusivo quando a caixa não é testada",
                        ],
                        "depth": "Dependente do provedor",
                    },
                    {
                        "id": "phones_whatsapp",
                        "groupId": "sales",
                        "label": "Telefone e WhatsApp atribuíveis",
                        "description": "Canais ligados à pessoa somente quando houver evidência",
                        "highlights": [
                            "Formato E.164",
                            "Sinal de WhatsApp quando consultado",
                            "Evidência Atribuível",
                        ],
                        "depth": "Detalhado",
                    },
                    {
                        "id": "cpf_cadastral",
                        "groupId": "company",
                        "label": "CPF e dados cadastrais PF",
                        "description": "Validação estrutural local e dados de fonte autorizada",
                        "highlights": ["Formato", "Dígitos verificadores", "Origem dos atributos"],
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
                            "Resultado com horário e origem",
                            "Ausência explícita quando não consultado",
                        ],
                        "depth": "Dependente do provedor",
                    },
                    {
                        "id": "consignado_core",
                        "groupId": "operations",
                        "label": "Cenários de crédito consignado",
                        "description": (
                            "Sinais de benefício e simulações, sem declarar elegibilidade"
                        ),
                        "highlights": ["Cenário de margem", "Sinais INSS", "Sinais SIAPE"],
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
                            "Consulta de bloqueio quando a integração for aplicável"
                        ),
                        "highlights": [
                            "Status consultado",
                            "Canal e fonte",
                            "Resultado inconclusivo explícito",
                        ],
                        "depth": "Conformidade",
                    },
                    {
                        "id": "mailing_top3_discagem",
                        "groupId": "sales",
                        "label": "Priorização de até 3 telefones",
                        "description": (
                            "Ordenação por evidência, sem presumir operadora ou WhatsApp"
                        ),
                        "highlights": [
                            "Top 3 Celulares",
                            "Evidência por canal",
                            "Restrições de contato",
                        ],
                        "depth": "Dependente do provedor",
                    },
                ],
                "presets": [
                    {
                        "id": "commercial",
                        "label": "Prospecção Comercial Outbound",
                        "description": "Decisores e canais atribuíveis encontrados nas fontes",
                        "capabilityIds": ["cnpj_qsa", "emails_smtp", "phones_whatsapp"],
                    },
                    {
                        "id": "pf_whatsapp",
                        "label": "Higienização de CPF e sinal de WhatsApp",
                        "description": "Validação estrutural e sinal de WhatsApp quando consultado",
                        "capabilityIds": ["cpf_cadastral", "phones_whatsapp_probe"],
                    },
                    {
                        "id": "consignado_premium",
                        "label": "Crédito consignado e conformidade",
                        "description": (
                            "Dossiê de sinais, cenários de margem, NMP e canais priorizados"
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
        jobs = EnrichmentJob.objects.filter(tenant=tenant).order_by("-created_at")[:50]
        return Response(EnrichmentJobSerializer(jobs, many=True).data)


class EnrichmentJobDetailView(APIView):
    authentication_classes = (CombinedAuthentication,)
    permission_classes = (TenantAccessPermission,)

    def get(self, request: Request, job_id: uuid.UUID) -> Response:
        job = EnrichmentJob.objects.filter(
            pk=job_id,
            tenant=resolve_tenant(request),
        ).first()
        if not job:
            return Response(
                {"detail": "Execução de enriquecimento não encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(EnrichmentJobSerializer(job, context={"include_result": True}).data)


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
        tenant = resolve_tenant(request)
        try:
            list_uuid = uuid.UUID(list_id)
        except (TypeError, ValueError):
            raise ValidationError({"listId": "Identificador de lista inválido."}) from None
        activation_list = ActivationList.objects.filter(tenant=tenant, pk=list_uuid).first()
        if activation_list is None:
            return Response(
                {"detail": "Lista não encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if activation_list.archived_at is None:
            activation_list.archived_at = timezone.now()
            activation_list.save(update_fields=("archived_at", "updated_at"))
        activation_list = _activation_lists_for_tenant(tenant).get(pk=activation_list.pk)
        return Response(_activation_list_payload(activation_list))


class ListAddLeadsView(APIView):
    authentication_classes = (CombinedAuthentication,)
    permission_classes = (TenantAccessPermission,)

    def get(self, request: Request, list_id: str) -> Response:
        tenant = resolve_tenant(request)
        try:
            list_uuid = uuid.UUID(list_id)
        except (TypeError, ValueError):
            raise ValidationError({"listId": "Identificador de lista inválido."}) from None
        activation_list = ActivationList.objects.filter(tenant=tenant, pk=list_uuid).first()
        if activation_list is None:
            return Response(
                {"detail": "Lista não encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )
        members = list(
            activation_list.members.select_related("entity")
            .order_by("added_at")[:500]
        )
        leads = [lead for member in members if (lead := _lead_for_entity(member.entity))]
        total = activation_list.members.count()
        return Response({"count": total, "results": leads, "truncated": total > len(members)})

    def post(self, request: Request, list_id: str) -> Response:
        tenant = resolve_tenant(request)
        payload = _get_payload(request)
        reject_tenant_override(payload)
        try:
            list_uuid = uuid.UUID(list_id)
        except (TypeError, ValueError):
            raise ValidationError({"listId": "Identificador de lista inválido."}) from None
        activation_list = ActivationList.objects.filter(tenant=tenant, pk=list_uuid).first()
        if activation_list is None:
            return Response(
                {"detail": "Lista não encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if activation_list.archived_at is not None:
            raise ValidationError({"listId": "Uma lista arquivada não pode receber novos leads."})
        with transaction.atomic():
            _add_entities_to_activation_list(
                activation_list=activation_list,
                lead_ids=_validated_lead_ids(payload),
            )
        activation_list = _activation_lists_for_tenant(tenant).get(pk=activation_list.pk)
        return Response(_activation_list_payload(activation_list))


class ListExportView(APIView):
    authentication_classes = (CombinedAuthentication,)
    permission_classes = (TenantAccessPermission,)

    def get(self, request: Request, list_id: str) -> StreamingHttpResponse:
        tenant = resolve_tenant(request)
        try:
            list_uuid = uuid.UUID(list_id)
        except (TypeError, ValueError):
            raise ValidationError({"listId": "Identificador de lista inválido."}) from None
        activation_list = ActivationList.objects.filter(tenant=tenant, pk=list_uuid).first()
        if activation_list is None:
            raise Http404("Lista não encontrada.")
        response = StreamingHttpResponse(
            stream_activation_list_csv(activation_list),
            content_type="text/csv; charset=utf-8",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="leadstream-lista-{activation_list.pk}.csv"'
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class EnrichmentCompanyView(APIView):
    authentication_classes = (CombinedAuthentication,)
    permission_classes = (TenantAccessPermission,)

    def post(self, request: Request) -> Response:
        return _create_individual_enrichment_job(
            request=request,
            entity_type=EnrichmentJob.EntityType.COMPANY,
        )


class EnrichmentPersonView(APIView):
    """Enriquecimento cadastral de Pessoa Física (CPF) com garantia técnica de WhatsApp."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (TenantAccessPermission,)

    def post(self, request: Request) -> Response:
        return _create_individual_enrichment_job(
            request=request,
            entity_type=EnrichmentJob.EntityType.PERSON,
        )


def _create_individual_enrichment_job(*, request: Request, entity_type: str) -> Response:
    payload = _get_payload(request)
    if "query" not in payload:
        legacy_key = "cnpj" if entity_type == EnrichmentJob.EntityType.COMPANY else "cpf"
        payload = {**payload, "query": payload.get(legacy_key, "")}
    serializer = IndividualEnrichmentRequestSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    try:
        creation = create_enrichment_job(
            tenant=resolve_tenant(request),
            entity_type=entity_type,
            query=serializer.validated_data["query"],
            capabilities=serializer.validated_data.get("capabilities", []),
            idempotency_key=request.headers.get("Idempotency-Key", ""),
        )
    except DjangoValidationError as exc:
        detail = exc.message_dict if hasattr(exc, "message_dict") else {"detail": exc.messages}
        return Response(detail, status=status.HTTP_400_BAD_REQUEST)
    response_status = status.HTTP_202_ACCEPTED if creation.created else status.HTTP_200_OK
    return Response(
        EnrichmentJobSerializer(creation.job, context={"include_result": True}).data,
        status=response_status,
    )


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
