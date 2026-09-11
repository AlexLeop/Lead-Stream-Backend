from __future__ import annotations

from typing import Any
from uuid import UUID

from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from leadstream.batches.models import Batch
from leadstream.tenancy.models import Tenant
from leadstream.tenancy.services import get_internal_tenant

from .models import CRMConnection, CRMFieldMapping, CRMOutboxMessage
from .serializers import (
    AdminCRMOverviewResponseSerializer,
    CRMConnectionSerializer,
    CRMFieldMappingSerializer,
    CRMOutboxMessageSerializer,
    CRMSyncRequestSerializer,
    CRMTestConnectionResponseSerializer,
)
from .services import verify_crm_connection
from .tasks import sync_batch_to_crm_task


def resolve_tenant(request: Request | None) -> Tenant:
    """Extrai o tenant do cabeçalho X-Tenant-ID ou recorre ao tenant padrão interno."""
    if request is None or not hasattr(request, "headers"):
        return get_internal_tenant()
    tenant_header = request.headers.get("X-Tenant-ID")
    if tenant_header:
        try:
            return Tenant.objects.get(id=UUID(tenant_header))
        except (Tenant.DoesNotExist, ValueError) as exc:
            raise Http404("Tenant não encontrado.") from exc
    return get_internal_tenant()


@extend_schema(tags=["Integrações - Conexões CRM"])
class CRMConnectionListCreateView(generics.ListCreateAPIView[CRMConnection]):
    serializer_class = CRMConnectionSerializer

    def get_queryset(self) -> Any:
        if getattr(self, "swagger_fake_view", False):
            return CRMConnection.objects.none()
        return CRMConnection.objects.filter(tenant=resolve_tenant(self.request))

    def perform_create(self, serializer: Any) -> None:
        serializer.save(tenant=resolve_tenant(self.request))


@extend_schema(tags=["Integrações - Conexões CRM"])
class CRMConnectionDetailView(generics.RetrieveUpdateDestroyAPIView[CRMConnection]):
    serializer_class = CRMConnectionSerializer

    def get_queryset(self) -> Any:
        if getattr(self, "swagger_fake_view", False):
            return CRMConnection.objects.none()
        return CRMConnection.objects.filter(tenant=resolve_tenant(self.request))


@extend_schema(
    tags=["Integrações - Conexões CRM"],
    request=None,
    responses={200: CRMTestConnectionResponseSerializer, 400: CRMTestConnectionResponseSerializer},
)
class CRMConnectionTestView(APIView):
    def post(self, request: Request, pk: UUID) -> Response:
        tenant = resolve_tenant(request)
        connection = get_object_or_404(CRMConnection, pk=pk, tenant=tenant)
        result = verify_crm_connection(connection)
        serializer = CRMTestConnectionResponseSerializer(
            {
                "success": result.success,
                "message": result.message,
                "latency_ms": result.latency_ms,
                "remote_account_info": result.remote_account_info,
            }
        )
        http_status = status.HTTP_200_OK if result.success else status.HTTP_400_BAD_REQUEST
        return Response(serializer.data, status=http_status)


@extend_schema(tags=["Integrações - Mapeamento de Campos"])
class CRMFieldMappingListCreateView(generics.ListCreateAPIView[CRMFieldMapping]):
    serializer_class = CRMFieldMappingSerializer

    def get_queryset(self) -> Any:
        if getattr(self, "swagger_fake_view", False):
            return CRMFieldMapping.objects.none()
        conn_id = self.kwargs["connection_id"]
        tenant = resolve_tenant(self.request)
        return CRMFieldMapping.objects.filter(
            connection_id=conn_id,
            tenant=tenant,
        )

    def perform_create(self, serializer: Any) -> None:
        conn_id = self.kwargs["connection_id"]
        tenant = resolve_tenant(self.request)
        connection = get_object_or_404(CRMConnection, pk=conn_id, tenant=tenant)
        serializer.save(tenant=tenant, connection=connection)


@extend_schema(tags=["Integrações - Mapeamento de Campos"])
class CRMFieldMappingDetailView(generics.RetrieveUpdateDestroyAPIView[CRMFieldMapping]):
    serializer_class = CRMFieldMappingSerializer

    def get_queryset(self) -> Any:
        if getattr(self, "swagger_fake_view", False):
            return CRMFieldMapping.objects.none()
        conn_id = self.kwargs["connection_id"]
        tenant = resolve_tenant(self.request)
        return CRMFieldMapping.objects.filter(
            connection_id=conn_id,
            tenant=tenant,
        )


@extend_schema(tags=["Integrações - Outbox Transacional"])
class CRMOutboxMessageListView(generics.ListAPIView[CRMOutboxMessage]):
    serializer_class = CRMOutboxMessageSerializer

    def get_queryset(self) -> Any:
        if getattr(self, "swagger_fake_view", False):
            return CRMOutboxMessage.objects.none()
        conn_id = self.kwargs["connection_id"]
        tenant = resolve_tenant(self.request)
        return CRMOutboxMessage.objects.filter(
            connection_id=conn_id,
            tenant=tenant,
        ).order_by("-created_at")


@extend_schema(
    tags=["Integrações - Disparo para CRM"],
    request=CRMSyncRequestSerializer,
    responses={202: None},
)
class BatchSyncToCRMView(APIView):
    def post(self, request: Request, batch_id: UUID) -> Response:
        tenant = resolve_tenant(request)
        batch = get_object_or_404(Batch, pk=batch_id, tenant=tenant)
        serializer = CRMSyncRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        conn_id = serializer.validated_data["connection_id"]
        connection = get_object_or_404(CRMConnection, pk=conn_id, tenant=tenant)

        sync_batch_to_crm_task.delay(
            batch_id=str(batch.id),
            connection_id=str(connection.id),
            selected_statuses=serializer.validated_data.get("statuses"),
            lead_level=serializer.validated_data.get("lead_level", "DECISION_MAKER"),
        )

        return Response(
            {
                "status": "QUEUED",
                "batch_id": str(batch.id),
                "connection_id": str(connection.id),
                "connection_name": connection.name,
                "message": "Sincronização com o CRM iniciada via Outbox transacional.",
            },
            status=status.HTTP_202_ACCEPTED,
        )


@extend_schema(
    tags=["Cockpit do CEO - Métricas de Integrações"],
    responses={200: AdminCRMOverviewResponseSerializer},
)
class AdminCRMOverviewView(APIView):
    """Cockpit do CEO: Métricas globais de integrações e entregas de CRM."""

    def get(self, request: Request) -> Response:
        status_counts = dict(
            CRMOutboxMessage.objects.values("status")
            .annotate(total=Count("id"))
            .values_list("status", "total")
        )
        connector_counts = dict(
            CRMConnection.objects.values("connector_type")
            .annotate(total=Count("id"))
            .values_list("connector_type", "total")
        )

        total_delivered = status_counts.get("DELIVERED", 0)
        total_failed = status_counts.get("FAILED", 0) + status_counts.get("DEAD_LETTER", 0)
        total_all = sum(status_counts.values())
        success_rate = (total_delivered / total_all * 100.0) if total_all > 0 else 100.0

        return Response(
            {
                "outbox_status_summary": status_counts,
                "active_connectors_summary": connector_counts,
                "total_messages": total_all,
                "total_delivered": total_delivered,
                "total_failed": total_failed,
                "global_success_rate_percent": round(success_rate, 2),
            },
            status=status.HTTP_200_OK,
        )
