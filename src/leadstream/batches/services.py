from __future__ import annotations

import csv
import io
import logging
import math
import socket
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone

from leadstream.entities.normalization import DataValidationError
from leadstream.entities.services import create_company
from leadstream.tenancy.models import Tenant

from .hygiene import normalize_row, original_json
from .models import Batch, BatchChunk, BatchItem, ProcessingAttempt
from .storage import ChunkedUpload, delete_input, open_input, save_upload

logger = logging.getLogger(__name__)

TERMINAL_BATCH_STATUSES = {
    Batch.Status.CANCELLED,
    Batch.Status.COMPLETED,
    Batch.Status.PARTIAL,
    Batch.Status.FAILED,
}
TERMINAL_ITEM_STATUSES = {
    BatchItem.Status.SUCCEEDED,
    BatchItem.Status.ABSENT,
    BatchItem.Status.FAILED,
}


@dataclass(frozen=True)
class BatchCreation:
    batch: Batch
    created: bool


@dataclass(frozen=True)
class ChunkExecution:
    status: str
    retryable: bool = False
    retry_after_seconds: int | None = None


def _validate_idempotency_key(value: str) -> str:
    key = value.strip()
    if len(key) < 8 or len(key) > 128:
        raise ValidationError({"Idempotency-Key": "Informe uma chave entre 8 e 128 caracteres."})
    return key


def _publish_ingestion(batch_id: UUID | str) -> None:
    from .tasks import ingest_batch_task

    try:
        ingest_batch_task.delay(str(batch_id))
    except Exception:
        logger.exception("batch_ingestion_dispatch_failed", extra={"batch_id": str(batch_id)})


def _publish_chunk(chunk_id: UUID | str) -> None:
    from leadstream.providers.tasks import process_enrichment_chunk_task

    from .tasks import process_chunk_task

    chunk = BatchChunk.objects.filter(pk=chunk_id).values("stage", "status").first()
    if chunk is None or chunk["status"] != BatchChunk.Status.PENDING:
        return
    BatchChunk.objects.filter(pk=chunk_id).update(dispatched_at=timezone.now())
    try:
        if chunk["stage"] == BatchChunk.Stage.ENRICHMENT:
            process_enrichment_chunk_task.delay(str(chunk_id))
        else:
            process_chunk_task.delay(str(chunk_id))
    except Exception:
        BatchChunk.objects.filter(pk=chunk_id, status=BatchChunk.Status.PENDING).update(
            dispatched_at=None
        )
        logger.exception("batch_chunk_dispatch_failed", extra={"chunk_id": str(chunk_id)})


def _publish_chunks(chunk_ids: list[UUID]) -> None:
    for chunk_id in chunk_ids:
        _publish_chunk(chunk_id)


def _publish_ingestions(batch_ids: list[UUID]) -> None:
    for batch_id in batch_ids:
        _publish_ingestion(batch_id)


def create_csv_batch(
    *,
    tenant: Tenant,
    name: str,
    upload: ChunkedUpload,
    idempotency_key: str,
    chunk_size: int = 500,
) -> BatchCreation:
    key = _validate_idempotency_key(idempotency_key)
    if chunk_size < 50 or chunk_size > 5000:
        raise ValidationError({"chunk_size": "Use um tamanho entre 50 e 5.000."})
    existing = Batch.objects.filter(tenant=tenant, idempotency_key=key).first()
    if existing is not None:
        return BatchCreation(batch=existing, created=False)
    stored = save_upload(tenant_id=tenant.pk, upload=upload)
    try:
        with transaction.atomic():
            batch = Batch.objects.create(
                tenant=tenant,
                name=" ".join(name.split())[:160] or Path(stored.original_name).stem[:160],
                source_type=Batch.SourceType.CSV,
                status=Batch.Status.RECEIVED,
                idempotency_key=key,
                input_backend=stored.backend,
                input_key=stored.key,
                input_original_name=stored.original_name,
                input_content_type=stored.content_type,
                input_size_bytes=stored.size_bytes,
                input_sha256=stored.sha256,
                chunk_size=chunk_size,
            )
            transaction.on_commit(lambda: _publish_ingestion(batch.pk))
    except IntegrityError:
        delete_input(stored.key)
        existing = Batch.objects.get(tenant=tenant, idempotency_key=key)
        return BatchCreation(batch=existing, created=False)
    return BatchCreation(batch=batch, created=True)


