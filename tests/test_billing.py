from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction

from leadstream.batches.models import Batch, BatchItem
from leadstream.billing.models import BillableEvent, DataBlock, ProviderCall
from leadstream.billing.services import (
    create_price_book,
    ensure_default_price_book,
    finalize_provider_call,
    record_billable_delivery,
    register_provider_call,
)
from leadstream.entities.normalization import fingerprint_value
from leadstream.evidence.models import EvidenceStatus
from leadstream.tenancy.services import get_internal_tenant

pytestmark = pytest.mark.django_db


def make_batch_item() -> tuple[Batch, BatchItem]:
    tenant = get_internal_tenant()
    batch = Batch.objects.create(
        tenant=tenant,
        name="Lote financeiro",
        source_type=Batch.SourceType.CSV,
        status=Batch.Status.COMPLETED,
        idempotency_key="billing-batch-001",
        total_rows=1,
        processed_rows=1,
        succeeded_rows=1,
    )
    item = BatchItem.objects.create(
        tenant=tenant,
        batch=batch,
        row_number=2,
        original_data={"CNPJ": "04.252.011/0001-10"},
        normalized_data={"cnpj": "04252011000110"},
        hygiene_state=BatchItem.HygieneState.CORRECTED,
        applied_rules=["NORMALIZE_CNPJ"],
        fingerprint=fingerprint_value(("cnpj", "04252011000110")),
        status=BatchItem.Status.SUCCEEDED,
    )
    return batch, item


def test_tabela_padrao_totaliza_oitenta_centavos(api_client: object) -> None:
    tenant = get_internal_tenant()
    book = ensure_default_price_book(tenant)
    assert book.rules.count() == 10
    assert sum(book.rules.values_list("unit_price_cents", flat=True)) == 80

    response = api_client.get("/api/v1/precos/")  # type: ignore[attr-defined]
    assert response.status_code == 200
    assert response.json()[0]["total_unit_price_cents"] == 80


def test_custo_e_cobranca_sao_idempotentes_e_apenas_por_entrega_util(
    api_client: object,
) -> None:
    tenant = get_internal_tenant()
    batch, item = make_batch_item()
    call = register_provider_call(
        tenant=tenant,
        batch=batch,
        item=item,
        provider="fixture-provider",
        operation="validate_company",
        block=DataBlock.HYGIENE,
        idempotency_key="provider-call-001",
        estimated_cost_cents=16,
    )
    same_call = register_provider_call(
        tenant=tenant,
        batch=batch,
        item=item,
        provider="fixture-provider",
        operation="validate_company",
        block=DataBlock.HYGIENE,
        idempotency_key="provider-call-001",
        estimated_cost_cents=16,
    )
    assert same_call.pk == call.pk
    finalized = finalize_provider_call(
        call=call,
        status=ProviderCall.Status.SUCCEEDED,
        confirmed_cost_cents=16,
    )
    replay = finalize_provider_call(
        call=call,
        status=ProviderCall.Status.SUCCEEDED,
        confirmed_cost_cents=16,
    )
    assert replay.pk == finalized.pk

    fingerprint = fingerprint_value(item.normalized_data)
    event = record_billable_delivery(
        tenant=tenant,
        batch=batch,
        item=item,
        block=DataBlock.HYGIENE,
        delivered_value_fingerprint=fingerprint,
        evidence_status=EvidenceStatus.TECHNICALLY_VALIDATED,
        confidence=100,
    )
    duplicate = record_billable_delivery(
        tenant=tenant,
        batch=batch,
        item=item,
        block=DataBlock.HYGIENE,
        delivered_value_fingerprint=fingerprint,
        evidence_status=EvidenceStatus.TECHNICALLY_VALIDATED,
        confidence=100,
    )
    assert event is not None
    assert duplicate is not None
    assert duplicate.pk == event.pk
    assert BillableEvent.objects.count() == 1
    assert event.unit_price_cents == 6

    not_billable = record_billable_delivery(
        tenant=tenant,
        batch=batch,
        item=item,
        block=DataBlock.DIRECT_EMAIL,
        delivered_value_fingerprint=fingerprint_value("ausente"),
        evidence_status=EvidenceStatus.ABSENT,
        confidence=100,
    )
    assert not_billable is None

    report = api_client.get(  # type: ignore[attr-defined]
        f"/api/v1/lotes/{batch.pk}/financeiro/"
    )
    assert report.status_code == 200
    payload = report.json()
    assert payload["cost_cents"] == 16
    assert payload["revenue_cents"] == 6
    assert payload["gross_profit_cents"] == -10
    assert payload["billable_deliveries"] == 1
    assert payload["coverage_percent"] == 100.0


def test_historico_de_preco_nao_altera_evento_e_ledger_e_append_only() -> None:
    tenant = get_internal_tenant()
    batch, item = make_batch_item()
    ensure_default_price_book(tenant)
    event = record_billable_delivery(
        tenant=tenant,
        batch=batch,
        item=item,
        block=DataBlock.HYGIENE,
        delivered_value_fingerprint=fingerprint_value("v1"),
        evidence_status=EvidenceStatus.TECHNICALLY_VALIDATED,
        confidence=100,
    )
    assert event is not None
    create_price_book(
        tenant=tenant,
        name="Nova tabela",
        rules=[
            {
                "block": DataBlock.HYGIENE,
                "unit_price_cents": 20,
                "minimum_confidence": 100,
                "refresh_window_days": 1,
            }
        ],
    )
    event.refresh_from_db()
    assert event.unit_price_cents == 6
    with pytest.raises(ValidationError, match="append-only"):
        event.unit_price_cents = 99
        event.save()
    with pytest.raises(ValidationError, match="append-only"):
        BillableEvent.objects.filter(pk=event.pk).delete()


def test_trigger_postgresql_bloqueia_mutacao_financeira_direta() -> None:
    if connection.vendor != "postgresql":
        pytest.skip("Trigger é validado pela CI com PostgreSQL.")
    tenant = get_internal_tenant()
    batch, item = make_batch_item()
    ensure_default_price_book(tenant)
    event = record_billable_delivery(
        tenant=tenant,
        batch=batch,
        item=item,
        block=DataBlock.HYGIENE,
        delivered_value_fingerprint=fingerprint_value("imutavel"),
        evidence_status=EvidenceStatus.TECHNICALLY_VALIDATED,
        confidence=100,
    )
    assert event is not None
    with pytest.raises(DatabaseError, match="append-only"), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE leadstream_billable_event SET unit_price_cents = 99 WHERE id = %s",
                [event.pk],
            )
