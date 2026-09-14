from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from leadstream.billing.models import CreditWallet
from leadstream.tenancy.models import Tenant


@pytest.mark.django_db
def test_manager_dashboard_endpoints() -> None:
    client = APIClient()
    tenant, _ = Tenant.objects.get_or_create(slug="internal", defaults={"name": "Operação interna"})
    user = User.objects.create_superuser(username="manager_admin", password="ManagerPassword123!")
    access_token = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

    # 1. Dashboard (both with and without trailing slash)
    res_dash = client.get("/api/v1/dashboard")
    assert res_dash.status_code == 200
    assert "summary" in res_dash.data
    assert "chartData" in res_dash.data
    assert "industryBreakdown" in res_dash.data
    assert "seniorityBreakdown" in res_dash.data

    res_dash_slash = client.get("/api/v1/dashboard/")
    assert res_dash_slash.status_code == 200

    # 2. Data Health
    res_health = client.get("/api/v1/data-health")
    assert res_health.status_code == 200
    assert "summary" in res_health.data
    assert "coverage" in res_health.data

    # 3. Datasets
    res_datasets = client.get("/api/v1/datasets")
    assert res_datasets.status_code == 200
    assert isinstance(res_datasets.data, list)

    # 4. Leads & lookup
    res_leads = client.get("/api/v1/leads")
    assert res_leads.status_code == 200
    assert isinstance(res_leads.data, list)

    res_lookup = client.get("/api/v1/leads/lookup?q=empresa")
    assert res_lookup.status_code == 200

    # 5. Lists
    res_lists = client.get("/api/v1/lists")
    assert res_lists.status_code == 200

    # 6. Activities
    res_act = client.get("/api/v1/activities")
    assert res_act.status_code == 200

    # 7. CRM Connections
    res_crm = client.get("/api/v1/crm-connections")
    assert res_crm.status_code == 200

    # 8. Pix Status
    res_pix = client.get("/api/v1/pix/status")
    assert res_pix.status_code == 200

    # 9. Enrichment Catalog & Status & Company
    res_enr_stat = client.get("/api/v1/enrichment/status")
    assert res_enr_stat.status_code == 200
    res_enr_cat = client.get("/api/v1/enrichment/catalog")
    assert res_enr_cat.status_code == 200

    res_enr_comp = client.post(
        "/api/v1/enrichment/company", {"query": "12345678000190"}, format="json"
    )
    assert res_enr_comp.status_code == 200

    # 10. Billing Wallet & Transactions
    CreditWallet.objects.get_or_create(tenant=tenant)
    res_wallet = client.get("/api/v1/billing/wallet/")
    assert res_wallet.status_code == 200
    res_tx = client.get("/api/v1/billing/transactions/")
    assert res_tx.status_code == 200

    # 11. Discovery CNAE & Search
    res_cnae = client.get("/api/v1/discovery/cnaes?q=tecnologia")
    assert res_cnae.status_code == 200
    res_disc_search = client.post(
        "/api/v1/discovery/search", {"cnaePrincipal": "6201501"}, format="json"
    )
    assert res_disc_search.status_code == 200
