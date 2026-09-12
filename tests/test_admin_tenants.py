import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


@pytest.mark.django_db
def test_admin_tenant_lifecycle():
    admin = User.objects.create_superuser(
        username="master", email="master@example.com", password="pass"
    )
    client = APIClient()
    client.force_authenticate(user=admin)

    # 1. Create tenant
    create_resp = client.post(
        "/api/v1/admin/tenants/",
        {
            "name": "Cliente Alfa",
            "slug": "cliente-alfa",
            "max_batch_size": 25000,
            "rate_limit_per_minute": 120,
            "max_concurrency": 8,
            "initial_credits": 1000,
        },
    )
    assert create_resp.status_code == 201
    tenant_id = create_resp.data["id"]

    # 2. List tenants
    list_resp = client.get("/api/v1/admin/tenants/")
    assert list_resp.status_code == 200
    results = (
        list_resp.data["results"] if "results" in list_resp.data else list_resp.data
    )
    assert any(t["slug"] == "cliente-alfa" for t in results)

    # 3. Patch tenant (deactivate)
    patch_resp = client.patch(
        f"/api/v1/admin/tenants/{tenant_id}/",
        {"is_active": False, "max_batch_size": 50000},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.data["is_active"] is False
    assert patch_resp.data["max_batch_size"] == 50000

    # 4. Impersonate tenant
    imp_resp = client.post(f"/api/v1/admin/tenants/{tenant_id}/impersonate/")
    assert imp_resp.status_code == 200
    assert imp_resp.data["tenant"]["slug"] == "cliente-alfa"
    assert "token" in imp_resp.data or "tenant_slug" in imp_resp.data
