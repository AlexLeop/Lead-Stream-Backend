import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from leadstream.billing.models import CreditWallet, DataBlock, PriceBook, PriceRule
from leadstream.tenancy.models import Tenant

User = get_user_model()


@pytest.mark.django_db
def test_admin_pricing_and_ledger():
    master = User.objects.create_superuser(
        username="master", email="master@example.com", password="pass"
    )
    tenant = Tenant.objects.create(name="Delta Corp", slug="delta-corp")
    CreditWallet.objects.create(tenant=tenant, balance=500)
    book = PriceBook.objects.create(
        tenant=tenant, version=1, name="Plano Padrão", effective_at=timezone.now()
    )
    PriceRule.objects.create(
        tenant=tenant,
        price_book=book,
        block=DataBlock.COMPANY_REGISTRY,
        unit_price_cents=10,
    )

    client = APIClient()
    client.force_authenticate(user=master)

    # 1. List pricing
    price_resp = client.get("/api/v1/admin/pricing/")
    assert price_resp.status_code == 200
    results = (
        price_resp.data["results"]
        if "results" in price_resp.data
        else price_resp.data
    )
    assert len(results) >= 1

    # 2. Update price rule
    update_resp = client.put(
        f"/api/v1/admin/pricing/{book.id}/",
        {
            "rules": [
                {
                    "block": "COMPANY_REGISTRY",
                    "unit_price_cents": 15,
                    "minimum_confidence": 85,
                    "refresh_window_days": 45,
                }
            ]
        },
        format="json",
    )
    assert update_resp.status_code == 200

    # 3. List wallets
    wallets_resp = client.get("/api/v1/admin/wallets/")
    assert wallets_resp.status_code == 200

    # 4. Inject audited credit
    credit_resp = client.post(
        f"/api/v1/admin/wallets/{tenant.id}/credit/",
        {"amount": 2500, "reason": "Recarga contratual via Pix - Pedido #8912"},
        format="json",
    )
    assert credit_resp.status_code == 200
    assert credit_resp.data["balance"] == 3000

    # 5. List transactions
    tx_resp = client.get(f"/api/v1/admin/wallets/{tenant.id}/transactions/")
    assert tx_resp.status_code == 200
    tx_results = (
        tx_resp.data["results"] if "results" in tx_resp.data else tx_resp.data
    )
    assert len(tx_results) >= 1
    assert tx_results[0]["amount"] == 2500
