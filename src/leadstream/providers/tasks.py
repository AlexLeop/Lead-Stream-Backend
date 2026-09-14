from __future__ import annotations

from typing import Any

from celery import shared_task

from .discovery import discovery_worker_id, execute_discovery_search, recover_discovery_searches
from .enrichment_jobs import (
    execute_enrichment_job,
    purge_expired_enrichment_payloads,
    recover_stalled_enrichment_jobs,
)
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


@shared_task(  # type: ignore[untyped-decorator]
    bind=True,
    name="leadstream.providers.process_enrichment_job",
    ignore_result=True,
    max_retries=5,
)
def process_enrichment_job_task(self: Any, job_id: str) -> None:
    try:
        execute_enrichment_job(job_id, worker_id=str(self.request.id))
    except Exception as exc:
        from .models import EnrichmentJob

        current_job = EnrichmentJob.objects.filter(pk=job_id).first()
        if current_job and current_job.status != EnrichmentJob.Status.FAILED:
            raise self.retry(exc=exc, countdown=min(30 * (self.request.retries + 1), 300)) from exc


@shared_task(  # type: ignore[untyped-decorator]
    name="leadstream.providers.recover_enrichment_jobs",
    ignore_result=True,
)
def recover_enrichment_jobs_task() -> None:
    recover_stalled_enrichment_jobs()


@shared_task(  # type: ignore[untyped-decorator]
    name="leadstream.providers.purge_enrichment_payloads",
    ignore_result=True,
)
def purge_enrichment_payloads_task() -> None:
    purge_expired_enrichment_payloads()
