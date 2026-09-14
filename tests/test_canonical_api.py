from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from leadstream.batches.models import Batch, BatchItem
from leadstream.tenancy.services import get_internal_tenant

pytestmark = pytest.mark.django_db


def test_get_canonical_lead_endpoint(api_client: APIClient) -> None:
    tenant = get_internal_tenant()
    batch = Batch.objects.create(
        tenant=tenant,
        name="Lote API Test",
        idempotency_key="batch-api-001",
    )
    item = BatchItem.objects.create(
        tenant=tenant,
        batch=batch,
        row_number=1,
        hygiene_state=BatchItem.HygieneState.CORRECTED,
        normalized_data={
            "cnpj": "48.944.179/0001-61",
            "razao_social": "ALEX LEOPOLDO DE OLIVEIRA",
            "situacao_cadastral": "ATIVA",
            "correio_eletronico": "lx.leopoldo@outlook.com",
            "ddd_telefone_1": "21996260135",
        },
    )

    response = api_client.get(
        f"/api/v1/leads/{item.id}/canonical/",
        HTTP_X_TENANT_ID=tenant.slug,
    )
    assert response.status_code == 200
    assert response.data["_meta"]["schema_version"] == "2.4.0"
    assert response.data["company"]["cnpj"] == "48.944.179/0001-61"
    assert response.data["identification"]["status"] == "OBSERVED"
    assert response.data["identification"]["lead_score"] == 0


def test_get_canonical_lead_direct_endpoint(api_client: APIClient) -> None:
    tenant = get_internal_tenant()
    batch = Batch.objects.create(
        tenant=tenant,
        name="Lote API Test 2",
        idempotency_key="batch-api-002",
    )
    item = BatchItem.objects.create(
        tenant=tenant,
        batch=batch,
        row_number=1,
        hygiene_state=BatchItem.HygieneState.CORRECTED,
        canonical_payload={
            "_meta": {"schema_version": "2.4.0", "canon_id": "canon-test"},
            "identification": {"lead_score": 90, "lead_temperature": "HOT"},
            "company": {"cnpj": "48.944.179/0001-61"},
        },
    )

    response = api_client.get(
        f"/api/v1/leads/{item.id}/",
        HTTP_X_TENANT_ID=tenant.slug,
    )
    assert response.status_code == 200
    assert response.data["_meta"]["schema_version"] == "2.4.0"
    assert response.data["company"]["cnpj"] == "48.944.179/0001-61"
