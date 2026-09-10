from __future__ import annotations

from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Avg, Count, Sum
from django.http import Http404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from leadstream.batches.models import Batch
from leadstream.batches.serializers import BatchSerializer
from leadstream.billing.models import ProviderCall
from leadstream.common.api import reject_tenant_override
from leadstream.common.pagination import DiscoveryCursorPagination, StandardPagination
from leadstream.tenancy.services import get_internal_tenant

from .discovery import create_discovery_batch, create_discovery_search
from .exceptions import ProviderNotConfigured
from .models import DiscoverySearch, ProviderPolicy
from .orchestrator import DEFAULT_BLOCKS
from .pipeline import start_batch_enrichment
from .registry import default_adapters, ensure_provider_policies
from .serializers import (
    DiscoveryCreateSerializer,
    DiscoveryMaterializeSerializer,
    DiscoveryResultSerializer,
    DiscoverySearchSerializer,
    EnrichmentStartSerializer,
    ProviderMetricSerializer,
    ProviderPolicySerializer,
)


def _domain_error(exc: DjangoValidationError) -> ValidationError:
    if hasattr(exc, "message_dict"):
        return ValidationError(exc.message_dict)
    return ValidationError({"erro": exc.messages})


class ProviderUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_code = "provider_not_configured"
    default_detail = "O provedor necessário não está configurado."


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


def _get_discovery(search_id: UUID) -> DiscoverySearch:
    try:
        return DiscoverySearch.objects.get(pk=search_id, tenant=get_internal_tenant())
    except DiscoverySearch.DoesNotExist as exc:
        raise Http404("Descoberta não encontrada.") from exc


class DiscoveryCollectionView(APIView):
    @extend_schema(responses=DiscoverySearchSerializer(many=True), tags=["Descoberta"])
    def get(self, request: Request) -> Response:
        queryset = DiscoverySearch.objects.filter(tenant=get_internal_tenant())
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(DiscoverySearchSerializer(page, many=True).data)

    @extend_schema(
        request=DiscoveryCreateSerializer,
        responses={200: DiscoverySearchSerializer, 202: DiscoverySearchSerializer},
        parameters=[
            OpenApiParameter(
                "Idempotency-Key",
                str,
                location=OpenApiParameter.HEADER,
                required=True,
                description="Chave estável da descoberta.",
            )
        ],
        tags=["Descoberta"],
    )
    def post(self, request: Request) -> Response:
        reject_tenant_override(request.data)
        serializer = DiscoveryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            result = create_discovery_search(
                tenant=get_internal_tenant(),
                name=data.get("name", ""),
                filters=data["filters"],
                idempotency_key=request.headers.get("Idempotency-Key", ""),
                max_results=data["max_results"],
                query_page_size=data["query_page_size"],
            )
        except ProviderNotConfigured as exc:
            raise ProviderUnavailable(str(exc)) from exc
        except DjangoValidationError as exc:
            raise _domain_error(exc) from exc
        response_status = status.HTTP_202_ACCEPTED if result.created else status.HTTP_200_OK
        return Response(DiscoverySearchSerializer(result.search).data, status=response_status)


class DiscoveryDetailView(APIView):
    @extend_schema(responses=DiscoverySearchSerializer, tags=["Descoberta"])
    def get(self, request: Request, search_id: UUID) -> Response:
        del request
        return Response(DiscoverySearchSerializer(_get_discovery(search_id)).data)


class DiscoveryResultsView(APIView):
    @extend_schema(responses=DiscoveryResultSerializer(many=True), tags=["Descoberta"])
    def get(self, request: Request, search_id: UUID) -> Response:
        search = _get_discovery(search_id)
        queryset = search.results.filter(tenant=search.tenant).order_by("rank", "id")
        paginator = DiscoveryCursorPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(DiscoveryResultSerializer(page, many=True).data)


class DiscoveryMaterializeView(APIView):
    @extend_schema(
        request=DiscoveryMaterializeSerializer,
        responses={200: BatchSerializer, 202: BatchSerializer},
        parameters=[
            OpenApiParameter(
                "Idempotency-Key",
                str,
                location=OpenApiParameter.HEADER,
                required=True,
                description="Chave estável da materialização.",
            )
        ],
        tags=["Descoberta"],
    )
    def post(self, request: Request, search_id: UUID) -> Response:
        reject_tenant_override(request.data)
        serializer = DiscoveryMaterializeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        tenant = get_internal_tenant()
        existing = Batch.objects.filter(
            tenant=tenant,
            idempotency_key=request.headers.get("Idempotency-Key", "").strip(),
        ).first()
        try:
            batch = create_discovery_batch(
                tenant=tenant,
                search_id=search_id,
                name=data.get("name", ""),
                idempotency_key=request.headers.get("Idempotency-Key", ""),
                chunk_size=data["chunk_size"],
                result_ids=data.get("result_ids"),
            )
        except DiscoverySearch.DoesNotExist as exc:
            raise Http404("Descoberta não encontrada.") from exc
        except DjangoValidationError as exc:
            raise _domain_error(exc) from exc
        return Response(
            BatchSerializer(batch).data,
            status=status.HTTP_200_OK if existing else status.HTTP_202_ACCEPTED,
        )
