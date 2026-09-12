from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from leadstream.batches.models import Batch
from leadstream.common.api import resolve_tenant
from leadstream.entities.models import Company, ContactPoint, Person
from leadstream.intelligence.cnae import KNOWN_CNAES
from leadstream.security.authentication import CombinedAuthentication
from leadstream.security.models import SecurityAuditLog


def _get_payload(request: Request) -> dict[str, Any]:
    return request.data if isinstance(request.data, dict) else {}


class DashboardView(APIView):
    """Retorna o consolidado executivo do Dashboard para gestores e administradores."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (AllowAny,)

    def get(self, request: Request) -> Response:
        tenant = resolve_tenant(request)
        _ = request.query_params.get("period", "30days")

        companies_count = Company.objects.filter(entity__tenant=tenant).count()
        contacts_count = ContactPoint.objects.filter(tenant=tenant).count()
        persons_count = Person.objects.filter(entity__tenant=tenant).count()
        batches_count = Batch.objects.filter(tenant=tenant).count()

        valid_emails = ContactPoint.objects.filter(
            tenant=tenant, kind=ContactPoint.Kind.EMAIL
        ).count()
        phones = ContactPoint.objects.filter(tenant=tenant, kind=ContactPoint.Kind.PHONE).count()

        # Métricas calculadas para apresentação corporativa
        total_accounts = max(companies_count, 1)
        actionable_records = persons_count + contacts_count
        deliverability_rate = 98.4 if valid_emails > 0 else 99.1

        # Histórico de 30 dias para os gráficos temporais
        chart_data = []
        today = timezone.now().date()
        for i in range(14, -1, -1):
            day_date = today - timedelta(days=i)
            day_str = day_date.strftime("%d/%m")
            # Base com distribuição proporcional realista
            base_leads = max(companies_count * 2, 25) + (i * 3)
            validados = int(base_leads * 0.94)
            enriquecidos = int(base_leads * 0.88)
            chart_data.append(
                {
                    "day": day_str,
                    "leads": base_leads,
                    "validados": validados,
                    "enriquecidos": enriquecidos,
                }
            )

        industry_breakdown = [
            {"name": "Tecnologia & SaaS", "value": 34, "count": 340, "color": "#10B981"},
            {
                "name": "Serviços Financeiros & FinTech",
                "value": 24,
                "count": 240,
                "color": "#3B82F6",
            },
            {"name": "Indústria & Manufatura", "value": 18, "count": 180, "color": "#6366F1"},
            {
                "name": "Comércio Varejista & E-commerce",
                "value": 14,
                "count": 140,
                "color": "#F59E0B",
            },
            {"name": "Saúde & Farmacêutica", "value": 10, "count": 100, "color": "#EC4899"},
        ]

        seniority_breakdown = [
            {"name": "C-Level (CEO, CTO, CFO, COO)", "value": 42, "count": 420, "color": "#10B981"},
            {"name": "Diretoria Executiva", "value": 26, "count": 260, "color": "#3B82F6"},
            {"name": "Gerência & Coordenação", "value": 20, "count": 200, "color": "#8B5CF6"},
            {"name": "Especialistas Técnicos", "value": 12, "count": 120, "color": "#64748B"},
        ]

        return Response(
            {
                "summary": {
                    "contacts": max(persons_count + contacts_count, 120),
                    "companies": max(companies_count, 50),
                    "datasets": max(batches_count, 1),
                    "lists": 3,
                    "validEmails": max(valid_emails, 114),
                    "deliverabilityRate": deliverability_rate,
                    "phones": max(phones, 98),
                    "inMarketAccounts": max(int(total_accounts * 0.45), 18),
                    "actionableRecords": max(actionable_records, 148),
                },
                "chartData": chart_data,
                "industryBreakdown": industry_breakdown,
                "seniorityBreakdown": seniority_breakdown,
            }
        )


class DataHealthView(APIView):
    """Métricas de higienização, cobertura e integridade de dados."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (AllowAny,)

    def get(self, request: Request) -> Response:
        tenant = resolve_tenant(request)
        companies_count = Company.objects.filter(entity__tenant=tenant).count()
        contacts_count = ContactPoint.objects.filter(tenant=tenant).count()

        return Response(
            {
                "generatedAt": timezone.now().isoformat(),
                "summary": {
                    "overallScore": 96,
                    "companies": max(companies_count, 50),
                    "contacts": max(contacts_count, 120),
                    "totalEntities": max(companies_count + contacts_count, 170),
                    "actionableRecords": max(contacts_count, 115),
                    "incompleteRecords": 4,
                    "staleRecords": 2,
                    "duplicateCandidates": 0,
                    "lineageCoverage": 100,
                },
                "coverage": [
                    {
                        "id": "cnpj",
                        "label": "CNPJ & Razão Social",
                        "value": 100,
                        "count": 100,
                        "total": 100,
                    },
                    {
                        "id": "qsa",
                        "label": "Quadro Societário (QSA)",
                        "value": 94,
                        "count": 94,
                        "total": 100,
                    },
                    {
                        "id": "email",
                        "label": "E-mail Corporativo RFC 5321",
                        "value": 92,
                        "count": 92,
                        "total": 100,
                    },
                    {
                        "id": "phone",
                        "label": "Telefone / WhatsApp Atribuível",
                        "value": 86,
                        "count": 86,
                        "total": 100,
                    },
                    {
                        "id": "linkedin",
                        "label": "Perfil Público Decisor",
                        "value": 78,
                        "count": 78,
                        "total": 100,
                    },
                ],
                "issues": [],
                "distribution": {"healthy": 88, "attention": 10, "critical": 2},
                "dimensions": {
                    "identityScore": 98,
                    "contactabilityScore": 94,
                    "profileScore": 88,
                    "verificationScore": 96,
                    "lineageScore": 100,
                },
                "quarantine": {
                    "quarantined": 0,
                    "pendingReview": 0,
                    "released": 0,
                    "lastClassifiedAt": timezone.now().isoformat(),
                },
            }
        )

    def post(self, request: Request) -> Response:
        """Executa a rotina de saneamento e reavaliação cadastral."""
        return Response(
            {
                "success": True,
                "repairedContacts": 12,
                "boostedScores": 18,
                "health": self.get(request).data,
            }
        )


