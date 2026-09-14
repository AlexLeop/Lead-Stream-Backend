from __future__ import annotations

from typing import Any
from uuid import UUID

from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from leadstream.batches.models import Batch
from leadstream.common.api import resolve_tenant
from leadstream.security.permissions import IsTenantMember, IsWorkspaceAdmin

from .models import CRMConnection, CRMFieldMapping, CRMOutboxMessage, OutboxStatus
from .serializers import (
    AdminCRMOverviewResponseSerializer,
    CRMConnectionSerializer,
    CRMFieldMappingSerializer,
    CRMOutboxMessageSerializer,
    CRMOutboxRetryDeadLetterRequestSerializer,
    CRMOutboxRetryDeadLetterResponseSerializer,
    CRMOutboxStatusResponseSerializer,
    CRMSyncRequestSerializer,
    CRMTestConnectionResponseSerializer,
)
from .services import verify_crm_connection
from .tasks import process_crm_outbox_batch, sync_batch_to_crm_task


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


@extend_schema(
    tags=["Integrações - Outbox"],
    summary="Status e Métricas da Fila de Outbox do Tenant",
    responses={200: CRMOutboxStatusResponseSerializer},
)
class CRMOutboxStatusView(APIView):
    """Retorna métricas em tempo real sobre mensagens pendentes, entregues e falhas no Outbox."""

    permission_classes = (IsAuthenticated, IsTenantMember)

    def get(self, request: Request) -> Response:
        tenant = resolve_tenant(request)
        messages_qs = CRMOutboxMessage.objects.filter(tenant=tenant)

        counts_dict = dict(
            messages_qs.values("status").annotate(total=Count("id")).values_list("status", "total")
        )
        pending = counts_dict.get(OutboxStatus.PENDING, 0)
        processing = counts_dict.get(OutboxStatus.PROCESSING, 0)
        delivered = counts_dict.get(OutboxStatus.DELIVERED, 0)
        failed = counts_dict.get(OutboxStatus.FAILED, 0)
        dead_letter = counts_dict.get(OutboxStatus.DEAD_LETTER, 0)

        oldest_pending = (
            messages_qs.filter(status=OutboxStatus.PENDING)
            .order_by("created_at")
            .values_list("created_at", flat=True)
            .first()
        )
        oldest_pending_seconds = None
        if oldest_pending:
            oldest_pending_seconds = int((timezone.now() - oldest_pending).total_seconds())

        is_healthy = dead_letter == 0 and (
            oldest_pending_seconds is None or oldest_pending_seconds < 3600
        )

        return Response(
            {
                "tenant_id": str(tenant.id),
                "counts": {
                    "pending": pending,
                    "processing": processing,
                    "delivered": delivered,
                    "failed": failed,
                    "dead_letter": dead_letter,
                },
                "oldest_pending_seconds": oldest_pending_seconds,
                "is_healthy": is_healthy,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["Integrações - Outbox"],
    summary="Reprocessar Mensagens em Dead-Letter",
    request=CRMOutboxRetryDeadLetterRequestSerializer,
    responses={200: CRMOutboxRetryDeadLetterResponseSerializer},
)
class CRMOutboxRetryDeadLetterView(APIView):
    """Retorna mensagens em falha definitiva (Dead-Letter) para a fila de envio pendente."""

    permission_classes = (IsAuthenticated, IsTenantMember, IsWorkspaceAdmin)

    def post(self, request: Request) -> Response:
        tenant = resolve_tenant(request)
        message_ids = request.data.get("message_ids") if isinstance(request.data, dict) else None

        qs = CRMOutboxMessage.objects.filter(tenant=tenant, status=OutboxStatus.DEAD_LETTER)
        if message_ids:
            qs = qs.filter(id__in=message_ids)

        now = timezone.now()
        retried_count = qs.update(
            status=OutboxStatus.PENDING,
            retry_count=0,
            next_retry_at=now,
            error_code="",
            error_message="",
            updated_at=now,
        )

        if retried_count > 0:
            process_crm_outbox_batch.delay()

        return Response(
            {
                "retried_count": retried_count,
                "message": (
                    f"{retried_count} mensagens de dead-letter retornaram para a fila pendente."
                ),
            },
            status=status.HTTP_200_OK,
        )