def _dialect(sample: str) -> type[csv.Dialect]:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        return csv.excel


def _terminal_item_for_result(result_state: str) -> tuple[str, str, str]:
    if result_state == BatchItem.HygieneState.INVALID:
        return BatchItem.Status.FAILED, "INVALID_INPUT", "Registro inválido para processamento."
    if result_state == BatchItem.HygieneState.DUPLICATE:
        return BatchItem.Status.SUCCEEDED, "", ""
    return BatchItem.Status.PENDING, "", ""


def _parse_and_store_items(batch: Batch) -> tuple[int, int, int, int]:
    seen: dict[str, UUID] = {}
    buffer: list[BatchItem] = []
    total = corrected = invalid = duplicates = 0
    with open_input(batch.input_key) as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
        sample = text.read(8192)
        if not sample.strip():
            raise ValidationError("Arquivo CSV sem conteúdo legível.")
        text.seek(0)
        reader = csv.DictReader(text, dialect=_dialect(sample))
        if not reader.fieldnames:
            raise ValidationError("Arquivo CSV sem cabeçalho.")
        for row_number, raw_row in enumerate(reader, start=2):
            total += 1
            if total > settings.BATCH_MAX_ROWS:
                raise ValidationError(
                    f"O arquivo excede o limite de {settings.BATCH_MAX_ROWS:,} registros."
                )
            original = original_json(raw_row)
            result = normalize_row(original)
            state = result.state
            duplicate_of_id: UUID | None = None
            if result.fingerprint and result.fingerprint in seen:
                state = BatchItem.HygieneState.DUPLICATE
                duplicate_of_id = seen[result.fingerprint]
                duplicates += 1
            status, error_code, error_message = _terminal_item_for_result(state)
            item = BatchItem(
                tenant=batch.tenant,
                batch=batch,
                row_number=row_number,
                original_data=original,
                normalized_data=result.normalized,
                hygiene_state=state,
                applied_rules=result.rules,
                issues=result.issues,
                fingerprint=result.fingerprint,
                duplicate_of_id=duplicate_of_id,
                status=status,
                error_code=error_code,
                error_message=error_message,
                processed_at=timezone.now() if status in TERMINAL_ITEM_STATUSES else None,
            )
            if result.fingerprint and duplicate_of_id is None:
                seen[result.fingerprint] = item.id
            if state == BatchItem.HygieneState.CORRECTED:
                corrected += 1
            elif state == BatchItem.HygieneState.INVALID:
                invalid += 1
            buffer.append(item)
            if len(buffer) >= 1000:
                BatchItem.objects.bulk_create(buffer, batch_size=1000)
                buffer.clear()
        if buffer:
            BatchItem.objects.bulk_create(buffer, batch_size=1000)
    if total == 0:
        raise ValidationError("O CSV contém cabeçalho, mas nenhuma linha de dados.")
    return total, corrected, invalid, duplicates