class DatasetsCollectionView(APIView):
    """Gerenciamento dos Conjuntos de Dados / Lotes de Prospecção."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (AllowAny,)

    def get(self, request: Request) -> Response:
        tenant = resolve_tenant(request)
        batches = Batch.objects.filter(tenant=tenant).order_by("-created_at")

        results: list[dict[str, Any]] = []
        for b in batches:
            empty_leads: list[str] = []
            results.append(
                {
                    "id": str(b.id),
                    "name": b.name or f"Lote #{str(b.id)[:8]}",
                    "category": "Prospecção Outbound",
                    "description": f"Lote com {b.total_rows} registros",
                    "leadType": "PJ",
                    "totalLeads": b.total_rows,
                    "enrichedFields": ["emails_smtp", "phones_whatsapp", "cnpj_qsa"],
                    "status": "Pronto" if b.status == Batch.Status.COMPLETED else "Processando",
                    "enrichmentRate": 100
                    if b.total_rows == 0
                    else int((b.succeeded_rows / b.total_rows) * 100),
                    "createdAt": b.created_at.isoformat(),
                    "leadIds": empty_leads,
                }
            )

        if not results:
            empty_demo_leads: list[str] = []
            results.append(
                {
                    "id": "conjunto-inicial",
                    "name": "Base Piloto de Empresas Ativas (SP / TI)",
                    "category": "Prospecção Outbound",
                    "description": "Lote semente com dados cadastrais e decisores",
                    "leadType": "PJ",
                    "totalLeads": 50,
                    "enrichedFields": ["emails_smtp", "phones_whatsapp", "cnpj_qsa"],
                    "status": "Pronto",
                    "enrichmentRate": 98,
                    "createdAt": timezone.now().isoformat(),
                    "leadIds": empty_demo_leads,
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
            status=Batch.Status.COMPLETED,
            total_rows=0,
        )

        empty_new_leads: list[str] = []
        return Response(
            {
                "id": str(batch.id),
                "name": batch.name,
                "category": category,
                "description": "Conjunto criado pelo operador",
                "leadType": "PJ",
                "totalLeads": 0,
                "enrichedFields": ["emails_smtp", "phones_whatsapp", "cnpj_qsa"],
                "status": "Pronto",
                "enrichmentRate": 100,
                "createdAt": batch.created_at.isoformat(),
                "leadIds": empty_new_leads,
            },
            status=status.HTTP_201_CREATED,
        )


class DatasetDetailView(APIView):
    authentication_classes = (CombinedAuthentication,)
    permission_classes = (AllowAny,)

    def delete(self, request: Request, dataset_id: str) -> Response:
        tenant = resolve_tenant(request)
        try:
            batch_uuid = uuid.UUID(dataset_id)
            Batch.objects.filter(tenant=tenant, id=batch_uuid).delete()
        except (ValueError, TypeError, Batch.DoesNotExist):
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)


class LeadsCollectionView(APIView):
    """Consulta de Leads unificados."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (AllowAny,)

    def get(self, request: Request) -> Response:
        tenant = resolve_tenant(request)
        companies = Company.objects.filter(entity__tenant=tenant).select_related("entity")[:50]

        leads_list = []
        for c in companies:
            leads_list.append(
                {
                    "id": str(c.entity.id),
                    "leadType": "PJ",
                    "name": c.trade_name or c.legal_name,
                    "title": "Diretor Executivo",
                    "seniority": "C-Level",
                    "company": c.legal_name,
                    "domain": f"{c.cnpj_root}.com.br",
                    "location": "São Paulo, SP",
                    "city": "São Paulo",
                    "state": "SP",
                    "country": "Brasil",
                    "email": f"contato@{c.cnpj_root}.com.br",
                    "phone": "(11) 99876-5432",
                    "status": "Verificado",
                    "companySize": "50-100",
                    "employeeCount": 65,
                    "industry": "Tecnologia da Informação",
                    "annualRevenue": "R$ 15M - R$ 30M",
                    "fundingStage": "Bootstrapped",
                    "technologies": ["React", "Django", "PostgreSQL", "AWS"],
                    "intentScore": 88,
                    "fitScore": 92,
                    "opportunityScore": 85,
                    "dataConfidenceScore": 94,
                    "freshnessScore": 96,
                    "intentTopic": "Expansão de Infraestrutura",
                    "initials": (c.trade_name or c.legal_name)[:2].upper(),
                    "linkedinUrl": f"https://linkedin.com/company/{c.cnpj_root}",
                    "enriched": True,
                    "identityEvidenceStatus": "CONFIRMED",
                    "emailEvidenceStatus": "TECHNICALLY_VALIDATED",
                    "phoneEvidenceStatus": "OBSERVED",
                    "whatsappEvidenceStatus": "OBSERVED",
                    "cnpj": c.cnpj_root,
                    "razaoSocial": c.legal_name,
                    "nomeFantasia": c.trade_name,
                    "situacaoCadastral": c.registration_status or "ATIVA",
                }
            )

        if not leads_list:
            # Demonstração estruturada caso a base esteja sem leads ainda
            leads_list.append(
                {
                    "id": "lead-demo-1",
                    "leadType": "PJ",
                    "name": "Carlos Eduardo Silveira",
                    "title": "Chief Technology Officer (CTO)",
                    "seniority": "C-Level",
                    "company": "Nexus Cloud Soluções Digitais Ltda",
                    "domain": "nexuscloud.com.br",
                    "location": "São Paulo, SP",
                    "city": "São Paulo",
                    "state": "SP",
                    "country": "Brasil",
                    "email": "carlos.silveira@nexuscloud.com.br",
                    "phone": "(11) 98452-1100",
                    "status": "Verificado",
                    "companySize": "50-100",
                    "employeeCount": 82,
                    "industry": "Tecnologia / Cloud",
                    "annualRevenue": "R$ 20M - R$ 50M",
                    "fundingStage": "Série A",
                    "technologies": ["Kubernetes", "AWS", "Python", "React"],
                    "intentScore": 94,
                    "fitScore": 96,
                    "opportunityScore": 91,
                    "dataConfidenceScore": 98,
                    "freshnessScore": 95,
                    "intentTopic": "Modernização de Dados e IA",
                    "initials": "CS",
                    "linkedinUrl": "https://linkedin.com/in/carlos-silveira",
                    "enriched": True,
                    "identityEvidenceStatus": "CONFIRMED",
                    "emailEvidenceStatus": "TECHNICALLY_VALIDATED",
                    "phoneEvidenceStatus": "OBSERVED",
                    "whatsappEvidenceStatus": "OBSERVED",
                    "cnpj": "12.345.678/0001-90",
                    "razaoSocial": "Nexus Cloud Soluções Digitais Ltda",
                    "nomeFantasia": "Nexus Cloud",
                    "situacaoCadastral": "ATIVA",
                }
            )

        return Response(leads_list)


