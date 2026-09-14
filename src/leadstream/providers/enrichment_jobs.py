from __future__ import annotations

import hashlib
import hmac
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction
from django.utils import timezone

from leadstream.common.redaction import mask_cpf
from leadstream.entities.normalization import only_digits
from leadstream.tenancy.models import Tenant

from .live_enrichment import enrich_company_live
from .live_enrichment_person import enrich_person_live
from .models import EnrichmentJob

logger = logging.getLogger(__name__)

FINAL_JOB_STATUSES = {
    EnrichmentJob.Status.SUCCEEDED,
    EnrichmentJob.Status.NO_DATA,
    EnrichmentJob.Status.FAILED,
}


def _payload_retention_deadline(now: datetime) -> datetime:
    retention_days = max(int(getattr(settings, "ENRICHMENT_JOB_RETENTION_DAYS", 30)), 1)
    return now + timedelta(days=retention_days)


@dataclass(frozen=True)
class EnrichmentJobCreation:
    job: EnrichmentJob
    created: bool


def _query_digest(*, tenant: Tenant, entity_type: str, query: str) -> str:
    secret = str(getattr(settings, "DATA_HASH_KEY", ""))
    if not secret:
        raise ImproperlyConfigured("DATA_HASH_KEY é obrigatória para proteger consultas.")
    material = f"{tenant.pk}:{entity_type}:{query}".encode()
    return hmac.new(secret.encode("utf-8"), material, hashlib.sha256).hexdigest()


def _query_label(entity_type: str, digits: str) -> str:
    if entity_type == EnrichmentJob.EntityType.PERSON:
        return mask_cpf(digits)
    return f"{digits[:2]}.***.***/****-{digits[-2:]}"


def _normalize_capabilities(capabilities: list[str]) -> list[str]:
    normalized = sorted(
        {
            capability.strip()
            for capability in capabilities
            if isinstance(capability, str) and capability.strip()
        }
    )
    if len(normalized) > 30 or any(len(capability) > 64 for capability in normalized):
        raise ValidationError("A lista de capacidades solicitadas é inválida.")
    return normalized


def create_enrichment_job(
    *,
    tenant: Tenant,
    entity_type: str,
    query: str,
    capabilities: list[str],
    idempotency_key: str,
) -> EnrichmentJobCreation:
    idempotency_key = idempotency_key.strip()
    if not idempotency_key or len(idempotency_key) > 128:
        raise ValidationError({"Idempotency-Key": "Informe uma chave de até 128 caracteres."})
    digits = only_digits(query)
    expected_length = 14 if entity_type == EnrichmentJob.EntityType.COMPANY else 11
    if len(digits) != expected_length:
        document = "CNPJ" if expected_length == 14 else "CPF"
        raise ValidationError({"query": f"Informe um {document} com {expected_length} dígitos."})
    normalized_capabilities = _normalize_capabilities(capabilities)
    digest = _query_digest(tenant=tenant, entity_type=entity_type, query=digits)

    with transaction.atomic():
        existing = EnrichmentJob.objects.filter(
            tenant=tenant,
            idempotency_key=idempotency_key,
        ).first()
        if existing:
            if (
                existing.entity_type != entity_type
                or existing.query_digest != digest
                or existing.capabilities != normalized_capabilities
            ):
                raise ValidationError(
                    {"Idempotency-Key": "Esta chave já foi usada com outra solicitação."}
                )
            return EnrichmentJobCreation(job=existing, created=False)

        job = EnrichmentJob.objects.create(
            tenant=tenant,
            entity_type=entity_type,
            idempotency_key=idempotency_key,
            query_digest=digest,
            query_label=_query_label(entity_type, digits),
            input_payload={"query": digits},  # type: ignore[misc]
            capabilities=normalized_capabilities,
            purge_after=_payload_retention_deadline(timezone.now()),
        )
        from .tasks import process_enrichment_job_task

        transaction.on_commit(lambda: process_enrichment_job_task.delay(str(job.pk)))
        return EnrichmentJobCreation(job=job, created=True)


