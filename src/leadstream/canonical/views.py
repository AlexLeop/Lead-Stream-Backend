from __future__ import annotations

from uuid import UUID

from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from leadstream.batches.models import BatchItem
from leadstream.canonical.builder import CanonicalLeadBuilder
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
        summary="Consulta do Lead Canônico",
        description=(
            "Retorna o payload canônico v2.4.0 consolidado com todas as seções e "
            "inteligência do lead."
        ),
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
