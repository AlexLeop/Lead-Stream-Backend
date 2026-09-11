from __future__ import annotations

from uuid import UUID

from django.http import Http404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from leadstream.batches.models import BatchItem
from leadstream.canonical.builder import CanonicalLeadBuilder
from leadstream.canonical.contracts import CanonicalLeadPayload
from leadstream.tenancy.models import Tenant
from leadstream.tenancy.services import get_internal_tenant


def resolve_request_tenant(request: Request) -> Tenant:
    tenant_header = request.headers.get("X-Tenant-Id") or request.META.get("HTTP_X_TENANT_ID")
    if tenant_header:
        try:
            return Tenant.objects.get(slug=tenant_header, is_active=True)
        except Tenant.DoesNotExist:
            try:
                return Tenant.objects.get(pk=tenant_header, is_active=True)
            except (Tenant.DoesNotExist, ValueError):
                pass
    return get_internal_tenant()


class CanonicalLeadDetailView(APIView):
    @extend_schema(
        summary="Consulta do Lead Canônico Consolidado (v2.4.0)",
        description=(
            "Retorna a estrutura canônica completa e higienizada de um lead processado.\n\n"
            "O payload canônico consolida até 14 blocos de inteligência de dados B2B:\n"
            "- **_meta**: Identificador canônico, timestamp ISO 8601, tenant e score global de confiança.\n"
            "- **identification**: Status de qualificação, lead score (0-100), temperatura (COLD/WARM/HOT), fit com ICP e tags comerciais.\n"
            "- **company**: Dados cadastrais oficiais da Receita Federal (CNPJ, Razão Social, Nome Fantasia, Situação, Natureza Jurídica, Porte Sebrae, Regime Tributário, Capital Social, Faturamento Estimado, Faixa de Funcionários e Domínio Web).\n"
            "- **financial_and_banking**: Detecção de instituições bancárias de relacionamento (ex: Nu Pagamentos/Nubank, Itaú, Bradesco), linhas de crédito, score de crédito e protestos.\n"
            "- **fiscal_and_tax_intelligence**: Regularidade fiscal federal, certidões CND/PGFN, regularidade FGTS/CRF e Inscrição Estadual (SINTEGRA) e Municipal.\n"
            "- **cnae**: CNAE Principal (com setor econômico e grau de risco de trabalho) e lista completa de CNAEs secundários.\n"
            "- **address**: Endereço oficial higienizado (tipo de logradouro, logradouro, número, complemento, bairro, município, UF, CEP com máscara, código IBGE e precisão do georreferenciamento).\n"
            "- **contacts**: Canais diretos da empresa com validação técnica: telefones com DDD separado e dígitos limpos (sem caracteres especiais ou espaços, operadora e status WhatsApp) e e-mails com verificação sintática, MX e descarte.\n"
            "- **decision_makers_qsa**: Quadro de Sócios e Administradores (QSA) enriquecido com cargos executivos de mercado, contatos diretos (e-mail corporativo, celular/WhatsApp com DDD separado e dígitos limpos) e link do perfil LinkedIn público verificado (sem subdomínios ou sufixos de país).\n"
            "- **foreign_trade_and_logistics**: Habilitação Radar SISCOMEX, histórico de importação/exportação e frota de veículos cadastrada.\n"
            "- **legal_and_judicial**: Contagem de processos (cíveis, trabalhistas, fiscais), índice de judicialização e certidões negativas de trabalho escravo.\n"
            "- **digital_presence_and_tech_stack**: Tecnologias detectadas, redes sociais oficiais e certificados SSL.\n"
            "- **governance_lgpd_and_compliance**: Enquadramento na LGPD (art. 7º IX - Legítimo Interesse para prospecção B2B comercial), canal de opt-out e política de retenção.\n"
            "- **crm_outbox_integration**: Histórico e status de sincronização com CRMs e outbox transacional com idempotência."
        ),
        parameters=[
            OpenApiParameter(
                name="item_id",
                type=UUID,
                location=OpenApiParameter.PATH,
                description="Identificador UUID do item de lote (lead).",
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=CanonicalLeadPayload,
                description="Payload Canônico v2.4.0 consolidado com sucesso.",
            ),
            404: OpenApiResponse(
                description="Lead não encontrado para o workspace (tenant) autenticado.",
            ),
        },
        tags=["Leads Canônicos"],
    )
    def get(self, request: Request, item_id: UUID) -> Response:
        tenant = resolve_request_tenant(request)
        try:
            item = BatchItem.objects.get(pk=item_id, tenant=tenant)
        except BatchItem.DoesNotExist as exc:
            raise Http404("Lead não encontrado.") from exc

        if item.canonical_payload and item.canonical_payload.get("_meta"):
            return Response(item.canonical_payload, status=status.HTTP_200_OK)

        builder = CanonicalLeadBuilder(tenant=tenant)
        payload = builder.build_and_save(item)
        return Response(payload, status=status.HTTP_200_OK)