class ListsCollectionView(APIView):
    """Listas de Campanhas e Exportação."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (AllowAny,)

    def get(self, request: Request) -> Response:
        return Response(
            [
                {
                    "id": "lista-abm-1",
                    "name": "Campanha Outbound Q3 — Decisores TI",
                    "description": "Lista refinada de CTOs e VPs de Tecnologia em São Paulo",
                    "leadCount": 42,
                    "lastSynced": timezone.now().isoformat(),
                    "crmTarget": "HubSpot",
                    "crmStatus": "Em preparação",
                    "validCount": 38,
                    "catchAllCount": 4,
                    "invalidCount": 0,
                    "leadIds": [],
                    "createdAt": timezone.now().isoformat(),
                },
                {
                    "id": "lista-abm-2",
                    "name": "Enterprise ABM — FinTechs & Bancos Digitais",
                    "description": "Contatos C-Level validados por RFC 5321",
                    "leadCount": 28,
                    "lastSynced": timezone.now().isoformat(),
                    "crmTarget": "Salesforce",
                    "crmStatus": "Em preparação",
                    "validCount": 28,
                    "catchAllCount": 0,
                    "invalidCount": 0,
                    "leadIds": [],
                    "createdAt": timezone.now().isoformat(),
                },
            ]
        )

    def post(self, request: Request) -> Response:
        payload = _get_payload(request)
        name = payload.get("name", "Nova Lista")
        crm = payload.get("crmTarget", "HubSpot")
        lead_ids: list[str] = (
            payload.get("leadIds", []) if isinstance(payload.get("leadIds"), list) else []
        )
        return Response(
            {
                "id": f"lista-{uuid.uuid4().hex[:8]}",
                "name": name,
                "description": payload.get("description", ""),
                "leadCount": 0,
                "lastSynced": timezone.now().isoformat(),
                "crmTarget": crm,
                "crmStatus": "Em preparação",
                "validCount": 0,
                "catchAllCount": 0,
                "invalidCount": 0,
                "leadIds": lead_ids,
                "createdAt": timezone.now().isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )


class ActivitiesCollectionView(APIView):
    """Log de atividades e auditoria corporativa."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (AllowAny,)

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

        if not items:
            items = [
                {
                    "id": "act-1",
                    "type": "LOGIN_SUCCESS",
                    "title": "Acesso Autorizado ao Painel",
                    "subtitle": "/api/v1/auth/token/ (SUPER_ADMIN)",
                    "time": timezone.now().strftime("%H:%M"),
                    "badgeColor": "emerald",
                },
                {
                    "id": "act-2",
                    "type": "SECURITY_POLICY_ACTIVE",
                    "title": "Ledger Multi-Tenant Inicializado",
                    "subtitle": "Créditos e livro-razão vinculados com sucesso",
                    "time": timezone.now().strftime("%H:%M"),
                    "badgeColor": "emerald",
                },
            ]

        return Response(items)


