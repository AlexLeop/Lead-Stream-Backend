from __future__ import annotations

import socket
from datetime import timedelta
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from leadstream.batches.models import Batch, BatchChunk, BatchItem, ProcessingAttempt
from leadstream.batches.services import ChunkExecution, _publish_chunks, claim_chunk
from leadstream.billing.models import DataBlock
from leadstream.tenancy.models import Tenant

from .orchestrator import DEFAULT_BLOCKS, run_enrichment_cascade


def _validate_blocks(blocks: frozenset[str]) -> frozenset[str]:
    allowed = {choice for choice, _ in DataBlock.choices}
    invalid = blocks.difference(allowed)
    if invalid:
        raise ValidationError({"blocks": f"Blocos inválidos: {', '.join(sorted(invalid))}."})
    return blocks


@transaction.atomic
def start_batch_enrichment(
    *,
    tenant: Tenant,
    batch_id: UUID | str,
    requested_blocks: frozenset[str] = DEFAULT_BLOCKS,
) -> Batch:
    blocks = _validate_blocks(requested_blocks)
    batch = Batch.objects.select_for_update().get(pk=batch_id, tenant=tenant)
    if batch.status in {Batch.Status.CANCELLED, Batch.Status.FAILED}:
        raise ValidationError("Lote cancelado ou inválido não pode ser enriquecido.")
    existing = batch.chunks.filter(stage=BatchChunk.Stage.ENRICHMENT)
    if existing.exists():
        ids = list(existing.filter(status=BatchChunk.Status.PENDING).values_list("pk", flat=True))
        transaction.on_commit(lambda: _publish_chunks(ids))
        return batch
    rows = list(
        batch.items.filter(status=BatchItem.Status.SUCCEEDED, entity__isnull=False)
        .order_by("row_number")
        .values_list("row_number", flat=True)
    )
    if not rows:
        raise ValidationError("Lote não possui empresas elegíveis para enriquecimento.")
    chunks: list[BatchChunk] = []
    for index in range(0, len(rows), batch.chunk_size):
        group = rows[index : index + batch.chunk_size]
        chunks.append(
            BatchChunk(
                tenant=tenant,
                batch=batch,
                stage=BatchChunk.Stage.ENRICHMENT,
                requested_blocks=sorted(blocks),
                sequence=(index // batch.chunk_size) + 1,
                start_row=group[0],
                end_row=group[-1],
                checkpoint_row=group[0] - 1,
            )
        )
    BatchChunk.objects.bulk_create(chunks, batch_size=500)
    batch.items.filter(status=BatchItem.Status.SUCCEEDED, entity__isnull=False).update(
        enrichment_status=BatchItem.EnrichmentStatus.PENDING,
        delivered_blocks=[],
        missing_blocks=sorted(blocks),
        enrichment_errors=[],
    )
    batch.status = Batch.Status.QUEUED
    batch.current_stage = BatchChunk.Stage.ENRICHMENT
    batch.completed_at = None
    batch.save(update_fields=("status", "current_stage", "completed_at", "updated_at"))
    ids = [chunk.pk for chunk in chunks]
    transaction.on_commit(lambda: _publish_chunks(ids))
    return batch


def _complete_batch(batch_id: UUID | str) -> None:
    with transaction.atomic():
        batch = Batch.objects.select_for_update().get(pk=batch_id)
        active = batch.chunks.filter(
            stage=BatchChunk.Stage.ENRICHMENT,
            status__in=(BatchChunk.Status.PENDING, BatchChunk.Status.RUNNING),
        ).exists()
        if active or batch.status == Batch.Status.PAUSED:
            return
        if batch.status == Batch.Status.CANCEL_REQUESTED:
            batch.status = Batch.Status.CANCELLED
        elif batch.items.filter(enrichment_status=BatchItem.EnrichmentStatus.FAILED).exists():
            batch.status = Batch.Status.PARTIAL
        elif batch.items.filter(enrichment_status=BatchItem.EnrichmentStatus.PARTIAL).exists():
            batch.status = Batch.Status.PARTIAL
        else:
            batch.status = Batch.Status.COMPLETED
        batch.completed_at = timezone.now()
        batch.save(update_fields=("status", "completed_at", "updated_at"))


def process_enrichment_chunk(
    *, chunk_id: UUID | str, worker_id: str | None = None
) -> ChunkExecution:
    claimed = claim_chunk(chunk_id=chunk_id, worker_id=worker_id or socket.gethostname())
    if claimed is None:
        return ChunkExecution(status="SKIPPED")
    chunk, attempt = claimed
    if chunk.stage != BatchChunk.Stage.ENRICHMENT:
        raise ValidationError("Chunk não pertence à etapa de enriquecimento.")
    try:
        items = BatchItem.objects.filter(
            batch_id=chunk.batch_id,
            row_number__gte=max(chunk.start_row, chunk.checkpoint_row + 1),
            row_number__lte=chunk.end_row,
            status=BatchItem.Status.SUCCEEDED,
            entity__isnull=False,
        ).order_by("row_number")
        for item in items.iterator(chunk_size=100):
            batch = Batch.objects.get(pk=chunk.batch_id)
            if batch.status in {Batch.Status.PAUSED, Batch.Status.CANCEL_REQUESTED}:
                with transaction.atomic():
                    locked = BatchChunk.objects.select_for_update().get(pk=chunk.pk)
                    locked.status = (
                        BatchChunk.Status.PAUSED
                        if batch.status == Batch.Status.PAUSED
                        else BatchChunk.Status.CANCELLED
                    )
                    locked.lease_owner = ""
                    locked.leased_until = None
                    locked.save()
                _complete_batch(chunk.batch_id)
                return ChunkExecution(status=locked.status)
            result = run_enrichment_cascade(
                tenant=item.tenant,
                batch=batch,
                item=item,
                requested_blocks=frozenset(chunk.requested_blocks),
            )
            with transaction.atomic():
                locked_item = BatchItem.objects.select_for_update().get(pk=item.pk)
                locked_item.delivered_blocks = sorted(result.delivered_blocks)
                locked_item.missing_blocks = sorted(result.missing_blocks)
                locked_item.enrichment_errors = list(result.errors)
                if not result.missing_blocks:
                    locked_item.enrichment_status = BatchItem.EnrichmentStatus.SUCCEEDED
                elif result.delivered_blocks:
                    locked_item.enrichment_status = BatchItem.EnrichmentStatus.PARTIAL
                else:
                    locked_item.enrichment_status = BatchItem.EnrichmentStatus.FAILED
                locked_item.save()
                try:
                    from leadstream.canonical.builder import CanonicalLeadBuilder
                    CanonicalLeadBuilder(tenant=item.tenant).build_and_save(locked_item)
                except Exception:
                    pass
                BatchChunk.objects.filter(pk=chunk.pk).update(
                    checkpoint_row=item.row_number,
                    leased_until=timezone.now() + timedelta(seconds=settings.BATCH_LEASE_SECONDS),
                )
        with transaction.atomic():
            locked_chunk = BatchChunk.objects.select_for_update().get(pk=chunk.pk)
            locked_chunk.status = BatchChunk.Status.COMPLETED
            locked_chunk.lease_owner = ""
            locked_chunk.leased_until = None
            locked_chunk.completed_at = timezone.now()
            locked_chunk.save()
            attempt.status = ProcessingAttempt.Status.SUCCEEDED
            attempt.finished_at = timezone.now()
            attempt.save(update_fields=("status", "finished_at"))
        _complete_batch(chunk.batch_id)
        return ChunkExecution(status=BatchChunk.Status.COMPLETED)
    except Exception as exc:  # noqa: BLE001 -- fronteira do worker persiste retry
        with transaction.atomic():
            locked_chunk = BatchChunk.objects.select_for_update().get(pk=chunk.pk)
            retryable = locked_chunk.attempt_count < locked_chunk.max_attempts
            locked_chunk.status = (
                BatchChunk.Status.PENDING if retryable else BatchChunk.Status.FAILED
            )
            locked_chunk.dispatched_at = None
            locked_chunk.lease_owner = ""
            locked_chunk.leased_until = None
            locked_chunk.last_error_code = "ENRICHMENT_CHUNK_ERROR"
            locked_chunk.last_error_message = str(exc)[:500]
            locked_chunk.save()
            attempt.status = (
                ProcessingAttempt.Status.RETRYABLE_FAILURE
                if retryable
                else ProcessingAttempt.Status.PERMANENT_FAILURE
            )
            attempt.error_code = "ENRICHMENT_CHUNK_ERROR"
            attempt.error_message = str(exc)[:500]
            attempt.finished_at = timezone.now()
            attempt.save()
        if not retryable:
            BatchItem.objects.filter(
                batch_id=chunk.batch_id,
                row_number__gt=chunk.checkpoint_row,
                row_number__lte=chunk.end_row,
            ).update(
                enrichment_status=BatchItem.EnrichmentStatus.FAILED,
                enrichment_errors=["ENRICHMENT_CHUNK_ERROR"],
            )
        _complete_batch(chunk.batch_id)
        return ChunkExecution(status=BatchChunk.Status.FAILED, retryable=retryable)
