from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any, Literal, cast

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from leadstream.batches.models import Batch, BatchItem
from leadstream.common.api import resolve_tenant
from leadstream.security.authentication import ApiKeyUser, CombinedAuthentication
from leadstream.security.crypto import generate_api_key
from leadstream.security.models import APIKey, SecurityAuditLog, WorkspaceMembership, WorkspaceRole
from leadstream.security.permissions import IsTenantMember, IsWorkspaceAdmin
from leadstream.security.serializers import (
    APIKeyCreatedResponseSerializer,
    APIKeyCreateSerializer,
    APIKeyReadSerializer,
    AuthMeResponseSerializer,
    SecurityAuditLogSerializer,
    SwitchWorkspaceSerializer,
    TokenRevokeSerializer,
)
from leadstream.security.throttling import AuthRateThrottle, AuthRefreshRateThrottle
from leadstream.tenancy.models import Tenant

CookieSameSite = Literal["Lax", "Strict", "None", False]


def _set_refresh_cookie(response: Response, raw_refresh: str) -> None:
    refresh_lifetime = settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]
    if not isinstance(refresh_lifetime, timedelta):
        raise TypeError("REFRESH_TOKEN_LIFETIME deve ser um timedelta.")
    same_site = cast(CookieSameSite, settings.AUTH_COOKIE_SAMESITE)
    if same_site not in {"Lax", "Strict", "None", False, None}:
        raise ValueError("AUTH_COOKIE_SAMESITE inválido.")
    response.set_cookie(
        key=settings.AUTH_REFRESH_COOKIE_NAME,
        value=raw_refresh,
        max_age=int(refresh_lifetime.total_seconds()),
        secure=settings.AUTH_COOKIE_SECURE,
        httponly=True,
        samesite=same_site,
        domain=settings.AUTH_COOKIE_DOMAIN,
        path=settings.AUTH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    same_site = cast(CookieSameSite, settings.AUTH_COOKIE_SAMESITE)
    response.delete_cookie(
        key=settings.AUTH_REFRESH_COOKIE_NAME,
        samesite=same_site,
        domain=settings.AUTH_COOKIE_DOMAIN,
        path=settings.AUTH_COOKIE_PATH,
    )


def get_client_ip(request: Request) -> str | None:
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if isinstance(x_forwarded_for, str) and x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    remote_addr = request.META.get("REMOTE_ADDR")
    if isinstance(remote_addr, str) and remote_addr:
        return remote_addr
    return None


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
        username = ""
        if isinstance(request.data, dict):
            username = str(request.data.get("username", ""))

        if response.status_code == status.HTTP_200_OK:
            raw_refresh = response.data.pop("refresh", None)
            if isinstance(raw_refresh, str):
                _set_refresh_cookie(response, raw_refresh)
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

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        request_data = request.data if isinstance(request.data, dict) else {}
        raw_refresh = request_data.get("refresh") or request.COOKIES.get(
            settings.AUTH_REFRESH_COOKIE_NAME
        )
        if not isinstance(raw_refresh, str) or not raw_refresh:
            response = Response(
                {"detail": "Sessão expirada. Faça login novamente."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            _clear_refresh_cookie(response)
            return response

        serializer = self.get_serializer(data={"refresh": raw_refresh})
        serializer.is_valid(raise_exception=True)
        response_data = dict(serializer.validated_data)
        rotated_refresh = response_data.pop("refresh", None)
        response = Response(response_data, status=status.HTTP_200_OK)
        if isinstance(rotated_refresh, str):
            _set_refresh_cookie(response, rotated_refresh)
        return response


@extend_schema(
    tags=["Autenticação"],
    request=TokenRevokeSerializer,
    responses={
        200: OpenApiResponse(description="Token revogado com sucesso."),
        400: OpenApiResponse(description="Token inválido ou já revogado."),
    },
)
class TokenRevokeView(APIView):
    """Revogação e invalidação imediata de um Refresh Token via Blacklist."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request: Request) -> Response:
        serializer = TokenRevokeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw_refresh_value = serializer.validated_data.get("refresh") or request.COOKIES.get(
            settings.AUTH_REFRESH_COOKIE_NAME
        )
        if not isinstance(raw_refresh_value, str) or not raw_refresh_value:
            response = Response(
                {"detail": "Sessão já encerrada."},
                status=status.HTTP_200_OK,
            )
            _clear_refresh_cookie(response)
            return response

        try:
            token = RefreshToken(raw_refresh_value)  # type: ignore[arg-type]
            token.blacklist()
        except TokenError as exc:
            response = Response(
                {"detail": f"Token inválido ou já revogado: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
            _clear_refresh_cookie(response)
            return response

        log_security_event(
            request=request,
            action="TOKEN_REVOKE",
            status_code=status.HTTP_200_OK,
            details={"revoked_at": timezone.now().isoformat()},
        )
        response = Response(
            {"detail": "Token revogado com sucesso."},
            status=status.HTTP_200_OK,
        )
        _clear_refresh_cookie(response)
        return response


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
        tenant = resolve_tenant(request)
        keys = APIKey.objects.filter(tenant=tenant).order_by("-created_at")
        serializer = APIKeyReadSerializer(keys, many=True)
        return Response({"results": serializer.data, "count": keys.count()})

    def post(self, request: Request) -> Response:
        tenant = resolve_tenant(request)
        serializer = APIKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        api_key, raw_key = generate_api_key(
            tenant=tenant,
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
            tenant=tenant,
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
    responses={
        204: OpenApiResponse(description="Chave de API revogada com sucesso."),
        404: OpenApiResponse(description="Chave de API não encontrada."),
    },
)
class APIKeyDetailView(APIView):
    """Revogação de chave de API por ID."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (IsAuthenticated, IsTenantMember, IsWorkspaceAdmin)

    def delete(self, request: Request, pk: uuid.UUID) -> Response:
        tenant = resolve_tenant(request)
        api_key = APIKey.objects.filter(tenant=tenant, pk=pk).first()
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
            tenant=tenant,
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
        tenant = resolve_tenant(request)
        logs = SecurityAuditLog.objects.filter(tenant=tenant).order_by("-timestamp")
        serializer = SecurityAuditLogSerializer(logs[:200], many=True)
        return Response({"results": serializer.data, "count": logs.count()})


ROLE_PERMISSIONS: dict[str, list[str]] = {
    "SUPER_ADMIN": [
        "batches:view",
        "batches:create",
        "batches:export",
        "leads:view",
        "leads:enrich",
        "integrations:manage",
        "security:manage_keys",
        "security:view_audit",
        "workspaces:manage",
    ],
    WorkspaceRole.ADMIN: [
        "batches:view",
        "batches:create",
        "batches:export",
        "leads:view",
        "leads:enrich",
        "integrations:manage",
        "security:manage_keys",
        "security:view_audit",
    ],
    WorkspaceRole.OPERATOR: [
        "batches:view",
        "batches:create",
        "batches:export",
        "leads:view",
        "leads:enrich",
        "integrations:view",
    ],
    WorkspaceRole.READ_ONLY: [
        "batches:view",
        "batches:export",
        "leads:view",
    ],
}


@extend_schema(
    tags=["Autenticação"],
    summary="Consultar Perfil do Usuário e Workspace Ativo",
    responses={200: AuthMeResponseSerializer},
)
class AuthMeView(APIView):
    """Retorna os dados do operador/chave autenticado, perfil, workspace ativo e permissões."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        tenant = resolve_tenant(request)

        if isinstance(request.user, ApiKeyUser):
            role = request.user.role
            permissions = ROLE_PERMISSIONS.get(role, ["batches:view", "leads:view"])
            user_data = {
                "id": str(request.user.api_key.id),
                "username": request.user.username,
                "email": None,
                "first_name": "",
                "last_name": "",
                "is_superuser": False,
                "is_staff": False,
            }
            auth_type = "API_KEY"
            active_workspace_data = {
                "id": tenant.id,
                "name": tenant.name,
                "slug": tenant.slug,
                "role": role,
                "is_owner": False,
                "stats": {
                    "total_batches": Batch.objects.filter(tenant=tenant).count(),
                    "total_leads_processed": BatchItem.objects.filter(batch__tenant=tenant).count(),
                    "active_api_keys": APIKey.objects.filter(tenant=tenant, is_active=True).count(),
                },
            }
            workspaces_list = [
                {
                    "id": tenant.id,
                    "name": tenant.name,
                    "slug": tenant.slug,
                    "role": role,
                    "is_active": tenant.is_active,
                    "is_current": True,
                }
            ]
        else:
            user = request.user
            if not user or not user.is_authenticated:
                return Response({"detail": "Não autenticado."}, status=status.HTTP_401_UNAUTHORIZED)

            is_super = bool(getattr(user, "is_superuser", False))
            user_id = str(user.pk)
            username = getattr(user, "username", "")
            email = getattr(user, "email", None)
            first_name = getattr(user, "first_name", "")
            last_name = getattr(user, "last_name", "")
            is_staff = bool(getattr(user, "is_staff", False))

            if is_super:
                role = "SUPER_ADMIN"
                permissions = ROLE_PERMISSIONS["SUPER_ADMIN"]
                user_data = {
                    "id": user_id,
                    "username": username,
                    "email": email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "is_superuser": True,
                    "is_staff": is_staff,
                }
                auth_type = "JWT"
                all_tenants = Tenant.objects.filter(is_active=True).order_by("name")
                workspaces_list = [
                    {
                        "id": t.id,
                        "name": t.name,
                        "slug": t.slug,
                        "role": "SUPER_ADMIN",
                        "is_active": t.is_active,
                        "is_current": (t.id == tenant.id),
                    }
                    for t in all_tenants
                ]
                active_workspace_data = {
                    "id": tenant.id,
                    "name": tenant.name,
                    "slug": tenant.slug,
                    "role": "SUPER_ADMIN",
                    "is_owner": True,
                    "stats": {
                        "total_batches": Batch.objects.filter(tenant=tenant).count(),
                        "total_leads_processed": BatchItem.objects.filter(
                            batch__tenant=tenant
                        ).count(),
                        "active_api_keys": APIKey.objects.filter(
                            tenant=tenant, is_active=True
                        ).count(),
                    },
                }
            else:
                memberships = (
                    WorkspaceMembership.objects.filter(user_id=user.pk, is_active=True)
                    .select_related("tenant")
                    .order_by("tenant__name")
                )
                current_membership = getattr(request, "workspace_membership", None)
                current_role = (
                    current_membership.role if current_membership else WorkspaceRole.OPERATOR
                )
                permissions = ROLE_PERMISSIONS.get(current_role, ["batches:view", "leads:view"])

                user_data = {
                    "id": user_id,
                    "username": username,
                    "email": email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "is_superuser": False,
                    "is_staff": is_staff,
                }
                auth_type = "JWT"
                workspaces_list = [
                    {
                        "id": m.tenant.id,
                        "name": m.tenant.name,
                        "slug": m.tenant.slug,
                        "role": m.role,
                        "is_active": m.is_active,
                        "is_current": (m.tenant.id == tenant.id),
                    }
                    for m in memberships
                ]
                active_workspace_data = {
                    "id": tenant.id,
                    "name": tenant.name,
                    "slug": tenant.slug,
                    "role": current_role,
                    "is_owner": (current_role == WorkspaceRole.ADMIN),
                    "stats": {
                        "total_batches": Batch.objects.filter(tenant=tenant).count(),
                        "total_leads_processed": BatchItem.objects.filter(
                            batch__tenant=tenant
                        ).count(),
                        "active_api_keys": APIKey.objects.filter(
                            tenant=tenant, is_active=True
                        ).count(),
                    },
                }

        payload = {
            "user": user_data,
            "auth_type": auth_type,
            "active_workspace": active_workspace_data,
            "workspaces": workspaces_list,
            "permissions": permissions,
        }
        return Response(payload, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Autenticação"],
    summary="Alternar Workspace Ativo",
    request=SwitchWorkspaceSerializer,
    responses={
        200: OpenApiResponse(description="Workspace alterado com sucesso."),
        400: OpenApiResponse(description="Dados inválidos ou cliente autenticado via API Key."),
        403: OpenApiResponse(description="Usuário não possui acesso ao workspace informado."),
        404: OpenApiResponse(description="Workspace não encontrado."),
    },
)
class SwitchWorkspaceView(APIView):
    """Permite a operadores autenticados via JWT alternar seu workspace ativo em tempo real."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request: Request) -> Response:
        if isinstance(request.user, ApiKeyUser):
            return Response(
                {"detail": "Chaves de API são fixadas ao seu workspace de emissão."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SwitchWorkspaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        workspace_id = serializer.validated_data.get("workspace_id")
        slug = serializer.validated_data.get("slug")

        if workspace_id:
            target_tenant = Tenant.objects.filter(id=workspace_id, is_active=True).first()
        else:
            target_tenant = Tenant.objects.filter(slug=slug, is_active=True).first()

        if not target_tenant:
            return Response(
                {"detail": "Workspace não encontrado ou inativo."},
                status=status.HTTP_404_NOT_FOUND,
            )

        user = request.user
        if not user or not user.is_authenticated or not isinstance(user, AbstractBaseUser):
            return Response(
                {"detail": "Não autenticado."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if bool(getattr(user, "is_superuser", False)):
            role = "SUPER_ADMIN"
        else:
            membership = WorkspaceMembership.objects.filter(
                user_id=user.pk,
                tenant=target_tenant,
                is_active=True,
            ).first()
            if not membership:
                return Response(
                    {
                        "detail": "Você não possui acesso a este workspace.",
                        "code": "WORKSPACE_ACCESS_DENIED",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            role = membership.role

        refresh = RefreshToken.for_user(user)
        refresh["tenant_id"] = str(target_tenant.id)
        access = refresh.access_token
        access["tenant_id"] = str(target_tenant.id)

        log_security_event(
            request=request,
            action="WORKSPACE_SWITCH",
            status_code=status.HTTP_200_OK,
            tenant=target_tenant,
            details={"target_tenant_id": str(target_tenant.id), "target_slug": target_tenant.slug},
        )

        response = Response(
            {
                "message": f"Workspace alterado para '{target_tenant.name}'.",
                "active_workspace": {
                    "id": str(target_tenant.id),
                    "name": target_tenant.name,
                    "slug": target_tenant.slug,
                    "role": role,
                },
                "access": str(access),
            },
            status=status.HTTP_200_OK,
        )
        _set_refresh_cookie(response, str(refresh))
        return response
