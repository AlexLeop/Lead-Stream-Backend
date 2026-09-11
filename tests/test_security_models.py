from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError

from leadstream.security.crypto import generate_api_key, hash_api_key, verify_api_key
from leadstream.security.models import (
    SecurityAuditLog,
    WorkspaceMembership,
    WorkspaceRole,
)
from leadstream.tenancy.models import Tenant


@pytest.mark.django_db
def test_crypto_api_key_generation_and_hashing() -> None:
    tenant = Tenant.objects.create(name="Tenant Teste", slug="tenant-teste")

    api_key_instance, raw_key = generate_api_key(
        tenant=tenant,
        name="Chave de Producao",
        role=WorkspaceRole.ADMIN,
        env="live",
    )

    assert raw_key.startswith("ls_live_")
    assert len(raw_key) > 30
    assert api_key_instance.prefix == raw_key[:16]
    assert len(api_key_instance.hashed_key) == 64
    assert api_key_instance.hashed_key == hash_api_key(raw_key)
    assert raw_key not in api_key_instance.hashed_key

    # Verificacao com timing-attack safe compare
    assert verify_api_key(raw_key, api_key_instance.hashed_key) is True
    assert verify_api_key("ls_live_invalid_key_12345", api_key_instance.hashed_key) is False


@pytest.mark.django_db
def test_crypto_test_environment_prefix() -> None:
    tenant = Tenant.objects.create(name="Tenant Teste 2", slug="tenant-teste-2")

    api_key_instance, raw_key = generate_api_key(
        tenant=tenant,
        name="Chave de Teste",
        role=WorkspaceRole.OPERATOR,
        env="test",
    )

    assert raw_key.startswith("ls_test_")
    assert api_key_instance.prefix.startswith("ls_test_")
    assert api_key_instance.role == WorkspaceRole.OPERATOR


@pytest.mark.django_db
def test_workspace_membership_creation_and_unique_constraint() -> None:
    tenant = Tenant.objects.create(name="Empresa Alpha", slug="empresa-alpha")
    user = User.objects.create_user(username="operador1", password="secure_password_123")

    membership = WorkspaceMembership.objects.create(
        user=user,
        tenant=tenant,
        role=WorkspaceRole.ADMIN,
    )

    assert membership.role == WorkspaceRole.ADMIN
    assert membership.is_active is True
    assert user.workspace_memberships.count() == 1

    # Nao pode permitir associacao duplicada do mesmo user e tenant
    with pytest.raises(IntegrityError):
        WorkspaceMembership.objects.create(
            user=user,
            tenant=tenant,
            role=WorkspaceRole.OPERATOR,
        )


@pytest.mark.django_db
def test_security_audit_log_creation() -> None:
    tenant = Tenant.objects.create(name="Empresa Beta", slug="empresa-beta")

    audit = SecurityAuditLog.objects.create(
        tenant=tenant,
        actor_type="USER",
        actor_id="user-123",
        ip_address="192.168.1.100",
        user_agent="Mozilla/5.0 TestBrowser",
        action="LOGIN_SUCCESS",
        resource_accessed="/api/v1/auth/token/",
        status_code=200,
        details={"method": "JWT"},
    )

    assert audit.action == "LOGIN_SUCCESS"
    assert audit.actor_type == "USER"
    assert audit.ip_address == "192.168.1.100"
    assert audit.details["method"] == "JWT"
    assert audit.timestamp is not None
