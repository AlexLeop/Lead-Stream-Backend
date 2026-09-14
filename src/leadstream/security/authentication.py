from __future__ import annotations

import uuid
from typing import Any

from django.utils import timezone
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request
from rest_framework_simplejwt.authentication import JWTAuthentication

from leadstream.security.crypto import hash_api_key
from leadstream.security.models import APIKey, WorkspaceMembership
from leadstream.tenancy.models import Tenant


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
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
    """Autenticação combinada para suportar API Keys e JWT com resolução de workspace."""

    def authenticate_header(self, request: Request) -> str:
        return "Bearer"

    def authenticate(self, request: Request) -> tuple[Any, Any] | None:
        auth_header = request.headers.get("Authorization")
        x_api_key = request.headers.get("X-API-Key")

        if x_api_key:
            return self._authenticate_api_key(request, x_api_key)

        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise AuthenticationFailed("Cabeçalho Authorization inválido.")

        raw_token = parts[1]
        if raw_token.startswith("ls_live_") or raw_token.startswith("ls_test_"):
            return self._authenticate_api_key(request, raw_token)

        return self._authenticate_jwt(request, raw_token)

    def _authenticate_api_key(self, request: Request, raw_key: str) -> tuple[Any, Any]:
        key_hash = hash_api_key(raw_key)
        api_key = (
            APIKey.objects.select_related("tenant")
            .filter(hashed_key=key_hash, is_active=True)
            .first()
        )

        if not api_key:
            raise AuthenticationFailed("Chave de API inválida ou inativa.")

        if api_key.is_expired:
            raise AuthenticationFailed("Chave de API expirada.")

        if not api_key.tenant.is_active:
            raise AuthenticationFailed("O workspace associado a esta chave de API está inativo.")

        # Atualiza métrica de último uso
        APIKey.objects.filter(pk=api_key.pk).update(last_used_at=timezone.now())

        tenant_header = request.headers.get("X-Tenant-ID")
        if tenant_header and tenant_header not in {str(api_key.tenant_id), api_key.tenant.slug}:
            raise AuthenticationFailed(
                "Chaves de API são vinculadas a um único workspace e não podem alternar contexto."
            )
        request.tenant = api_key.tenant  # type: ignore[attr-defined]

        request.auth = api_key
        return ApiKeyUser(api_key), api_key

    def _authenticate_jwt(self, request: Request, token: str) -> tuple[Any, Any]:
        jwt_auth = JWTAuthentication()
        try:
            validated_token = jwt_auth.get_validated_token(token.encode("utf-8"))
            user = jwt_auth.get_user(validated_token)
        except Exception as exc:
            raise AuthenticationFailed("Token JWT inválido ou expirado.") from exc

        tenant_header = request.headers.get("X-Tenant-ID")
        token_tenant_id = validated_token.get("tenant_id")
        tenant_selector = tenant_header or (str(token_tenant_id) if token_tenant_id else None)

        is_superuser = bool(getattr(user, "is_superuser", False))
        if is_superuser:
            if tenant_selector:
                try:
                    if _is_uuid(tenant_selector):
                        tenant = Tenant.objects.get(id=tenant_selector, is_active=True)
                    else:
                        tenant = Tenant.objects.get(slug=tenant_selector, is_active=True)
                except Tenant.DoesNotExist as exc:
                    raise AuthenticationFailed(
                        f"Workspace '{tenant_selector}' não encontrado ou inativo."
                    ) from exc
            else:
                from leadstream.tenancy.services import get_internal_tenant

                tenant = get_internal_tenant()
                if not tenant.is_active:
                    raise AuthenticationFailed("O workspace interno está inativo.")

            request.tenant = tenant  # type: ignore[attr-defined]
            request.workspace_membership = None  # type: ignore[attr-defined]
        else:
            pk_val = getattr(user, "pk", None)
            if pk_val is None:
                raise AuthenticationFailed("Usuário sem chave primária válida.")
            user_pk: int | str = pk_val if isinstance(pk_val, (int, str)) else str(pk_val)
            memberships = WorkspaceMembership.objects.filter(
                user_id=user_pk, is_active=True
            ).select_related("tenant")
            if tenant_selector:
                if _is_uuid(tenant_selector):
                    membership = memberships.filter(tenant__id=tenant_selector).first()
                else:
                    membership = memberships.filter(tenant__slug=tenant_selector).first()
                if not membership:
                    raise AuthenticationFailed(
                        f"Usuário não possui acesso ativo ao workspace '{tenant_selector}'."
                    )
            else:
                membership = memberships.first()
                if not membership:
                    raise AuthenticationFailed(
                        "Usuário não possui vínculo ativo com nenhum workspace."
                    )

            request.tenant = membership.tenant  # type: ignore[attr-defined]
            request.workspace_membership = membership  # type: ignore[attr-defined]

        request.auth = validated_token
        return user, validated_token


class CombinedAuthenticationScheme(OpenApiAuthenticationExtension):  # type: ignore[no-untyped-call]
    target_class = "leadstream.security.authentication.CombinedAuthentication"
    name = "BearerAuth"

    def get_security_definition(self, auto_schema: Any) -> dict[str, Any]:
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT / APIKey",
            "description": (
                "Autenticação híbrida enterprise. Forneça um token JWT de acesso "
                "(Bearer <token>) ou uma chave de API direta (Bearer ls_live_...)."
            ),
        }
