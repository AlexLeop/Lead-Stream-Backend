from __future__ import annotations

from typing import Any

from celery import shared_task

from .discovery import discovery_worker_id, execute_discovery_search, recover_discovery_searches
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


@shared_task(  # type: ignore[untyped-decorator]
    bind=True,
    name="leadstream.providers.process_discovery",
    ignore_result=True,
    max_retries=5,
)
def process_discovery_search_task(self: Any, search_id: str) -> None:
    result = execute_discovery_search(
        search_id=search_id,
        worker_id=discovery_worker_id(str(self.request.id)),
    )
    if result.retryable:
        raise self.retry(countdown=min(30 * (self.request.retries + 1), 300))


@shared_task(name="leadstream.providers.recover_discovery", ignore_result=True)  # type: ignore[untyped-decorator]
def recover_discovery_searches_task() -> None:
    recover_discovery_searches()