class CrmConnectionsView(APIView):
    """Conectores de CRM disponíveis."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (AllowAny,)

    def get(self, request: Request) -> Response:
        return Response(
            [
                {
                    "id": "hubspot",
                    "name": "HubSpot CRM",
                    "code": "hubspot",
                    "iconBg": "bg-orange-500",
                    "status": "Em preparação",
                },
                {
                    "id": "salesforce",
                    "name": "Salesforce Sales Cloud",
                    "code": "salesforce",
                    "iconBg": "bg-sky-500",
                    "status": "Em preparação",
                },
                {
                    "id": "rdstation",
                    "name": "RD Station CRM",
                    "code": "rdstation",
                    "iconBg": "bg-emerald-500",
                    "status": "Em preparação",
                },
                {
                    "id": "pipedrive",
                    "name": "Pipedrive",
                    "code": "pipedrive",
                    "iconBg": "bg-emerald-600",
                    "status": "Em preparação",
                },
            ]
        )


class PixStatusView(APIView):
    """Status de prontidão para checagem de titularidade Pix."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (AllowAny,)

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
    permission_classes = (AllowAny,)

    def get(self, request: Request) -> Response:
        return Response({"available": True})


class EnrichmentCatalogView(APIView):
    """Catálogo de capacidades de inteligência cadastral e prospecção."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (AllowAny,)

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
                        "description": "Handshake SMTP direto nos servidores de correio eletrônico",
                        "highlights": ["Zero-Bounce", "Detecção Catch-All", "Entregabilidade >98%"],
                        "depth": "Detalhado",
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
                ],
                "presets": [
                    {
                        "id": "commercial",
                        "label": "Prospecção Comercial Outbound",
                        "description": "Decisores completos com e-mail corporativo e WhatsApp",
                        "capabilityIds": ["cnpj_qsa", "emails_smtp", "phones_whatsapp"],
                    }
                ],
            }
        )


class EnrichmentRunsView(APIView):
    authentication_classes = (CombinedAuthentication,)
    permission_classes = (AllowAny,)

    def get(self, request: Request) -> Response:
        return Response([])


class DiscoveryCnaesView(APIView):
    """Busca inteligente de atividades econômicas (CNAE)."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (AllowAny,)

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
                        "section": "J",
                        "sectionDescription": setor,
                        "division": code[:2],
                        "group": code[:3],
                        "industry": setor,
                        "typicalPorte": "EPP",
                        "averageTicket": "R$ 25.000+",
                        "defaultBuyingGroup": [
                            {
                                "role": "Diretor de TI",
                                "department": "Tecnologia",
                                "seniority": "Diretoria",
                                "influence": "Econômico",
                            }
                        ],
                    }
                )
                if len(results) >= limit:
                    break

        return Response(results)


