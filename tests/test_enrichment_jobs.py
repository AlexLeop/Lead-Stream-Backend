from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from leadstream.providers.enrichment_jobs import (
    create_enrichment_job,
    execute_enrichment_job,
    purge_expired_enrichment_payloads,
)
from leadstream.providers.models import EnrichmentJob
from leadstream.security.crypto import generate_api_key
from leadstream.security.models import WorkspaceRole
from leadstream.tenancy.models import Tenant
from leadstream.tenancy.services import get_internal_tenant

pytestmark = pytest.mark.django_db


def test_company_enrichment_is_durable_idempotent_and_encrypted(
    api_client: APIClient,
    django_capture_on_commit_callbacks: Any,
) -> None:
    raw_cnpj = "11222333000181"
    with (
        patch("leadstream.providers.tasks.process_enrichment_job_task.delay") as delay,
        django_capture_on_commit_callbacks(execute=True),
    ):
        response = api_client.post(
            "/api/v1/enrichment/company",
            {"query": raw_cnpj, "capabilities": ["cnpj_qsa"]},
            format="json",
            HTTP_IDEMPOTENCY_KEY="enrichment-company-001",
        )

    assert response.status_code == 202
    assert response.data["entityType"] == "COMPANY"
    assert response.data["query"] != raw_cnpj
    assert response.data["status"] == "QUEUED"
    assert delay.call_count == 1
    job_id = response.data["id"]

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT input_payload FROM leadstream_enrichment_job WHERE idempotency_key = %s",
            ["enrichment-company-001"],
        )
        raw_payload = str(cursor.fetchone()[0])
    assert raw_payload.startswith("enc:v1:")
    assert raw_cnpj not in raw_payload

    with patch("leadstream.providers.tasks.process_enrichment_job_task.delay") as second_delay:
        repeated = api_client.post(
            "/api/v1/enrichment/company",
            {"query": raw_cnpj, "capabilities": ["cnpj_qsa"]},
            format="json",
            HTTP_IDEMPOTENCY_KEY="enrichment-company-001",
        )
    assert repeated.status_code == 200
    assert repeated.data["id"] == job_id
    second_delay.assert_not_called()


def test_enrichment_job_result_is_encrypted_and_available_to_its_tenant(
    api_client: APIClient,
) -> None:
    tenant = get_internal_tenant()
    with patch("leadstream.providers.tasks.process_enrichment_job_task.delay"):
        creation = create_enrichment_job(
            tenant=tenant,
            entity_type=EnrichmentJob.EntityType.COMPANY,
            query="11222333000181",
            capabilities=["cnpj_qsa"],
            idempotency_key="enrichment-result-001",
        )

    fake_result = {
        "runId": "run-safe",
        "companyId": "company-123",
        "company": {"legalName": "Empresa Observada"},
        "sections": [],
        "costCredits": 7,
        "telefonesAtribuiveis": [{"value": "+5511999999999"}],
    }
    with patch(
        "leadstream.providers.enrichment_jobs.enrich_company_live",
        return_value=fake_result,
    ):
        completed = execute_enrichment_job(str(creation.job.pk), worker_id="worker-test")

    assert completed.status == EnrichmentJob.Status.SUCCEEDED
    assert completed.cost_credits == 7
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT result_payload FROM leadstream_enrichment_job WHERE idempotency_key = %s",
            ["enrichment-result-001"],
        )
        raw_result = str(cursor.fetchone()[0])
    assert raw_result.startswith("enc:v1:")
    assert "+5511999999999" not in raw_result

    response = api_client.get(f"/api/v1/enrichment/runs/{completed.pk}/")
    assert response.status_code == 200
    assert response.data["result"]["company"]["legalName"] == "Empresa Observada"


def test_person_job_masks_cpf_and_is_tenant_isolated(api_client: APIClient) -> None:
    tenant = get_internal_tenant()
    with patch("leadstream.providers.tasks.process_enrichment_job_task.delay"):
        creation = create_enrichment_job(
            tenant=tenant,
            entity_type=EnrichmentJob.EntityType.PERSON,
            query="52998224725",
            capabilities=["cpf_cadastral"],
            idempotency_key="enrichment-person-001",
        )

    job = creation.job
    assert job.query_label == "***.982.247-**"
    assert "52998224725" not in job.query_label

    other = Tenant.objects.create(name="Tenant sem acesso", slug="tenant-sem-acesso")
    _, raw_key = generate_api_key(
        tenant=other,
        name="Tenant isolado",
        role=WorkspaceRole.ADMIN,
    )
    other_client = APIClient()
    other_client.credentials(HTTP_X_API_KEY=raw_key)
    response = other_client.get(f"/api/v1/enrichment/runs/{job.pk}/")
    assert response.status_code == 404


def test_enrichment_job_failure_is_sanitized_and_terminal() -> None:
    tenant = get_internal_tenant()
    with patch("leadstream.providers.tasks.process_enrichment_job_task.delay"):
        creation = create_enrichment_job(
            tenant=tenant,
            entity_type=EnrichmentJob.EntityType.PERSON,
            query="52998224725",
            capabilities=["cpf_cadastral"],
            idempotency_key="enrichment-failure-001",
        )
    EnrichmentJob.objects.filter(pk=creation.job.pk).update(max_attempts=1)

    with (
        patch(
            "leadstream.providers.enrichment_jobs.enrich_person_live",
            side_effect=RuntimeError("falha contendo 52998224725"),
        ),
        pytest.raises(RuntimeError),
    ):
        execute_enrichment_job(str(creation.job.pk), worker_id="worker-failure")

    failed = EnrichmentJob.objects.get(pk=creation.job.pk)
    assert failed.status == EnrichmentJob.Status.FAILED
    assert failed.last_error_code == "RuntimeError"
    assert "52998224725" not in failed.last_error_message


def test_expired_enrichment_payloads_are_purged() -> None:
    tenant = get_internal_tenant()
    with patch("leadstream.providers.tasks.process_enrichment_job_task.delay"):
        creation = create_enrichment_job(
            tenant=tenant,
            entity_type=EnrichmentJob.EntityType.PERSON,
            query="52998224725",
            capabilities=["cpf_cadastral"],
            idempotency_key="enrichment-purge-001",
        )
    EnrichmentJob.objects.filter(pk=creation.job.pk).update(
        status=EnrichmentJob.Status.SUCCEEDED,
        result_payload={"cpf": "52998224725"},  # type: ignore[misc]
        purge_after=timezone.now() - timedelta(seconds=1),
    )

    assert purge_expired_enrichment_payloads() == 1
    purged = EnrichmentJob.objects.get(pk=creation.job.pk)
    assert purged.input_payload == {}
    assert purged.result_payload == {}
    assert purged.purged_at is not None
