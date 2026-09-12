import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from leadstream.security.models import SecurityAuditLog
from leadstream.tenancy.models import Tenant

User = get_user_model()


@pytest.mark.django_db
def test_admin_governance_providers_smtp():
    master = User.objects.create_superuser(
        username="master", email="master@example.com", password="pass"
    )
    tenant = Tenant.objects.create(name="Omega Corp", slug="omega-corp")
    client = APIClient()
    client.force_authenticate(user=master)

    # 1. Suppression Opt-Out
    supp_resp = client.post(
        "/api/v1/admin/suppression/",
        {
            "tenant_id": str(tenant.id),
            "scope": "EMAIL",
            "value": "optout@cliente.com.br",
            "reason": "Solicitação LGPD do titular",
        },
        format="json",
    )
    assert supp_resp.status_code == 201
    supp_id = supp_resp.data["id"]

    list_supp = client.get("/api/v1/admin/suppression/")
    assert list_supp.status_code == 200

    del_supp = client.delete(f"/api/v1/admin/suppression/{supp_id}/")
    assert del_supp.status_code in [200, 204]

    # 2. Audit Logs
    SecurityAuditLog.objects.create(
        tenant=tenant,
        actor_type="SUPERADMIN",
        actor_id="master",
        action="CONFIG_UPDATE",
        resource_accessed="/api/v1/admin/suppression/",
        status_code=200,
    )
    logs_resp = client.get("/api/v1/admin/audit-logs/")
    assert logs_resp.status_code == 200
    assert len(logs_resp.data["results"]) >= 1

    # 3. Providers Config & Budget
    prov_resp = client.get("/api/v1/admin/providers/")
    assert prov_resp.status_code == 200

    budget_resp = client.patch(
        "/api/v1/admin/providers/budget/",
        {"daily_limit_usd": 150.0, "circuit_breaker_rate": 0.15},
        format="json",
    )
    assert budget_resp.status_code == 200

    # 4. SMTP Config & Probe
    smtp_resp = client.get("/api/v1/admin/smtp-config/")
    assert smtp_resp.status_code == 200

    probe_resp = client.post(
        "/api/v1/admin/smtp-probe/",
        {"email": "test@gmail.com"},
        format="json",
    )
    assert probe_resp.status_code == 200
    assert "status" in probe_resp.data
    assert "mx_host" in probe_resp.data
