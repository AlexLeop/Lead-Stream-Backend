from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from leadstream.security.crypto import generate_api_key
from leadstream.security.models import WorkspaceRole
from leadstream.tenancy.models import Tenant

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", "/api/v1/dashboard", None),
        ("get", "/api/v1/workspace/", None),
        ("get", "/api/v1/enrichment/status", None),
        ("get", "/api/v1/leads", None),
        ("post", "/api/v1/enrichment/person", {"query": "52998224725"}),
        ("post", "/api/v1/discovery/search", {"cnaePrincipal": "6201501"}),
    ],
)
def test_business_endpoints_reject_anonymous_access(
    method: str, path: str, payload: dict[str, str] | None
) -> None:
    client = APIClient()
    response = getattr(client, method)(path, payload or {}, format="json")
    assert response.status_code == 401


def test_api_key_cannot_switch_workspace() -> None:
    tenant_a = Tenant.objects.create(name="Cliente A", slug="cliente-a")
    tenant_b = Tenant.objects.create(name="Cliente B", slug="cliente-b")
    _, raw_key = generate_api_key(tenant_a, "integração-a", WorkspaceRole.ADMIN)
    client = APIClient()
    client.credentials(HTTP_X_API_KEY=raw_key, HTTP_X_TENANT_ID=str(tenant_b.id))

    response = client.get("/api/v1/workspace/")

    assert response.status_code == 401
    assert "não podem alternar" in response.json()["detail"]


def test_read_only_key_cannot_trigger_enrichment() -> None:
    tenant = Tenant.objects.create(name="Cliente leitura", slug="cliente-leitura")
    _, raw_key = generate_api_key(tenant, "somente-leitura", WorkspaceRole.READ_ONLY)
    client = APIClient()
    client.credentials(HTTP_X_API_KEY=raw_key)

    response = client.post(
        "/api/v1/enrichment/person",
        {"query": "52998224725"},
        format="json",
    )

    assert response.status_code == 403


def test_superadmin_must_select_active_workspace_explicitly_for_switch() -> None:
    target = Tenant.objects.create(name="Cliente alvo", slug="cliente-alvo")
    user = User.objects.create_superuser(
        username="root-enterprise",
        email="root@example.com",
        password="not-used-in-test",
    )
    token = RefreshToken.for_user(user).access_token
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(target.id),
    )

    response = client.get("/api/v1/workspace/")

    assert response.status_code == 200
    assert response.json()["id"] == str(target.id)