def execute_enrichment_job(job_id: str, *, worker_id: str) -> EnrichmentJob:
    now = timezone.now()
    lease_seconds = int(getattr(settings, "ENRICHMENT_JOB_LEASE_SECONDS", 600))
    with transaction.atomic():
        job = EnrichmentJob.objects.select_for_update().select_related("tenant").get(pk=job_id)
        if job.status in FINAL_JOB_STATUSES:
            return job
        if (
            job.status == EnrichmentJob.Status.RUNNING
            and job.leased_until
            and job.leased_until > now
            and job.lease_owner != worker_id
        ):
            return job
        job.status = EnrichmentJob.Status.RUNNING
        job.lease_owner = worker_id[:255]
        job.leased_until = now + timedelta(seconds=lease_seconds)
        job.attempt_count += 1
        job.started_at = job.started_at or now
        job.last_error_code = ""
        job.last_error_message = ""
        job.save(
            update_fields=[
                "status",
                "lease_owner",
                "leased_until",
                "attempt_count",
                "started_at",
                "last_error_code",
                "last_error_message",
                "updated_at",
            ]
        )

    try:
        query = str(job.input_payload.get("query", ""))
        if job.entity_type == EnrichmentJob.EntityType.COMPANY:
            result = enrich_company_live(
                query=query,
                tenant=job.tenant,
                capabilities=list(job.capabilities),
            )
            matched = bool(result.get("company"))
            matched_entity_id = str(result.get("companyId") or "")
        else:
            result = enrich_person_live(
                query=query,
                tenant=job.tenant,
                capabilities=list(job.capabilities),
            )
            matched = bool(result.get("person"))
            matched_entity_id = str(result.get("personId") or "")
    except Exception as exc:
        error_code = type(exc).__name__[:64]
        terminal = job.attempt_count >= job.max_attempts
        EnrichmentJob.objects.filter(pk=job.pk).update(
            status=EnrichmentJob.Status.FAILED if terminal else EnrichmentJob.Status.QUEUED,
            lease_owner="",
            leased_until=None,
            last_error_code=error_code,
            last_error_message="Falha temporária ao consultar um provedor.",
            completed_at=timezone.now() if terminal else None,
            purge_after=_payload_retention_deadline(timezone.now()),
            updated_at=timezone.now(),
        )
        logger.warning(
            "Falha no job de enriquecimento %s (%s): %s",
            job.pk,
            job.query_digest[:12],
            error_code,
        )
        raise

    completed_at = timezone.now()
    EnrichmentJob.objects.filter(pk=job.pk).update(
        status=(EnrichmentJob.Status.SUCCEEDED if matched else EnrichmentJob.Status.NO_DATA),
        result_payload=result,
        matched_entity_id=matched_entity_id,
        cost_credits=max(int(result.get("costCredits") or 0), 0),
        lease_owner="",
        leased_until=None,
        completed_at=completed_at,
        purge_after=_payload_retention_deadline(completed_at),
        updated_at=completed_at,
    )
    return EnrichmentJob.objects.get(pk=job.pk)


def recover_stalled_enrichment_jobs() -> int:
    now = timezone.now()
    stalled_ids = list(
        EnrichmentJob.objects.filter(
            status=EnrichmentJob.Status.RUNNING,
            leased_until__lt=now,
        ).values_list("pk", flat=True)[:100]
    )
    if not stalled_ids:
        return 0
    EnrichmentJob.objects.filter(pk__in=stalled_ids).update(
        status=EnrichmentJob.Status.QUEUED,
        lease_owner="",
        leased_until=None,
        updated_at=now,
    )
    from .tasks import process_enrichment_job_task

    for job_id in stalled_ids:
        process_enrichment_job_task.delay(str(job_id))
    return len(stalled_ids)


def purge_expired_enrichment_payloads() -> int:
    now = timezone.now()
    expired = EnrichmentJob.objects.filter(
        status__in=FINAL_JOB_STATUSES,
        purge_after__lte=now,
        purged_at__isnull=True,
    )
    count = expired.count()
    if count:
        expired.update(
            input_payload={},
            result_payload={},
            purged_at=now,
            updated_at=now,
        )
    return count
