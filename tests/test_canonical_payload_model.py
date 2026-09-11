from __future__ import annotations

import pytest

from leadstream.batches.models import Batch, BatchItem
from leadstream.tenancy.services import get_internal_tenant

pytestmark = pytest.mark.django_db


def test_batch_item_has_canonical_payload_field() -> None:
    tenant = get_internal_tenant()
    batch = Batch.objects.create(
        tenant=tenant,
        name="Lote Teste Canônico",
        idempotency_key="teste-can-key-001",
    )
    item = BatchItem.objects.create(
        tenant=tenant,
        batch=batch,
        row_number=1,
        hygiene_state=BatchItem.HygieneState.UNCHANGED,
        canonical_payload={
            "_meta": {"schema_version": "2.4.0"},
            "identification": {"status": "QUALIFIED"},
        },
    )
    item.refresh_from_db()
    assert item.canonical_payload["_meta"]["schema_version"] == "2.4.0"
    assert item.canonical_payload["identification"]["status"] == "QUALIFIED"
