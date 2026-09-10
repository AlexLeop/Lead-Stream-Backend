from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from leadstream.batches.models import Batch, BatchChunk, BatchItem, ProcessingAttempt
from leadstream.batches.services import ingest_batch, process_chunk, recover_stalled_work
from leadstream.tenancy.services import get_internal_tenant

pytestmark = pytest.mark.django_db


CSV_CONTENT = """CNPJ;Razão Social;E-mail
04.252.011/0001-10;Empresa Exemplo;CONTATO@EXAMPLE.COM
04252011000110;Empresa Exemplo duplicada;contato@example.com
00.000.000/0000-00;Empresa Inválida;invalido@example.com
;Lead sem CNPJ;pessoa@example.com
""".encode()


def upload_csv(client: APIClient, *, key: str) -> Any:
    return client.post(
        "/api/v1/lotes/",
        {
            "name": "Base comercial",
            "chunk_size": 50,
            "arquivo": SimpleUploadedFile("leads.csv", CSV_CONTENT, content_type="text/csv"),
        },
        format="multipart",
        HTTP_IDEMPOTENCY_KEY=key,
    )


def test_upload_retorna_202_e_processamento_e_retomavel(
    api_client: APIClient,
    tmp_path: Path,
    settings: object,
    django_capture_on_commit_callbacks: object,
) -> None:
    settings.BATCH_STORAGE_ROOT = tmp_path  # type: ignore[attr-defined]
    with patch("leadstream.batches.tasks.ingest_batch_task.delay") as enqueue:
        with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
            response = upload_csv(api_client, key="upload-lote-001")
    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == Batch.Status.RECEIVED
    assert enqueue.call_count == 1

    batch = ingest_batch(payload["id"])
    assert batch.status == Batch.Status.QUEUED
    assert batch.total_rows == 4
    assert batch.corrected_rows >= 1
    assert batch.duplicate_rows == 1
    assert batch.invalid_rows == 1
    assert batch.chunks.count() == 1

    chunk = batch.chunks.get()
    result = process_chunk(chunk_id=chunk.pk, worker_id="worker-test")
    assert result.status == BatchChunk.Status.COMPLETED
    batch.refresh_from_db()
    assert batch.status == Batch.Status.PARTIAL
    assert batch.processed_rows == 4
    assert batch.succeeded_rows == 2
    assert batch.absent_rows == 1
    assert batch.failed_rows == 1
    assert batch.items.filter(entity__isnull=False).count() == 1

    replay = process_chunk(chunk_id=chunk.pk, worker_id="worker-replay")
    assert replay.status == "SKIPPED"
    chunk.refresh_from_db()
    assert chunk.attempt_count == 1
    assert chunk.attempts.count() == 1

    detail = api_client.get(f"/api/v1/lotes/{batch.pk}/")
    assert detail.status_code == 200
    assert detail.json()["progress_percent"] == 100.0
    items = api_client.get(f"/api/v1/lotes/{batch.pk}/itens/?page_size=100")
    assert items.status_code == 200
    assert items.json()["count"] == 4


def test_upload_idempotente_nao_cria_lote_ou_arquivo_novo(
    api_client: APIClient,
    tmp_path: Path,
    settings: object,
    django_capture_on_commit_callbacks: object,
) -> None:
    settings.BATCH_STORAGE_ROOT = tmp_path  # type: ignore[attr-defined]
    with patch("leadstream.batches.tasks.ingest_batch_task.delay"):
        with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
            first = upload_csv(api_client, key="upload-lote-idempotente")
        second = upload_csv(api_client, key="upload-lote-idempotente")
    assert first.status_code == 202
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert Batch.objects.count() == 1
    assert len(list(tmp_path.rglob("*.csv"))) == 1


def test_pausa_retomada_e_cancelamento_preservam_checkpoint(
    api_client: APIClient,
    tmp_path: Path,
    settings: object,
    django_capture_on_commit_callbacks: object,
) -> None:
    settings.BATCH_STORAGE_ROOT = tmp_path  # type: ignore[attr-defined]
    with patch("leadstream.batches.tasks.ingest_batch_task.delay"):
        with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
            response = upload_csv(api_client, key="upload-lote-controle")
    batch = ingest_batch(response.json()["id"])
    chunk = batch.chunks.get()
    checkpoint = chunk.checkpoint_row

    paused = api_client.post(f"/api/v1/lotes/{batch.pk}/pausar/")
    assert paused.status_code == 200
    assert paused.json()["status"] == Batch.Status.PAUSED

    with patch("leadstream.batches.tasks.process_chunk_task.delay") as enqueue:
        with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
            resumed = api_client.post(f"/api/v1/lotes/{batch.pk}/retomar/")
    assert resumed.status_code == 200
    assert resumed.json()["status"] == Batch.Status.QUEUED
    assert enqueue.call_count == 1

    cancelled = api_client.post(f"/api/v1/lotes/{batch.pk}/cancelar/")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == Batch.Status.CANCELLED
    chunk.refresh_from_db()
    assert chunk.status == BatchChunk.Status.CANCELLED
    assert chunk.checkpoint_row == checkpoint
    assert BatchItem.objects.filter(batch=batch, status=BatchItem.Status.PENDING).exists()


def test_scanner_recupera_lease_expirado_e_ingestao_sem_despacho(
    django_capture_on_commit_callbacks: object,
) -> None:
    tenant = get_internal_tenant()
    received = Batch.objects.create(
        tenant=tenant,
        name="Recebido sem broker",
        source_type=Batch.SourceType.CSV,
        status=Batch.Status.RECEIVED,
        idempotency_key="recover-received-001",
    )
    running = Batch.objects.create(
        tenant=tenant,
        name="Worker interrompido",
        source_type=Batch.SourceType.CSV,
        status=Batch.Status.RUNNING,
        idempotency_key="recover-running-001",
        total_rows=1,
    )
    chunk = BatchChunk.objects.create(
        tenant=tenant,
        batch=running,
        sequence=1,
        start_row=2,
        end_row=2,
        status=BatchChunk.Status.RUNNING,
        lease_owner="worker-morto",
        leased_until=timezone.now() - timedelta(seconds=1),
        attempt_count=1,
    )
    attempt = ProcessingAttempt.objects.create(
        tenant=tenant,
        chunk=chunk,
        attempt_number=1,
        worker_id="worker-morto",
        status=ProcessingAttempt.Status.STARTED,
        started_at=timezone.now() - timedelta(minutes=10),
    )

    with (
        patch("leadstream.batches.tasks.ingest_batch_task.delay") as ingest_enqueue,
        patch("leadstream.batches.tasks.process_chunk_task.delay") as chunk_enqueue,
    ):
        with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
            result = recover_stalled_work()

    assert result == {
        "ingestions_requeued": 1,
        "chunks_recovered": 1,
        "chunks_requeued": 1,
    }
    ingest_enqueue.assert_called_once_with(str(received.pk))
    chunk_enqueue.assert_called_once_with(str(chunk.pk))
    chunk.refresh_from_db()
    attempt.refresh_from_db()
    assert chunk.status == BatchChunk.Status.PENDING
    assert chunk.lease_owner == ""
    assert chunk.dispatched_at is not None
    assert attempt.status == ProcessingAttempt.Status.ABANDONED
