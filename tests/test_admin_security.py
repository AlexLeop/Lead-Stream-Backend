import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from leadstream.tenancy.models import Tenant

User = get_user_model()


@pytest.mark.django_db
def test_admin_users_and_api_keys():
    master = User.objects.create_superuser(
        username="master", email="master@example.com", password="pass"
    )
    tenant = Tenant.objects.create(name="Beta Corp", slug="beta-corp")
    client = APIClient()
    client.force_authenticate(user=master)

    # 1. Create user
    user_resp = client.post(
        "/api/v1/admin/users/",
        {
            "username": "operador_beta",
            "email": "operador@betacorp.com",
            "password": "SecurePassword123!",
            "tenant_id": str(tenant.id),
            "role": "OPERATOR",
        },
    )
    assert user_resp.status_code == 201
    user_id = user_resp.data["id"]

    # 2. List users
    list_users = client.get("/api/v1/admin/users/")
    assert list_users.status_code == 200
    results = (
        list_users.data["results"]
        if "results" in list_users.data
        else list_users.data
    )
    assert any(u["username"] == "operador_beta" for u in results)

    # 3. Patch user
    patch_resp = client.patch(
        f"/api/v1/admin/users/{user_id}/",
        {"role": "ADMIN", "is_active": True},
    )
    assert patch_resp.status_code == 200

    # 4. Issue API Key
    key_resp = client.post(
        "/api/v1/admin/api-keys/",
        {
            "tenant_id": str(tenant.id),
            "name": "Integration Key CRM",
            "role": "OPERATOR",
        },
    )
    assert key_resp.status_code == 201
    assert "raw_key" in key_resp.data
    key_id = key_resp.data["id"]

    # 5. Revoke API Key
    del_resp = client.delete(f"/api/v1/admin/api-keys/{key_id}/")
    assert del_resp.status_code in [200, 204]
