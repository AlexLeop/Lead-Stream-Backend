from __future__ import annotations

from typing import Any

from celery import shared_task

from .services import ingest_batch, process_chunk, recover_stalled_work


@shared_task(name="leadstream.batches.ingest", ignore_result=True)  # type: ignore[untyped-decorator]
def ingest_batch_task(batch_id: str) -> None:
    ingest_batch(batch_id)


@shared_task(  # type: ignore[untyped-decorator]
    bind=True,
    name="leadstream.batches.process_chunk",
    ignore_result=True,
    max_retries=5,
)
def process_chunk_task(self: Any, chunk_id: str) -> None:
    request = self.request
    result = process_chunk(chunk_id=chunk_id, worker_id=str(request.id))
    if result.retryable:
        raise self.retry(countdown=10)


@shared_task(name="leadstream.batches.recover", ignore_result=True)  # type: ignore[untyped-decorator]
def recover_stalled_work_task() -> None:
    recover_stalled_work()


@shared_task(name="leadstream.batches.generate_export", ignore_result=True)  # type: ignore[untyped-decorator]
def generate_export_task(export_id: str) -> None:
    from .exporter import CommercialBatchExporter
    from .models import BatchExport

    export = BatchExport.objects.get(pk=export_id)
    exporter = CommercialBatchExporter(export)
    exporter.execute()