@transaction.atomic
def ingest_batch(batch_id: UUID | str) -> Batch:
    batch = Batch.objects.select_for_update().select_related("tenant").get(pk=batch_id)
    if batch.status in TERMINAL_BATCH_STATUSES or batch.status == Batch.Status.PAUSED:
        return batch
    if batch.items.exists():
        if batch.chunks.filter(status=BatchChunk.Status.PENDING).exists():
            chunk_ids = list(
                batch.chunks.filter(status=BatchChunk.Status.PENDING).values_list("pk", flat=True)
            )
            transaction.on_commit(lambda: _publish_chunks(chunk_ids))
        return batch
    batch.status = Batch.Status.INGESTING
    batch.started_at = batch.started_at or timezone.now()
    batch.save(update_fields=("status", "started_at", "updated_at"))
    try:
        with transaction.atomic():
            total, corrected, invalid, duplicates = _parse_and_store_items(batch)
    except (UnicodeError, csv.Error, DataValidationError, ValidationError) as exc:
        batch.status = Batch.Status.FAILED
        batch.last_error_code = "INVALID_CSV"
        batch.last_error_message = str(exc)[:500]
        batch.completed_at = timezone.now()
        batch.save(
            update_fields=(
                "status",
                "last_error_code",
                "last_error_message",
                "completed_at",
                "updated_at",
            )
        )
        return batch
    pending_rows = list(
        batch.items.filter(status=BatchItem.Status.PENDING)
        .order_by("row_number")
        .values_list("row_number", flat=True)
    )
    chunks: list[BatchChunk] = []
    for index in range(0, len(pending_rows), batch.chunk_size):
        rows = pending_rows[index : index + batch.chunk_size]
        chunks.append(
            BatchChunk(
                tenant=batch.tenant,
                batch=batch,
                sequence=(index // batch.chunk_size) + 1,
                start_row=rows[0],
                end_row=rows[-1],
                checkpoint_row=rows[0] - 1,
            )
        )
    BatchChunk.objects.bulk_create(chunks, batch_size=500)
    batch.total_rows = total
    batch.processed_rows = invalid + duplicates
    batch.succeeded_rows = duplicates
    batch.failed_rows = invalid
    batch.duplicate_rows = duplicates
    batch.corrected_rows = corrected
    batch.invalid_rows = invalid
    batch.current_stage = "HYGIENE"
    if chunks:
        batch.status = Batch.Status.QUEUED
    elif invalid == total:
        batch.status = Batch.Status.FAILED
        batch.completed_at = timezone.now()
    else:
        batch.status = Batch.Status.COMPLETED
        batch.completed_at = timezone.now()
    batch.save()
    chunk_ids = [chunk.pk for chunk in chunks]
    transaction.on_commit(lambda: _publish_chunks(chunk_ids))
    return batch


@transaction.atomic
def claim_chunk(
    *, chunk_id: UUID | str, worker_id: str
) -> tuple[BatchChunk, ProcessingAttempt] | None:
    now = timezone.now()
    chunk = BatchChunk.objects.select_for_update().select_related("batch").get(pk=chunk_id)
    if chunk.status in {BatchChunk.Status.COMPLETED, BatchChunk.Status.CANCELLED}:
        return None
    if chunk.batch.status == Batch.Status.PAUSED:
        chunk.status = BatchChunk.Status.PAUSED
        chunk.save(update_fields=("status", "updated_at"))
        return None
    if chunk.batch.status in {Batch.Status.CANCEL_REQUESTED, Batch.Status.CANCELLED}:
        chunk.status = BatchChunk.Status.CANCELLED
        chunk.completed_at = now
        chunk.save(update_fields=("status", "completed_at", "updated_at"))
        return None
    if chunk.leased_until and chunk.leased_until > now and chunk.lease_owner != worker_id:
        return None
    if chunk.attempt_count >= chunk.max_attempts:
        chunk.status = BatchChunk.Status.FAILED
        chunk.completed_at = now
        chunk.save(update_fields=("status", "completed_at", "updated_at"))
        return None
    chunk.attempt_count += 1
    chunk.status = BatchChunk.Status.RUNNING
    chunk.lease_owner = worker_id[:255]
    chunk.leased_until = now + timedelta(seconds=settings.BATCH_LEASE_SECONDS)
    chunk.dispatched_at = chunk.dispatched_at or now
    chunk.started_at = chunk.started_at or now
    chunk.save()
    attempt = ProcessingAttempt.objects.create(
        tenant=chunk.tenant,
        chunk=chunk,
        attempt_number=chunk.attempt_count,
        worker_id=worker_id[:255],
        started_at=now,
    )
    Batch.objects.filter(pk=chunk.batch_id, status=Batch.Status.QUEUED).update(
        status=Batch.Status.RUNNING,
        current_stage=chunk.stage,
    )
    return chunk, attempt


@transaction.atomic
def _process_item(item_id: UUID | str) -> str:
    item = BatchItem.objects.select_for_update().select_related("batch", "tenant").get(pk=item_id)
    if item.status in TERMINAL_ITEM_STATUSES:
        return item.status
    item.status = BatchItem.Status.PROCESSING
    item.save(update_fields=("status", "updated_at"))
    try:
        cnpj = item.normalized_data.get("cnpj", "")
        if cnpj:
            identity = create_company(
                tenant=item.tenant,
                cnpj=cnpj,
                legal_name=item.normalized_data.get("legal_name") or f"Empresa {cnpj}",
                trade_name=item.normalized_data.get("trade_name", ""),
            )
            item.entity = identity.company.entity
            item.status = BatchItem.Status.SUCCEEDED
        else:
            item.status = BatchItem.Status.ABSENT
            item.error_code = "CNPJ_ABSENT"
            item.error_message = "Registro higienizado, mas sem CNPJ para correlação empresarial."
    except (DataValidationError, ValidationError, IntegrityError) as exc:
        item.status = BatchItem.Status.FAILED
        item.error_code = "PROCESSING_ERROR"
        item.error_message = str(exc)[:500]
    item.processed_at = timezone.now()
    item.save()
    return item.status


@transaction.atomic
def refresh_batch_progress(batch_id: UUID | str) -> Batch:
    batch = Batch.objects.select_for_update().get(pk=batch_id)
    counts = {
        row["status"]: row["count"]
        for row in batch.items.values("status").annotate(count=Count("id"))
    }
    batch.succeeded_rows = counts.get(BatchItem.Status.SUCCEEDED, 0)
    batch.absent_rows = counts.get(BatchItem.Status.ABSENT, 0)
    batch.failed_rows = counts.get(BatchItem.Status.FAILED, 0)
    batch.processed_rows = sum(counts.get(status, 0) for status in TERMINAL_ITEM_STATUSES)
    active_chunks = batch.chunks.filter(
        status__in=(BatchChunk.Status.PENDING, BatchChunk.Status.RUNNING, BatchChunk.Status.LEASED)
    ).exists()
    if not active_chunks:
        if batch.status == Batch.Status.CANCEL_REQUESTED:
            batch.status = Batch.Status.CANCELLED
        elif batch.status == Batch.Status.PAUSED:
            batch.save()
            return batch
        elif batch.failed_rows == batch.total_rows:
            batch.status = Batch.Status.FAILED
        elif batch.failed_rows or batch.absent_rows:
            batch.status = Batch.Status.PARTIAL
        else:
            batch.status = Batch.Status.COMPLETED
        batch.completed_at = timezone.now()

        from django.db.models import Sum
        from django.db.models.functions import Coalesce

        from leadstream.billing.models import BillableEvent, CreditReservation
        from leadstream.billing.services import capture_and_release

        active_res = CreditReservation.objects.filter(
            batch=batch, status=CreditReservation.Status.ACTIVE
        ).first()
        if active_res:
            actual_delivered = BillableEvent.objects.filter(batch=batch).aggregate(
                total=Coalesce(Sum("unit_price_cents"), 0)
            )["total"]
            capture_and_release(active_res, actual_delivered)

    batch.save()
    return batch


def process_chunk(*, chunk_id: UUID | str, worker_id: str | None = None) -> ChunkExecution:
    claimed = claim_chunk(chunk_id=chunk_id, worker_id=worker_id or socket.gethostname())
    if claimed is None:
        return ChunkExecution(status="SKIPPED")
    chunk, attempt = claimed
    try:
        item_ids = list(
            BatchItem.objects.filter(
                batch_id=chunk.batch_id,
                row_number__gte=max(chunk.start_row, chunk.checkpoint_row + 1),
                row_number__lte=chunk.end_row,
                status=BatchItem.Status.PENDING,
            )
            .order_by("row_number")
            .values_list("pk", flat=True)
        )
        for item_id in item_ids:
            batch_status = Batch.objects.values_list("status", flat=True).get(pk=chunk.batch_id)
            if batch_status in {Batch.Status.PAUSED, Batch.Status.CANCEL_REQUESTED}:
                with transaction.atomic():
                    locked = BatchChunk.objects.select_for_update().get(pk=chunk.pk)
                    locked.status = (
                        BatchChunk.Status.PAUSED
                        if batch_status == Batch.Status.PAUSED
                        else BatchChunk.Status.CANCELLED
                    )
                    locked.leased_until = None
                    locked.lease_owner = ""
                    locked.save()
                refresh_batch_progress(chunk.batch_id)
                return ChunkExecution(status=locked.status)
            _process_item(item_id)
            row_number = BatchItem.objects.values_list("row_number", flat=True).get(pk=item_id)
            BatchChunk.objects.filter(pk=chunk.pk).update(
                checkpoint_row=row_number,
                leased_until=timezone.now() + timedelta(seconds=settings.BATCH_LEASE_SECONDS),
            )
        with transaction.atomic():
            locked_chunk = BatchChunk.objects.select_for_update().get(pk=chunk.pk)
            locked_chunk.status = BatchChunk.Status.COMPLETED
            locked_chunk.lease_owner = ""
            locked_chunk.leased_until = None
            locked_chunk.dispatched_at = None
            locked_chunk.completed_at = timezone.now()
            locked_chunk.save()
            attempt.status = ProcessingAttempt.Status.SUCCEEDED
            attempt.finished_at = timezone.now()
            attempt.save(update_fields=("status", "finished_at"))
        refresh_batch_progress(chunk.batch_id)
        return ChunkExecution(status=BatchChunk.Status.COMPLETED)
    except Exception as exc:  # noqa: BLE001 -- fronteira do worker registra e agenda retry
        with transaction.atomic():
            locked_chunk = BatchChunk.objects.select_for_update().get(pk=chunk.pk)
            retryable = locked_chunk.attempt_count < locked_chunk.max_attempts
            locked_chunk.status = (
                BatchChunk.Status.PENDING if retryable else BatchChunk.Status.FAILED
            )
            locked_chunk.lease_owner = ""
            locked_chunk.leased_until = None
            locked_chunk.last_error_code = "CHUNK_ERROR"
            locked_chunk.last_error_message = str(exc)[:500]
            locked_chunk.save()
            if not retryable:
                BatchItem.objects.filter(
                    batch_id=chunk.batch_id,
                    row_number__gte=locked_chunk.checkpoint_row + 1,
                    row_number__lte=locked_chunk.end_row,
                    status__in=(BatchItem.Status.PENDING, BatchItem.Status.PROCESSING),
                ).update(
                    status=BatchItem.Status.FAILED,
                    error_code="CHUNK_FAILED",
                    error_message="Chunk excedeu o limite de tentativas.",
                    processed_at=timezone.now(),
                )
            attempt.status = (
                ProcessingAttempt.Status.RETRYABLE_FAILURE
                if retryable
                else ProcessingAttempt.Status.PERMANENT_FAILURE
            )
            attempt.error_code = "CHUNK_ERROR"
            attempt.error_message = str(exc)[:500]
            attempt.finished_at = timezone.now()
            attempt.save()
        refresh_batch_progress(chunk.batch_id)
        return ChunkExecution(status=BatchChunk.Status.FAILED, retryable=retryable)


@transaction.atomic
def pause_batch(*, tenant: Tenant, batch_id: UUID | str) -> Batch:
    batch = Batch.objects.select_for_update().get(pk=batch_id, tenant=tenant)
    if batch.status in TERMINAL_BATCH_STATUSES:
        raise ValidationError("Lote concluído não pode ser pausado.")
    batch.status = Batch.Status.PAUSED
    batch.save(update_fields=("status", "updated_at"))
    batch.chunks.filter(status=BatchChunk.Status.PENDING).update(status=BatchChunk.Status.PAUSED)
    return batch


@transaction.atomic
def resume_batch(*, tenant: Tenant, batch_id: UUID | str) -> Batch:
    batch = Batch.objects.select_for_update().get(pk=batch_id, tenant=tenant)
    if batch.status != Batch.Status.PAUSED:
        raise ValidationError("Somente lote pausado pode ser retomado.")
    if not batch.items.exists():
        batch.status = Batch.Status.RECEIVED
        batch.save(update_fields=("status", "updated_at"))
        transaction.on_commit(lambda: _publish_ingestion(batch.pk))
        return batch
    batch.status = Batch.Status.QUEUED
    batch.save(update_fields=("status", "updated_at"))
    batch.chunks.filter(status=BatchChunk.Status.PAUSED).update(status=BatchChunk.Status.PENDING)
    batch.chunks.filter(status=BatchChunk.Status.PENDING).update(dispatched_at=None)
    ids = list(batch.chunks.filter(status=BatchChunk.Status.PENDING).values_list("pk", flat=True))
    transaction.on_commit(lambda: _publish_chunks(ids))
    return batch


@transaction.atomic
def cancel_batch(*, tenant: Tenant, batch_id: UUID | str) -> Batch:
    batch = Batch.objects.select_for_update().get(pk=batch_id, tenant=tenant)
    if batch.status in TERMINAL_BATCH_STATUSES:
        return batch
    running = batch.chunks.filter(status=BatchChunk.Status.RUNNING).exists()
    batch.status = Batch.Status.CANCEL_REQUESTED if running else Batch.Status.CANCELLED
    if not running:
        batch.completed_at = timezone.now()
    batch.save(update_fields=("status", "completed_at", "updated_at"))
    batch.chunks.filter(status__in=(BatchChunk.Status.PENDING, BatchChunk.Status.PAUSED)).update(
        status=BatchChunk.Status.CANCELLED,
        completed_at=timezone.now(),
    )
    return batch


def batch_eta_seconds(batch: Batch) -> int | None:
    if (
        not batch.started_at
        or batch.processed_rows == 0
        or batch.processed_rows >= batch.total_rows
    ):
        return None
    elapsed = max((timezone.now() - batch.started_at).total_seconds(), 1)
    rate = batch.processed_rows / elapsed
    return math.ceil((batch.total_rows - batch.processed_rows) / rate)


@transaction.atomic
def recover_stalled_work(*, now: datetime | None = None) -> dict[str, int]:
    check_time = now or timezone.now()
    dispatch_cutoff = check_time - timedelta(minutes=5)
    expired_chunks = list(
        BatchChunk.objects.select_for_update()
        .filter(
            status=BatchChunk.Status.RUNNING,
            leased_until__isnull=False,
            leased_until__lte=check_time,
        )
        .exclude(batch__status__in=TERMINAL_BATCH_STATUSES)
    )
    for chunk in expired_chunks:
        ProcessingAttempt.objects.filter(
            chunk=chunk, status=ProcessingAttempt.Status.STARTED
        ).update(status=ProcessingAttempt.Status.ABANDONED, finished_at=check_time)
        chunk.status = BatchChunk.Status.PENDING
        chunk.lease_owner = ""
        chunk.leased_until = None
        chunk.dispatched_at = None
        chunk.save()
    ingestion_ids = list(
        Batch.objects.filter(status=Batch.Status.RECEIVED).values_list("pk", flat=True)
    )
    pending_ids = list(
        BatchChunk.objects.filter(
            status=BatchChunk.Status.PENDING,
            batch__status__in=(Batch.Status.QUEUED, Batch.Status.RUNNING),
        )
        .filter(Q(dispatched_at__isnull=True) | Q(dispatched_at__lte=dispatch_cutoff))
        .values_list("pk", flat=True)
    )
    transaction.on_commit(lambda: _publish_ingestions(ingestion_ids))
    transaction.on_commit(lambda: _publish_chunks(pending_ids))
    return {
        "ingestions_requeued": len(ingestion_ids),
        "chunks_recovered": len(expired_chunks),
        "chunks_requeued": len(pending_ids),
    }
