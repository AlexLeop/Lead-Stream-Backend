from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from leadstream.billing.services import (
    capture_and_release,
    deposit_credits,
    get_or_create_wallet,
    hold_credits,
)
from leadstream.tenancy.models import Tenant


@pytest.mark.django_db
def test_wallet_creation_and_deposit():
    tenant = Tenant.objects.create(name="Workspace Teste", slug="ws-teste")
    wallet = get_or_create_wallet(tenant)
    assert wallet.balance == 500  # Saldo cortesia inicial
    assert wallet.reserved_balance == 0
    assert wallet.available_balance == 500

    tx = deposit_credits(wallet, amount=1000, reference_id="PIX-001", metadata={"origin": "pix"})
    wallet.refresh_from_db()
    assert wallet.balance == 1500
    assert wallet.available_balance == 1500
    assert tx.transaction_type == "DEPOSIT"
    assert tx.amount == 1000
    assert tx.balance_after == 1500


@pytest.mark.django_db
def test_wallet_hold_and_capture_with_release():
    tenant = Tenant.objects.create(name="Workspace Teste 2", slug="ws-teste-2")
    wallet = get_or_create_wallet(tenant)  # balance = 500

    # Hold de 300 créditos
    reservation = hold_credits(wallet, amount=300, batch=None, description="Reserva Lote Teste")
    wallet.refresh_from_db()
    assert wallet.balance == 200
    assert wallet.reserved_balance == 300
    assert wallet.available_balance == 200
    assert reservation.status == "ACTIVE"

    # Captura 180 (leads úteis) e estorna 120 (ausentes)
    cap_tx, rel_tx = capture_and_release(reservation, actual_amount=180)
    assert rel_tx is not None

    wallet.refresh_from_db()
    reservation.refresh_from_db()
    assert wallet.balance == 320  # 200 anterior + 120 liberados
    assert wallet.reserved_balance == 0
    assert wallet.available_balance == 320
    assert reservation.status == "SETTLED"
    assert reservation.captured_amount == 180
    assert reservation.released_amount == 120
    assert cap_tx.amount == -180
    assert rel_tx.amount == 120


@pytest.mark.django_db
def test_insufficient_credits_raises_error():
    tenant = Tenant.objects.create(name="Workspace Sem Saldo", slug="ws-sem-saldo")
    wallet = get_or_create_wallet(tenant)  # balance = 500

    with pytest.raises(ValidationError, match="Saldo insuficiente"):
        hold_credits(wallet, amount=600, batch=None, description="Tentativa excessiva")


@pytest.mark.django_db
def test_credit_transaction_is_append_only():
    tenant = Tenant.objects.create(name="Workspace Append Only", slug="ws-append")
    wallet = get_or_create_wallet(tenant)
    tx = deposit_credits(wallet, amount=100)

    with pytest.raises(ValidationError, match="Eventos de transação de crédito são append-only"):
        tx.amount = 999
        tx.save()

    with pytest.raises(ValidationError, match="Eventos de transação de crédito são append-only"):
        tx.delete()
