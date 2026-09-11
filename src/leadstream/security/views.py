from __future__ import annotations

import uuid
from typing import Any

from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from leadstream.security.authentication import ApiKeyUser, CombinedAuthentication
from leadstream.security.crypto import generate_api_key
from leadstream.security.models import APIKey, SecurityAuditLog
from leadstream.security.permissions import IsTenantMember, IsWorkspaceAdmin
from leadstream.security.serializers import (
    APIKeyCreatedResponseSerializer,
    APIKeyCreateSerializer,
    APIKeyReadSerializer,
    SecurityAuditLogSerializer,
    TokenRevokeSerializer,
)
from leadstream.security.throttling import AuthRateThrottle, AuthRefreshRateThrottle
from leadstream.tenancy.models import Tenant


def get_client_ip(request: Request) -> str | None:
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_security_event(
    request: Request,
    action: str,
    status_code: int,
    tenant: Tenant | None = None,
    actor_type: str | None = None,
    actor_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> SecurityAuditLog:
    if tenant is None:
        tenant = getattr(request, "tenant", None)

    if actor_type is None:
        if getattr(request.user, "is_superuser", False):
            actor_type = "SUPERADMIN"
            actor_id = str(request.user.pk)
        elif isinstance(request.user, ApiKeyUser):
            actor_type = "API_KEY"
            actor_id = str(request.user.pk)
        elif request.user and request.user.is_authenticated:
            actor_type = "USER"
            actor_id = str(request.user.pk)
        else:
            actor_type = "ANONYMOUS"
            actor_id = ""

    return SecurityAuditLog.objects.create(
        tenant=tenant,
        actor_type=actor_type,
        actor_id=actor_id or "",
        ip_address=get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
        action=action,
        resource_accessed=request.path[:255],
        status_code=status_code,
        details=details or {},
    )


@extend_schema(tags=["Autenticação"])
class TokenObtainPairAuditView(TokenObtainPairView):
    """Emissão de pares de tokens JWT (Access & Refresh) para operadores e administradores."""

    throttle_classes = (AuthRateThrottle,)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        response = super().post(request, *args, **kwargs)
        username = request.data.get("username", "")

        if response.status_code == status.HTTP_200_OK:
            log_security_event(
                request=request,
                action="LOGIN_SUCCESS",
                status_code=response.status_code,
                details={"username": username, "method": "PASSWORD"},
            )
        else:
            log_security_event(
                request=request,
                action="LOGIN_FAILURE",
                status_code=response.status_code,
                details={"username": username, "method": "PASSWORD"},
            )
        return response


@extend_schema(tags=["Autenticação"])
class TokenRefreshAuditView(TokenRefreshView):
    """Renovação de Access Token através de um Refresh Token válido."""

    throttle_classes = (AuthRefreshRateThrottle,)


@extend_schema(
    tags=["Autenticação"],
    request=TokenRevokeSerializer,
    responses={200: dict, 400: dict},
)
class TokenRevokeView(APIView):
    """Revogação e invalidação imediata de um Refresh Token via Blacklist."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request: Request) -> Response:
        serializer = TokenRevokeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw_refresh = serializer.validated_data["refresh"]

        try:
            token = RefreshToken(raw_refresh)
            token.blacklist()
        except TokenError as exc:
            return Response(
                {"detail": f"Token inválido ou já revogado: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        log_security_event(
            request=request,
            action="TOKEN_REVOKE",
            status_code=status.HTTP_200_OK,
            details={"revoked_at": timezone.now().isoformat()},
        )
        return Response(
            {"detail": "Token revogado com sucesso."},
            status=status.HTTP_200_OK,
        )


@extend_schema_view(
    get=extend_schema(
        tags=["Segurança & Chaves"],
        summary="Listar Chaves de API do Workspace",
        responses={200: APIKeyReadSerializer(many=True)},
    ),
    post=extend_schema(
        tags=["Segurança & Chaves"],
        summary="Criar Nova Chave de API",
        request=APIKeyCreateSerializer,
        responses={201: APIKeyCreatedResponseSerializer},
    ),
)
class APIKeyListCreateView(APIView):
    """Gestão de chaves criptográficas de integração vinculadas ao workspace."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (IsAuthenticated, IsTenantMember, IsWorkspaceAdmin)

    def get(self, request: Request) -> Response:
        tenant = request.tenant
        keys = APIKey.objects.filter(tenant=tenant).order_by("-created_at")
        serializer = APIKeyReadSerializer(keys, many=True)
        return Response({"results": serializer.data, "count": keys.count()})

    def post(self, request: Request) -> Response:
        serializer = APIKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        api_key, raw_key = generate_api_key(
            tenant=request.tenant,
            name=data["name"],
            role=data.get("role", "OPERATOR"),
            env=data.get("env", "live"),
            scopes=data.get("scopes", []),
            expires_at=data.get("expires_at"),
        )

        log_security_event(
            request=request,
            action="KEY_CREATE",
            status_code=status.HTTP_201_CREATED,
            tenant=request.tenant,
            details={
                "key_id": str(api_key.id),
                "name": api_key.name,
                "prefix": api_key.prefix,
                "role": api_key.role,
            },
        )

        response_data = APIKeyReadSerializer(api_key).data
        response_data["raw_key"] = raw_key
        response_data["notice"] = (
            "Guarde esta chave em local seguro. Ela não poderá ser visualizada novamente."
        )
        return Response(response_data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["Segurança & Chaves"],
    summary="Revogar Chave de API",
    responses={204: None, 404: dict},
)
class APIKeyDetailView(APIView):
    """Revogação de chave de API por ID."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (IsAuthenticated, IsTenantMember, IsWorkspaceAdmin)

    def delete(self, request: Request, pk: uuid.UUID) -> Response:
        api_key = APIKey.objects.filter(tenant=request.tenant, pk=pk).first()
        if not api_key:
            return Response(
                {"detail": "Chave de API não encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )

        api_key.is_active = False
        api_key.save(update_fields=["is_active"])

        log_security_event(
            request=request,
            action="KEY_REVOKE",
            status_code=status.HTTP_204_NO_CONTENT,
            tenant=request.tenant,
            details={"key_id": str(api_key.id), "name": api_key.name},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=["Segurança & Chaves"],
    summary="Listar Trilha de Auditoria de Segurança",
    responses={200: SecurityAuditLogSerializer(many=True)},
)
class SecurityAuditLogListView(APIView):
    """Consulta aos logs imutáveis de auditoria de segurança e acessos ao workspace."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (IsAuthenticated, IsTenantMember, IsWorkspaceAdmin)

    def get(self, request: Request) -> Response:
        logs = SecurityAuditLog.objects.filter(tenant=request.tenant).order_by("-timestamp")
        serializer = SecurityAuditLogSerializer(logs[:200], many=True)
        return Response({"results": serializer.data, "count": logs.count()})
