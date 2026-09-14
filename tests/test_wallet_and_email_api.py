from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from rest_framework.test import APIClient

from leadstream.billing.services import get_or_create_wallet
from leadstream.security.crypto import generate_api_key
from leadstream.security.models import WorkspaceRole
from leadstream.tenancy.models import Tenant


@pytest.mark.django_db
def test_wallet_and_ledger_api():
    client = APIClient()
    tenant = Tenant.objects.create(name="Org Financeiro", slug="org-financeiro")
    get_or_create_wallet(tenant)
    _, raw_key = generate_api_key(tenant, "financeiro", WorkspaceRole.OPERATOR)
    client.credentials(HTTP_X_API_KEY=raw_key)

    # 1. Consultar carteira
    res = client.get("/api/v1/faturamento/carteira/", HTTP_X_TENANT_ID=str(tenant.id))
    assert res.status_code == 200
    assert res.data["balance"] == 500
    assert res.data["reserved_balance"] == 0
    assert res.data["available_balance"] == 500

    # 2. Recarga simulada
    deposit_payload = {"amount": 250, "reference_id": "REC-001", "metadata": {"gateway": "pix"}}
    res = client.post(
        "/api/v1/faturamento/carteira/recarga/",
        deposit_payload,
        format="json",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert res.status_code == 200
    assert res.data["balance"] == 750
    assert res.data["transaction"]["amount"] == 250
    assert res.data["transaction"]["balance_after"] == 750

    # 3. Consultar extrato
    res = client.get("/api/v1/faturamento/carteira/extrato/", HTTP_X_TENANT_ID=str(tenant.id))
    assert res.status_code == 200
    assert len(res.data["results"]) >= 2  # Bônus inicial + Depósito


@pytest.mark.django_db
@patch("leadstream.validation.smtp_probe.check_domain_mx")
@patch("leadstream.validation.smtp_probe.smtplib.SMTP")
def test_email_validation_api(mock_smtp_cls, mock_mx):
    client = APIClient()
    tenant = Tenant.objects.create(name="Org Validador", slug="org-validador")
    _, raw_key = generate_api_key(tenant, "validador", WorkspaceRole.OPERATOR)
    client.credentials(HTTP_X_API_KEY=raw_key)

    mock_mx.return_value = {"mx_found": True, "mail_servers": ["mx.google.com"]}
    mock_client = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = mock_client
    mock_client.ehlo.return_value = (250, b"OK")
    mock_client.mail.return_value = (250, b"OK")
    mock_client.rcpt.side_effect = [
        (550, b"User unknown"),  # canary
        (250, b"Recipient OK"),  # target
    ]

    # Validação de e-mail único
    res = client.post(
        "/api/v1/validacao/emails/",
        {"email": "diretor@empresa.com.br", "deep_smtp": True},
        format="json",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert res.status_code == 200
    assert res.data["status"] == "DELIVERABLE"
    assert res.data["is_deliverable"] is True
    assert res.data["is_catch_all"] is False
