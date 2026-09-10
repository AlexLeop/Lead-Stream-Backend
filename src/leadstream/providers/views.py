from __future__ import annotations

from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Avg, Count, Sum
from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from leadstream.batches.models import Batch
from leadstream.billing.models import ProviderCall
from leadstream.common.api import reject_tenant_override
from leadstream.tenancy.services import get_internal_tenant

from .models import ProviderPolicy
from .orchestrator import DEFAULT_BLOCKS
from .pipeline import start_batch_enrichment
from .registry import default_adapters, ensure_provider_policies
from .serializers import (
    EnrichmentStartSerializer,
    ProviderMetricSerializer,
    ProviderPolicySerializer,
)


def _domain_error(exc: DjangoValidationError) -> ValidationError:
    if hasattr(exc, "message_dict"):
        return ValidationError(exc.message_dict)
    return ValidationError({"erro": exc.messages})


class ProviderPolicyCollectionView(APIView):
    @extend_schema(responses=ProviderPolicySerializer(many=True), tags=["Provedores"])
    def get(self, request: Request) -> Response:
        del request
        tenant = get_internal_tenant()
        ensure_provider_policies(tenant)
        adapters = default_adapters()
        queryset = ProviderPolicy.objects.filter(tenant=tenant).select_related("health")
        return Response(
            ProviderPolicySerializer(queryset, many=True, context={"adapters": adapters}).data
        )


class ProviderPolicyDetailView(APIView):
    @extend_schema(
        request=ProviderPolicySerializer,
        responses=ProviderPolicySerializer,
        tags=["Provedores"],
    )
    def patch(self, request: Request, policy_id: UUID) -> Response:
        reject_tenant_override(request.data)
        tenant = get_internal_tenant()
        try:
            policy = ProviderPolicy.objects.get(pk=policy_id, tenant=tenant)
        except ProviderPolicy.DoesNotExist as exc:
            raise Http404("Política de provedor não encontrada.") from exc
        serializer = ProviderPolicySerializer(
            policy,
            data=request.data,
            partial=True,
            context={"adapters": default_adapters()},
        )
        serializer.is_valid(raise_exception=True)
        try:
            updated = serializer.save()
        except DjangoValidationError as exc:
            raise _domain_error(exc) from exc
        return Response(
            ProviderPolicySerializer(updated, context={"adapters": default_adapters()}).data
        )


class StartBatchEnrichmentView(APIView):
    @extend_schema(
        request=EnrichmentStartSerializer,
        responses={202: None},
        tags=["Enriquecimento"],
    )
    def post(self, request: Request, batch_id: UUID) -> Response:
        reject_tenant_override(request.data)
        serializer = EnrichmentStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        blocks = frozenset(serializer.validated_data.get("blocks", DEFAULT_BLOCKS))
        try:
            batch = start_batch_enrichment(
                tenant=get_internal_tenant(), batch_id=batch_id, requested_blocks=blocks
            )
        except (DjangoValidationError, Batch.DoesNotExist) as exc:
            if isinstance(exc, Batch.DoesNotExist):
                raise Http404("Lote não encontrado.") from exc
            raise _domain_error(exc) from exc
        return Response(
            {"batch_id": str(batch.pk), "status": batch.status, "stage": batch.current_stage},
            status=status.HTTP_202_ACCEPTED,
        )


class ProviderMetricsView(APIView):
    @extend_schema(responses=ProviderMetricSerializer(many=True), tags=["Provedores — métricas"])
    def get(self, request: Request) -> Response:
        del request
        tenant = get_internal_tenant()
        rows = (
            ProviderCall.objects.filter(tenant=tenant)
            .values("provider", "status")
            .annotate(
                calls=Count("id"),
                average_latency_ms=Avg("latency_ms"),
                confirmed_cost_cents=Sum("confirmed_cost_cents"),
            )
            .order_by("provider", "status")
        )
        payload = [
            {
                "provider": row["provider"],
                "provider_status": row["status"],
                "calls": row["calls"],
                "average_latency_ms": row["average_latency_ms"],
                "confirmed_cost_cents": row["confirmed_cost_cents"],
            }
            for row in rows
        ]
        return Response(payload)
