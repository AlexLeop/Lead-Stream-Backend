from __future__ import annotations

import pytest

from leadstream.batches.models import Batch, BatchItem
from leadstream.batches.services import refresh_batch_progress
from leadstream.billing.models import (
    CreditReservation,
    DataBlock,
    PriceBook,
    PriceRule,
)
from leadstream.billing.services import (
    get_or_create_wallet,
    hold_credits,
    record_billable_delivery,
)
from leadstream.evidence.models import EvidenceStatus
from leadstream.tenancy.models import Tenant


@pytest.mark.django_db
def test_pay_per_value_batch_settlement():
    tenant = Tenant.objects.create(name="Empresa B2B", slug="empresa-b2b")
    wallet = get_or_create_wallet(tenant)  # Saldo inicial = 500
    assert wallet.balance == 500

    # Cria lote
    batch = Batch.objects.create(
        tenant=tenant,
        name="Lote Prospeccao",
        total_rows=10,
        chunk_size=100,
    )
    # Reserva 200 créditos para o lote
    reservation = hold_credits(
        wallet=wallet,
        amount=200,
        batch=batch,
        description=f"Reserva para lote {batch.name}",
    )
    wallet.refresh_from_db()
    assert wallet.balance == 300
    assert wallet.reserved_balance == 200
    assert reservation.status == CreditReservation.Status.ACTIVE

    # Cria tabela de preços e itens
    price_book = PriceBook.objects.create(
        tenant=tenant,
        version=1,
        name="Tabela Padrão",
        effective_at=batch.created_at,
    )
    PriceRule.objects.create(
        tenant=tenant,
        price_book=price_book,
        block=DataBlock.DIRECT_EMAIL,
        unit_price_cents=15,
        minimum_confidence=80,
    )

    # Simula 3 itens entregues com sucesso e 7 ausentes
    for i in range(1, 4):
        item = BatchItem.objects.create(
            tenant=tenant,
            batch=batch,
            row_number=i,
            fingerprint=f"fp_{i}",
            status=BatchItem.Status.SUCCEEDED,
        )
        record_billable_delivery(
            tenant=tenant,
            batch=batch,
            item=item,
            block=DataBlock.DIRECT_EMAIL,
            delivered_value_fingerprint=f"val_{i}",
            evidence_status=EvidenceStatus.TECHNICALLY_VALIDATED,
            confidence=95,
        )

    for i in range(4, 11):
        BatchItem.objects.create(
            tenant=tenant,
            batch=batch,
            row_number=i,
            fingerprint=f"fp_{i}",
            status=BatchItem.Status.ABSENT,
        )

    # Ao finalizar o lote via refresh_batch_progress, liquida a reserva
    updated_batch = refresh_batch_progress(batch.id)
    assert updated_batch.status in (Batch.Status.PARTIAL, Batch.Status.COMPLETED)

    # 3 itens * 15 centavos = 45 créditos faturados.
    # Reserva foi de 200 -> 45 capturados, 155 estornados!
    wallet.refresh_from_db()
    reservation.refresh_from_db()

    assert reservation.status == CreditReservation.Status.SETTLED
    assert reservation.captured_amount == 45
    assert reservation.released_amount == 155
    assert wallet.balance == 455  # 300 restantes + 155 liberados
    assert wallet.reserved_balance == 0
