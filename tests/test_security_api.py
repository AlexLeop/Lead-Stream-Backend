from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from leadstream.security.models import SecurityAuditLog, WorkspaceMembership, WorkspaceRole
from leadstream.tenancy.models import Tenant


@pytest.mark.django_db
def test_auth_token_obtain_and_refresh() -> None:
    tenant = Tenant.objects.create(name="Empresa Auth", slug="empresa-auth")
    user = User.objects.create_user(username="test_auth_user", password="secure_password_123")
    WorkspaceMembership.objects.create(user=user, tenant=tenant, role=WorkspaceRole.OPERATOR)

    client = APIClient()

    # Login valido
    response = client.post(
        "/api/v1/auth/token/",
        {"username": "test_auth_user", "password": "secure_password_123"},
        format="json",
    )
    assert response.status_code == 200
    data = response.json()
    assert "access" in data
    assert "refresh" not in data
    assert client.cookies["leadstream_refresh"]["httponly"] is True

    # Refresh válido usando somente o cookie HttpOnly
    refresh_response = client.post(
        "/api/v1/auth/token/refresh/",
        {},
        format="json",
    )
    assert refresh_response.status_code == 200
    assert "access" in refresh_response.json()
    assert "refresh" not in refresh_response.json()

    # Login invalido
    bad_response = client.post(
        "/api/v1/auth/token/",
        {"username": "test_auth_user", "password": "wrong_password"},
        format="json",
    )
    assert bad_response.status_code == 401


@pytest.mark.django_db
def test_auth_token_revoke() -> None:
    tenant = Tenant.objects.create(name="Empresa Revoke", slug="empresa-revoke")
    user = User.objects.create_user(username="user_revoke", password="secure_password_123")
    WorkspaceMembership.objects.create(user=user, tenant=tenant, role=WorkspaceRole.OPERATOR)

    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)
    refresh_str = str(refresh)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    client.cookies["leadstream_refresh"] = refresh_str

    response = client.post(
        "/api/v1/auth/token/revoke/",
        {},
        format="json",
    )
    assert response.status_code in (200, 204)

    # Tentar dar refresh no token revogado deve falhar
    refresh_attempt = client.post(
        "/api/v1/auth/token/refresh/",
        {},
        format="json",
    )
    assert refresh_attempt.status_code == 401


@pytest.mark.django_db
def test_api_keys_management_crud() -> None:
    tenant = Tenant.objects.create(name="Empresa Keys", slug="empresa-keys")
    admin_user = User.objects.create_user(username="admin_keys", password="secure_password_123")
    WorkspaceMembership.objects.create(user=admin_user, tenant=tenant, role=WorkspaceRole.ADMIN)

    client = APIClient()
    refresh = RefreshToken.for_user(admin_user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token!s}")

    # Criar API Key
    create_response = client.post(
        "/api/v1/security/keys/",
        {
            "name": "Chave de Integracao Hubspot",
            "role": "OPERATOR",
            "env": "live",
        },
        format="json",
    )
    assert create_response.status_code == 201
    created_data = create_response.json()
    assert "raw_key" in created_data
    raw_key = created_data["raw_key"]
    assert raw_key.startswith("ls_live_")
    key_id = created_data["id"]

    # Listar API Keys
    list_response = client.get("/api/v1/security/keys/")
    assert list_response.status_code == 200
    list_data = list_response.json()
    results = list_data.get("results", list_data)
    assert len(results) >= 1
    # Chave bruta ou hash nunca podem estar no endpoint de listagem
    assert "raw_key" not in results[0]
    assert "hashed_key" not in results[0]
    assert results[0]["prefix"].startswith("ls_live_")

    # Autenticar com a chave criada via header
    api_key_client = APIClient()
    api_key_client.credentials(HTTP_X_API_KEY=raw_key)
    # Testa acesso com a chave
    check_response = api_key_client.get("/api/v1/security/keys/")
    # Como a chave foi criada com papel OPERATOR, acessar endpoint que exige ADMIN deve dar 403
    assert check_response.status_code == 403

    # Revogar API Key como ADMIN
    delete_response = client.delete(f"/api/v1/security/keys/{key_id}/")
    assert delete_response.status_code in (200, 204)

    # Chave revogada nao deve mais autenticar
    revoked_check = api_key_client.get("/api/v1/security/keys/")
    assert revoked_check.status_code == 401


@pytest.mark.django_db
def test_security_audit_logs_list() -> None:
    tenant = Tenant.objects.create(name="Empresa Audit", slug="empresa-audit")
    admin_user = User.objects.create_user(username="admin_audit", password="secure_password_123")
    WorkspaceMembership.objects.create(user=admin_user, tenant=tenant, role=WorkspaceRole.ADMIN)

    SecurityAuditLog.objects.create(
        tenant=tenant,
        actor_type="USER",
        actor_id=str(admin_user.pk),
        action="KEY_CREATE",
        resource_accessed="/api/v1/security/keys/",
        status_code=201,
        details={"key_name": "Teste"},
    )

    client = APIClient()
    refresh = RefreshToken.for_user(admin_user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token!s}")

    response = client.get("/api/v1/security/audit-logs/")
    assert response.status_code == 200
    data = response.json()
    results = data.get("results", data)
    assert len(results) >= 1
    assert results[0]["action"] == "KEY_CREATE"


@pytest.mark.django_db
def test_unauthenticated_request_rejected_on_protected_endpoints() -> None:
    client = APIClient()

    # Tentativa sem token / chave em endpoint de leads canonicos
    resp_lead = client.get("/api/v1/leads/00000000-0000-0000-0000-000000000001/canonical/")
    assert resp_lead.status_code == 401
    assert "detail" in resp_lead.json()

    # Tentativa sem token / chave em endpoint de lotes
    resp_lotes = client.get("/api/v1/lotes/")
    assert resp_lotes.status_code == 401
    assert "detail" in resp_lotes.json()

    # Tentativa sem token / chave em endpoint de integracoes
    resp_integracoes = client.get("/api/v1/integracoes/conexoes/")
    assert resp_integracoes.status_code == 401
    assert "detail" in resp_integracoes.json()
