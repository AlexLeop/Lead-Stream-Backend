from __future__ import annotations

import uuid
from typing import Any

from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request
from rest_framework_simplejwt.authentication import JWTAuthentication

from leadstream.security.crypto import hash_api_key
from leadstream.security.models import APIKey, WorkspaceMembership
from leadstream.tenancy.models import Tenant


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError):
        return False


class ApiKeyUser:
    """Entidade sintética que representa uma chave de API autenticada."""

    is_authenticated = True
    is_anonymous = False
    is_active = True
    is_staff = False
    is_superuser = False

    def __init__(self, api_key: APIKey) -> None:
        self.api_key = api_key
        self.tenant = api_key.tenant
        self.role = api_key.role
        self.pk = api_key.pk
        self.username = f"apikey:{api_key.name}"

    def __str__(self) -> str:
        return self.username

    def get_username(self) -> str:
        return self.username


class CombinedAuthentication(BaseAuthentication):
    """Autenticador híbrido que processa API Keys (Bearer / X-API-Key) e JWT Tokens.
    
    Injeta com precisão request.tenant e request.workspace_membership no contexto HTTP.
    """

    def authenticate_header(self, request: Request) -> str:
        return "Bearer"

    def authenticate(self, request: Request) -> tuple[Any, Any] | None:
        x_api_key = request.headers.get("X-API-Key")
        if x_api_key:
            return self._authenticate_api_key(request, x_api_key)

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None

        parts = auth_header.strip().split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None

        token = parts[1]
        if token.startswith("ls_live_") or token.startswith("ls_test_"):
            return self._authenticate_api_key(request, token)

        return self._authenticate_jwt(request, token)

    def _authenticate_api_key(self, request: Request, raw_key: str) -> tuple[ApiKeyUser, APIKey]:
        hashed = hash_api_key(raw_key)
        api_key = (
            APIKey.objects.filter(hashed_key=hashed, is_active=True)
            .select_related("tenant")
            .first()
        )
        if not api_key:
            raise AuthenticationFailed("API Key inválida ou inativa.")

        if api_key.expires_at and api_key.expires_at <= timezone.now():
            raise AuthenticationFailed("API Key expirada.")

        # Atualizacao do registro temporal de ultimo uso
        APIKey.objects.filter(pk=api_key.pk).update(last_used_at=timezone.now())
        api_key.last_used_at = timezone.now()

        tenant_header = request.headers.get("X-Tenant-ID")
        from leadstream.security.models import WorkspaceRole
        from leadstream.tenancy.services import INTERNAL_TENANT_SLUG

        if (
            api_key.tenant.slug == INTERNAL_TENANT_SLUG
            and api_key.role == WorkspaceRole.ADMIN
            and tenant_header
        ):
            try:
                if _is_uuid(tenant_header):
                    target_tenant = Tenant.objects.get(id=tenant_header, is_active=True)
                else:
                    target_tenant = Tenant.objects.get(slug=tenant_header, is_active=True)
                request.tenant = target_tenant
            except Tenant.DoesNotExist as exc:
                raise AuthenticationFailed(
                    f"Workspace '{tenant_header}' não encontrado ou inativo."
                ) from exc
        else:
            request.tenant = api_key.tenant

        request.auth = api_key
        return ApiKeyUser(api_key), api_key

    def _authenticate_jwt(self, request: Request, token: str) -> tuple[Any, Any]:
        jwt_auth = JWTAuthentication()
        try:
            validated_token = jwt_auth.get_validated_token(token)
            user = jwt_auth.get_user(validated_token)
        except Exception as exc:
            raise AuthenticationFailed(f"Token JWT inválido: {exc}") from exc

        tenant_header = request.headers.get("X-Tenant-ID")

        if user.is_superuser:
            if tenant_header:
                try:
                    if _is_uuid(tenant_header):
                        tenant = Tenant.objects.get(id=tenant_header, is_active=True)
                    else:
                        tenant = Tenant.objects.get(slug=tenant_header, is_active=True)
                except Tenant.DoesNotExist as exc:
                    raise AuthenticationFailed(
                        f"Workspace '{tenant_header}' não encontrado ou inativo."
                    ) from exc
            else:
                tenant = Tenant.objects.filter(is_active=True).first()
                if not tenant:
                    raise AuthenticationFailed("Nenhum workspace ativo disponível no sistema.")

            request.tenant = tenant
            request.workspace_membership = None
        else:
            memberships = (
                WorkspaceMembership.objects.filter(user=user, is_active=True)
                .select_related("tenant")
            )
            if tenant_header:
                if _is_uuid(tenant_header):
                    membership = memberships.filter(tenant__id=tenant_header).first()
                else:
                    membership = memberships.filter(tenant__slug=tenant_header).first()
                if not membership:
                    raise AuthenticationFailed(
                        f"Usuário não possui acesso ativo ao workspace '{tenant_header}'."
                    )
            else:
                membership = memberships.first()
                if not membership:
                    raise AuthenticationFailed(
                        "Usuário não possui vínculo ativo com nenhum workspace."
                    )

            request.tenant = membership.tenant
            request.workspace_membership = membership

        request.auth = validated_token
        return user, validated_token