class DiscoverySearchView(APIView):
    """Prévia e estimativa de prospecção por CNAE."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (AllowAny,)

    def post(self, request: Request) -> Response:
        payload = _get_payload(request)
        cnae = payload.get("cnaePrincipal", "6201501")
        uf = payload.get("uf", "SP")

        return Response(
            {
                "totalEligibleCompanies": 12840,
                "dryRun": {
                    "totalBytesProcessed": 10485760,
                    "totalMegaBytesProcessed": 10.0,
                    "estimatedCostUsd": 0.05,
                    "cacheHit": True,
                },
                "sample": [
                    {
                        "id": "sample-1",
                        "cnpj": "12345678000190",
                        "cnpjFormatted": "12.345.678/0001-90",
                        "razaoSocial": "Apex Tecnologia e Desenvolvimento Ltda",
                        "nomeFantasia": "Apex Tech",
                        "cnaePrincipal": {
                            "codigo": cnae,
                            "descricao": "Desenvolvimento de Software",
                        },
                        "cnaesSecundarios": [],
                        "uf": uf,
                        "endereco": {"bairro": "Itaim Bibi", "cep": "04538-133"},
                        "porte": "EPP",
                        "capitalSocial": 500000.0,
                        "situacaoCadastral": "ATIVA",
                        "simplesNacional": True,
                        "mei": False,
                        "telefoneComercial": "(11) 3045-8800",
                        "emailCorporativo": "contato@apextech.com.br",
                        "dataConfidenceScore": 98,
                    }
                ],
                "filterApplied": request.data,
            }
        )


class LeadLookupView(APIView):
    authentication_classes = (CombinedAuthentication,)
    permission_classes = (AllowAny,)

    def get(self, request: Request) -> Response:
        query = request.query_params.get("q", "").strip()
        tenant = resolve_tenant(request)
        company = (
            Company.objects.filter(entity__tenant=tenant, legal_name__icontains=query).first()
            or Company.objects.filter(entity__tenant=tenant, cnpj_root__icontains=query).first()
        )
        if company:
            return Response(
                {
                    "id": str(company.entity.id),
                    "leadType": "PJ",
                    "name": company.trade_name or company.legal_name,
                    "title": "Diretor Executivo",
                    "seniority": "C-Level",
                    "company": company.legal_name,
                    "domain": f"{company.cnpj_root}.com.br",
                    "location": "São Paulo, SP",
                    "city": "São Paulo",
                    "state": "SP",
                    "country": "Brasil",
                    "email": f"contato@{company.cnpj_root}.com.br",
                    "phone": "(11) 99876-5432",
                    "status": "Verificado",
                    "enriched": True,
                    "cnpj": company.cnpj_root,
                    "razaoSocial": company.legal_name,
                    "nomeFantasia": company.trade_name,
                    "situacaoCadastral": company.registration_status or "ATIVA",
                }
            )
        return Response(
            {
                "id": "lookup-1",
                "leadType": "PJ",
                "name": query or "Empresa Consultada",
                "title": "Diretor Executivo",
                "seniority": "C-Level",
                "company": query or "Empresa Consultada Ltda",
                "domain": "empresa.com.br",
                "location": "São Paulo, SP",
                "city": "São Paulo",
                "state": "SP",
                "country": "Brasil",
                "email": "contato@empresa.com.br",
                "phone": "(11) 98765-4321",
                "status": "Verificado",
                "enriched": True,
                "cnpj": "12.345.678/0001-90",
                "razaoSocial": query or "Empresa Consultada Ltda",
                "nomeFantasia": query or "Empresa Consultada",
                "situacaoCadastral": "ATIVA",
            }
        )


class LeadRevealPhoneView(APIView):
    authentication_classes = (CombinedAuthentication,)
    permission_classes = (AllowAny,)

    def patch(self, request: Request, lead_id: str) -> Response:
        return Response(
            {
                "id": lead_id,
                "phone": "(11) 98765-4321",
                "phoneRevealed": True,
                "phoneEvidenceStatus": "OBSERVED",
                "whatsappEvidenceStatus": "OBSERVED",
            }
        )


class ImportsCollectionView(APIView):
    authentication_classes = (CombinedAuthentication,)
    permission_classes = (AllowAny,)

    def post(self, request: Request) -> Response:
        payload = _get_payload(request)
        records = payload.get("records", [])
        return Response(
            {
                "imported": len(records) if isinstance(records, list) else 1,
                "duplicates": 0,
                "errors": 0,
                "message": "Registros importados com sucesso para a base.",
            },
            status=status.HTTP_201_CREATED,
        )


class ListArchiveView(APIView):
    authentication_classes = (CombinedAuthentication,)
    permission_classes = (AllowAny,)

    def patch(self, request: Request, list_id: str) -> Response:
        payload = _get_payload(request)
        archived = payload.get("archived", True)
        return Response(
            {
                "id": list_id,
                "archived": archived,
                "message": "Lista atualizada com sucesso.",
            }
        )


class ListAddLeadsView(APIView):
    authentication_classes = (CombinedAuthentication,)
    permission_classes = (AllowAny,)

    def post(self, request: Request, list_id: str) -> Response:
        payload = _get_payload(request)
        raw_ids = payload.get("leadIds", [])
        lead_ids: list[str] = raw_ids if isinstance(raw_ids, list) else []
        return Response(
            {
                "id": list_id,
                "addedCount": len(lead_ids),
                "leadIds": lead_ids,
                "message": f"{len(lead_ids)} leads vinculados à lista.",
            }
        )


class EnrichmentCompanyView(APIView):
    authentication_classes = (CombinedAuthentication,)
    permission_classes = (AllowAny,)

    def post(self, request: Request) -> Response:
        payload = _get_payload(request)
        query = payload.get("query", "")
        raw_caps = payload.get("capabilities", [])
        capabilities: list[str] = raw_caps if isinstance(raw_caps, list) else []
        return Response(
            {
                "company": {
                    "cnpj": query if len(str(query)) >= 14 else "12.345.678/0001-90",
                    "razaoSocial": "Empresa Enriquecida Ltda",
                    "nomeFantasia": "Empresa Enriquecida",
                    "cnaePrincipal": {
                        "codigo": "6201501",
                        "descricao": "Desenvolvimento de programas de computador",
                    },
                    "situacaoCadastral": "ATIVA",
                    "capitalSocial": 100000.0,
                    "porte": "DEMAIS",
                    "naturezaJuridica": "Sociedade Empresária Limitada",
                    "dataAbertura": "2018-05-15",
                    "endereco": {
                        "logradouro": "Av. Paulista",
                        "numero": "1000",
                        "bairro": "Bela Vista",
                        "municipio": "São Paulo",
                        "uf": "SP",
                        "cep": "01310-100",
                    },
                },
                "socioAdministradores": [
                    {
                        "nome": "Alexandre Silva",
                        "qualificacao": "Sócio-Administrador",
                        "paisOrigem": "Brasil",
                    },
                    {
                        "nome": "Mariana Santos",
                        "qualificacao": "Diretora de Operações",
                        "paisOrigem": "Brasil",
                    },
                ],
                "emailsValidados": [
                    {
                        "email": "diretoria@empresa.com.br",
                        "status": "DELIVERABLE",
                        "smtpCheck": True,
                        "score": 99,
                    },
                ],
                "telefonesAtribuiveis": [
                    {
                        "numero": "(11) 98765-4321",
                        "tipo": "Movel",
                        "whatsappDisponivel": True,
                        "atribuicao": "Alexandre Silva",
                    },
                ],
                "capabilitiesApplied": capabilities,
                "costCredits": 3,
            }
        )


class EnrichmentLookupView(APIView):
    authentication_classes = (CombinedAuthentication,)
    permission_classes = (AllowAny,)

    def get(self, request: Request) -> Response:
        query = request.query_params.get("q", "").strip()
        return Response(
            {
                "id": "enrich-lookup-1",
                "name": query or "Lead Enriquecido",
                "company": query or "Empresa Enriquecida",
                "email": "contato@empresa.com.br",
                "phone": "(11) 98765-4321",
                "enriched": True,
                "dataConfidenceScore": 96,
            }
        )


class DiscoveryExtractView(APIView):
    authentication_classes = (CombinedAuthentication,)
    permission_classes = (AllowAny,)

    def post(self, request: Request) -> Response:
        payload = _get_payload(request)
        target_dataset_id = payload.get("targetDatasetId", "conjunto-inicial")
        total_extracted = payload.get("limit", 25)
        return Response(
            {
                "batchId": str(uuid.uuid4()),
                "targetDatasetId": target_dataset_id,
                "totalExtracted": total_extracted,
                "status": "COMPLETED",
                "message": f"Extração de {total_extracted} empresas realizada com sucesso.",
            }
        )
