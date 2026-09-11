from __future__ import annotations

import datetime

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIRequestFactory
from rest_framework_simplejwt.tokens import RefreshToken

from leadstream.security.authentication import CombinedAuthentication
from leadstream.security.crypto import generate_api_key
from leadstream.security.models import WorkspaceMembership, WorkspaceRole
from leadstream.security.permissions import HasWorkspaceRole
from leadstream.tenancy.models import Tenant


@pytest.mark.django_db
def test_authentication_with_valid_api_key_bearer() -> None:
    tenant = Tenant.objects.create(name="Tenant Alpha", slug="tenant-alpha")
    api_key_obj, raw_key = generate_api_key(
        tenant=tenant,
        name="Chave 1",
        role=WorkspaceRole.OPERATOR,
    )

    factory = APIRequestFactory()
    request = factory.get("/api/v1/test/", HTTP_AUTHORIZATION=f"Bearer {raw_key}")

    auth = CombinedAuthentication()
    auth_result = auth.authenticate(request)

    assert auth_result is not None
    user, key_instance = auth_result
    assert user.is_authenticated is True
    assert key_instance.id == api_key_obj.id
    assert request.tenant == tenant
    assert request.auth == api_key_obj

    # Valida atualizacao de last_used_at
    api_key_obj.refresh_from_db()
    assert api_key_obj.last_used_at is not None


@pytest.mark.django_db
def test_authentication_with_valid_x_api_key_header() -> None:
    tenant = Tenant.objects.create(name="Tenant Beta", slug="tenant-beta")
    _, raw_key = generate_api_key(
        tenant=tenant,
        name="Chave Header",
        role=WorkspaceRole.ADMIN,
    )

    factory = APIRequestFactory()
    request = factory.get("/api/v1/test/", HTTP_X_API_KEY=raw_key)

    auth = CombinedAuthentication()
    auth_result = auth.authenticate(request)

    assert auth_result is not None
    user, _ = auth_result
    assert user.is_authenticated is True
    assert request.tenant == tenant


@pytest.mark.django_db
def test_authentication_with_invalid_api_key() -> None:
    factory = APIRequestFactory()
    request = factory.get("/api/v1/test/", HTTP_AUTHORIZATION="Bearer ls_live_invalidkey123456789")

    auth = CombinedAuthentication()
    with pytest.raises(AuthenticationFailed, match="API Key inválida"):
        auth.authenticate(request)


@pytest.mark.django_db
def test_authentication_with_expired_api_key() -> None:
    tenant = Tenant.objects.create(name="Tenant Exp", slug="tenant-exp")
    api_key_obj, raw_key = generate_api_key(
        tenant=tenant,
        name="Chave Exp",
        role=WorkspaceRole.OPERATOR,
    )
    api_key_obj.expires_at = timezone.now() - datetime.timedelta(days=1)
    api_key_obj.save(update_fields=["expires_at"])

    factory = APIRequestFactory()
    request = factory.get("/api/v1/test/", HTTP_X_API_KEY=raw_key)

    auth = CombinedAuthentication()
    with pytest.raises(AuthenticationFailed, match="expirada"):
        auth.authenticate(request)


@pytest.mark.django_db
def test_authentication_with_jwt_for_workspace_member() -> None:
    tenant = Tenant.objects.create(name="Tenant Gamma", slug="tenant-gamma")
    user = User.objects.create_user(username="member_gamma", password="password123")
    WorkspaceMembership.objects.create(user=user, tenant=tenant, role=WorkspaceRole.OPERATOR)

    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)

    factory = APIRequestFactory()
    request = factory.get("/api/v1/test/", HTTP_AUTHORIZATION=f"Bearer {access_token}")

    auth = CombinedAuthentication()
    auth_result = auth.authenticate(request)

    assert auth_result is not None
    auth_user, _ = auth_result
    assert auth_user.id == user.id
    assert request.tenant == tenant
    assert request.workspace_membership.role == WorkspaceRole.OPERATOR


@pytest.mark.django_db
def test_authentication_with_jwt_superuser_tenant_switching() -> None:
    tenant_target = Tenant.objects.create(name="Tenant Alvo", slug="tenant-alvo")
    super_user = User.objects.create_superuser(username="admin_global", password="password123")

    refresh = RefreshToken.for_user(super_user)
    access_token = str(refresh.access_token)

    factory = APIRequestFactory()
    request = factory.get(
        "/api/v1/test/",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        HTTP_X_TENANT_ID="tenant-alvo",
    )

    auth = CombinedAuthentication()
    auth_result = auth.authenticate(request)

    assert auth_result is not None
    assert request.tenant == tenant_target


@pytest.mark.django_db
def test_authentication_with_jwt_user_without_workspace_fails() -> None:
    user = User.objects.create_user(username="orphan_user", password="password123")
    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)

    factory = APIRequestFactory()
    request = factory.get("/api/v1/test/", HTTP_AUTHORIZATION=f"Bearer {access_token}")

    auth = CombinedAuthentication()
    with pytest.raises(AuthenticationFailed, match="workspace"):
        auth.authenticate(request)


@pytest.mark.django_db
def test_permissions_role_hierarchy() -> None:
    tenant = Tenant.objects.create(name="Tenant Perm", slug="tenant-perm")
    user_ro = User.objects.create_user(username="user_ro", password="password123")
    WorkspaceMembership.objects.create(user=user_ro, tenant=tenant, role=WorkspaceRole.READ_ONLY)

    user_op = User.objects.create_user(username="user_op", password="password123")
    WorkspaceMembership.objects.create(user=user_op, tenant=tenant, role=WorkspaceRole.OPERATOR)

    perm_op = HasWorkspaceRole(WorkspaceRole.OPERATOR)
    perm_admin = HasWorkspaceRole(WorkspaceRole.ADMIN)

    factory = APIRequestFactory()

    # Usuario READ_ONLY tentando acessar rota OPERATOR -> negado
    req_ro = factory.get("/")
    req_ro.user = user_ro
    req_ro.tenant = tenant
    req_ro.workspace_membership = user_ro.workspace_memberships.first()
    assert perm_op.has_permission(req_ro, None) is False

    # Usuario OPERATOR tentando acessar rota OPERATOR -> permitido
    req_op = factory.get("/")
    req_op.user = user_op
    req_op.tenant = tenant
    req_op.workspace_membership = user_op.workspace_memberships.first()
    assert perm_op.has_permission(req_op, None) is True

    # Usuario OPERATOR tentando acessar rota ADMIN -> negado
    assert perm_admin.has_permission(req_op, None) is False
