from __future__ import annotations

from typing import Any

from celery import shared_task

from .pipeline import process_enrichment_chunk


@shared_task(  # type: ignore[untyped-decorator]
    bind=True,
    name="leadstream.providers.process_enrichment_chunk",
    ignore_result=True,
    max_retries=5,
)
def process_enrichment_chunk_task(self: Any, chunk_id: str) -> None:
    result = process_enrichment_chunk(chunk_id=chunk_id, worker_id=str(self.request.id))
    if result.retryable:
        raise self.retry(countdown=30)
