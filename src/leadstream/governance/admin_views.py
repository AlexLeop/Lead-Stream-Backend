from __future__ import annotations

from typing import Any, ClassVar

from rest_framework import serializers, status
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from leadstream.governance.models import Suppression
from leadstream.governance.services import create_suppression
from leadstream.security.authentication import CombinedAuthentication
from leadstream.security.models import SecurityAuditLog
from leadstream.tenancy.models import Tenant


class AdminSuppressionSerializer(serializers.ModelSerializer[Suppression]):
    tenant_slug = serializers.CharField(source="tenant.slug", read_only=True)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)

    class Meta:
        model = Suppression
        fields: ClassVar[list[str]] = [
            "id",
            "tenant_id",
            "tenant_slug",
            "tenant_name",
            "scope",
            "value_digest",
            "key_version",
            "reason",
            "effective_at",
            "expires_at",
            "created_at",
        ]


class AdminSuppressionListView(APIView):
    """Listagem e criação de entradas na lista de supressão (Opt-Out / LGPD)."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (IsAdminUser,)

    def get(self, request: Request) -> Response:
        suppressions = Suppression.objects.all().select_related("tenant").order_by("-created_at")
        tenant_id = request.query_params.get("tenant_id", "").strip()
        if tenant_id:
            suppressions = suppressions.filter(tenant_id=tenant_id)
        serializer = AdminSuppressionSerializer(suppressions, many=True)
        return Response({"results": serializer.data, "count": len(serializer.data)})

    def post(self, request: Request) -> Response:
        payload: dict[str, Any] = request.data if isinstance(request.data, dict) else {}
        tenant_id = payload.get("tenant_id", "").strip()
        scope = payload.get("scope", "").strip().upper()
        value = payload.get("value", "").strip()
        reason = payload.get("reason", "Solicitação do titular").strip()

        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except (Tenant.DoesNotExist, ValueError):
            return Response({"detail": "Tenant não encontrado."}, status=status.HTTP_404_NOT_FOUND)

        if not value:
            return Response(
                {"detail": "O identificador para supressão ('value') é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        suppression = create_suppression(
            tenant=tenant,
            scope=scope,
            value=value,
            reason=reason,
        )
        serializer = AdminSuppressionSerializer(suppression)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminSuppressionDetailView(APIView):
    """Remoção de entrada de supressão."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (IsAdminUser,)

    def delete(self, request: Request, suppression_id: str) -> Response:
        try:
            suppression = Suppression.objects.get(id=suppression_id)
        except (Suppression.DoesNotExist, ValueError):
            return Response(
                {"detail": "Entrada de supressão não encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )

        suppression.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminSecurityAuditLogSerializer(serializers.ModelSerializer[SecurityAuditLog]):
    tenant_slug = serializers.CharField(source="tenant.slug", read_only=True)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)

    class Meta:
        model = SecurityAuditLog
        fields: ClassVar[list[str]] = [
            "id",
            "timestamp",
            "tenant_id",
            "tenant_slug",
            "tenant_name",
            "actor_type",
            "actor_id",
            "ip_address",
            "action",
            "resource_accessed",
            "status_code",
            "details",
        ]


class AdminAuditLogsView(APIView):
    """Consulta estruturada aos logs imutáveis de segurança e governança."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (IsAdminUser,)

    def get(self, request: Request) -> Response:
        logs = SecurityAuditLog.objects.all().select_related("tenant").order_by("-timestamp")[:100]
        serializer = AdminSecurityAuditLogSerializer(logs, many=True)
        return Response({"results": serializer.data, "count": len(serializer.data)})
