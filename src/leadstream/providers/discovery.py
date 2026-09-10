from __future__ import annotations

import json
import logging
import math
import socket
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, cast
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from leadstream.batches.hygiene import normalize_row
from leadstream.batches.models import Batch, BatchChunk, BatchItem
from leadstream.batches.services import _publish_chunks
from leadstream.entities.normalization import DataValidationError, fingerprint_value, normalize_cnpj
from leadstream.tenancy.models import Tenant

from .adapters.bigquery import BigQueryOpenCNPJAdapter
from .adapters.mapping import pick
from .exceptions import ProviderNotConfigured, ProviderPermanentError
from .models import DiscoveryResult, DiscoverySearch

logger = logging.getLogger(__name__)

ALLOWED_FILTERS = {
    "cnaes",
    "ufs",
    "municipios",
    "situacoes_cadastrais",
    "portes",
    "naturezas_juridicas",
    "matriz",
}


@dataclass(frozen=True)
class DiscoveryCreation:
    search: DiscoverySearch
    created: bool


@dataclass(frozen=True)
class DiscoveryExecution:
    status: str
    retryable: bool = False


def normalize_discovery_filters(value: dict[str, Any]) -> dict[str, Any]:
    unknown = set(value).difference(ALLOWED_FILTERS)
    if unknown:
        raise ValidationError(
            {"filters": f"Filtros não suportados: {', '.join(sorted(unknown))}."}
        )
    normalized: dict[str, Any] = {}
    for key, raw in value.items():
        if key == "matriz":
            if not isinstance(raw, bool):
                raise ValidationError({"filters.matriz": "Informe verdadeiro ou falso."})
            normalized[key] = raw
            continue
        if not isinstance(raw, list) or not raw:
            raise ValidationError({f"filters.{key}": "Informe uma lista não vazia."})
        values = sorted({str(item).strip().upper() for item in raw if str(item).strip()})
        if not values or len(values) > 100:
            raise ValidationError(
                {f"filters.{key}": "Informe entre 1 e 100 valores distintos."}
            )
        if key == "ufs" and any(len(item) != 2 for item in values):
            raise ValidationError({"filters.ufs": "UF deve possuir duas letras."})
        normalized[key] = values
    if not normalized:
        raise ValidationError({"filters": "Informe ao menos um filtro de descoberta."})
    return normalized


def _validate_idempotency_key(value: str) -> str:
    key = value.strip()
    if len(key) < 8 or len(key) > 128:
        raise ValidationError(
            {"Idempotency-Key": "Informe uma chave entre 8 e 128 caracteres."}
        )
    return key


def _publish_discovery(search_id: UUID | str) -> None:
    from .tasks import process_discovery_search_task

    DiscoverySearch.objects.filter(
        pk=search_id, status=DiscoverySearch.Status.QUEUED
    ).update(dispatched_at=timezone.now())
    try:
        process_discovery_search_task.delay(str(search_id))
    except Exception:
        DiscoverySearch.objects.filter(
            pk=search_id, status=DiscoverySearch.Status.QUEUED
        ).update(dispatched_at=None)
        logger.exception("discovery_dispatch_failed", extra={"search_id": str(search_id)})


@transaction.atomic
def create_discovery_search(
    *,
    tenant: Tenant,
    name: str,
    filters: dict[str, Any],
    idempotency_key: str,
    max_results: int = 10_000,
    query_page_size: int = 1_000,
    adapter: BigQueryOpenCNPJAdapter | None = None,
) -> DiscoveryCreation:
    provider = adapter or BigQueryOpenCNPJAdapter()
    if not provider.is_discovery_configured():
        raise ProviderNotConfigured("Descoberta BigQuery/OpenCNPJ não configurada.")
    key = _validate_idempotency_key(idempotency_key)
    normalized_filters = normalize_discovery_filters(filters)
    if not 1 <= max_results <= settings.BATCH_MAX_ROWS:
        raise ValidationError(
            {"max_results": f"Informe entre 1 e {settings.BATCH_MAX_ROWS:,}."}
        )
    if not 100 <= query_page_size <= 10_000:
        raise ValidationError({"query_page_size": "Informe entre 100 e 10.000."})
    existing = DiscoverySearch.objects.filter(tenant=tenant, idempotency_key=key).first()
    if existing is not None:
        return DiscoveryCreation(search=existing, created=False)
    try:
        with transaction.atomic():
            search = DiscoverySearch.objects.create(
                tenant=tenant,
                name=" ".join(name.split())[:160] or "Descoberta de empresas",
                idempotency_key=key,
                filters=normalized_filters,
                max_results=max_results,
                query_page_size=query_page_size,
            )
    except IntegrityError:
        search = DiscoverySearch.objects.get(tenant=tenant, idempotency_key=key)
        return DiscoveryCreation(search=search, created=False)
    transaction.on_commit(lambda: _publish_discovery(search.pk))
    return DiscoveryCreation(search=search, created=True)


def _json_safe(value: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(json.dumps(value, ensure_ascii=False, default=str)))


def _result_from_row(
    *, search: DiscoverySearch, row: dict[str, Any], rank: int
) -> DiscoveryResult | None:
    raw_cnpj = str(pick(row, "cnpj", "documento", "cnpj_basico", default=""))
    try:
        cnpj = normalize_cnpj(raw_cnpj)
    except DataValidationError:
        return None
    source_data = _json_safe(row)
    return DiscoveryResult(
        tenant=search.tenant,
        search=search,
        rank=rank,
        cnpj=cnpj,
        legal_name=str(pick(row, "razao_social", "legal_name", "nome_empresarial"))[:255],
        trade_name=str(pick(row, "nome_fantasia", "trade_name"))[:255],
        registration_status=str(
            pick(row, "situacao_cadastral", "registration_status")
        )[:64],
        primary_cnae=str(pick(row, "cnae_fiscal", "cnae_principal", "primary_cnae"))[:16],
        company_size=str(pick(row, "porte", "company_size"))[:80],
        state=str(pick(row, "uf", "estado", "state"))[:2].upper(),
        city=str(pick(row, "municipio", "cidade", "city"))[:160],
        source_data=source_data,
        source_fingerprint=fingerprint_value(source_data),
    )


def _discovery_cost(billed_bytes: int) -> int:
    return math.ceil((billed_bytes / (1024**4)) * settings.BIGQUERY_COST_CENTS_PER_TIB)


def execute_discovery_search(
    *,
    search_id: UUID | str,
    worker_id: str,
    adapter: BigQueryOpenCNPJAdapter | None = None,
) -> DiscoveryExecution:
    provider = adapter or BigQueryOpenCNPJAdapter()
    now = timezone.now()
    with transaction.atomic():
        search = (
            DiscoverySearch.objects.select_for_update()
            .select_related("tenant")
            .get(pk=search_id)
        )
        if search.status in {
            DiscoverySearch.Status.COMPLETED,
            DiscoverySearch.Status.CANCELLED,
        }:
            return DiscoveryExecution(status=search.status)
        if search.leased_until and search.leased_until > now and search.lease_owner != worker_id:
            return DiscoveryExecution(status=search.status)
        if search.attempt_count >= search.max_attempts:
            search.status = DiscoverySearch.Status.FAILED
            search.completed_at = now
            search.last_error_code = "MAX_ATTEMPTS"
            search.last_error_message = "Número máximo de tentativas excedido."
            search.save()
            return DiscoveryExecution(status=search.status)
        search.status = DiscoverySearch.Status.RUNNING
        search.attempt_count += 1
        search.lease_owner = worker_id[:255]
        search.leased_until = now + timedelta(seconds=settings.BATCH_LEASE_SECONDS)
        search.started_at = search.started_at or now
        search.last_error_code = ""
        search.last_error_message = ""
        search.save()

    try:
        while search.total_results < search.max_results:
            limit = min(search.query_page_size, search.max_results - search.total_results)
            response = provider.discover(
                search.filters, limit=limit, offset=search.checkpoint_offset
            )
            rows = response.rows
            with transaction.atomic():
                search = (
                    DiscoverySearch.objects.select_for_update()
                    .select_related("tenant")
                    .get(pk=search_id)
                )
                if search.status == DiscoverySearch.Status.CANCELLED:
                    return DiscoveryExecution(status=search.status)
                candidates = [
                    candidate
                    for row in rows
                    if (candidate := _result_from_row(search=search, row=row, rank=0))
                    is not None
                ]
                known_cnpjs = set(
                    search.results.filter(
                        cnpj__in=[candidate.cnpj for candidate in candidates]
                    ).values_list("cnpj", flat=True)
                )
                pending: list[DiscoveryResult] = []
                page_cnpjs: set[str] = set()
                next_rank = search.total_results + 1
                for result in candidates:
                    if result.cnpj in known_cnpjs or result.cnpj in page_cnpjs:
                        continue
                    result.rank = next_rank
                    pending.append(result)
                    page_cnpjs.add(result.cnpj)
                    next_rank += 1
                    if search.total_results + len(pending) >= search.max_results:
                        break
                DiscoveryResult.objects.bulk_create(pending, batch_size=1_000)
                search.total_results += len(pending)
                search.checkpoint_offset += len(rows)
                search.billed_bytes += response.billed_bytes
                search.estimated_cost_cents = _discovery_cost(search.billed_bytes)
                search.leased_until = timezone.now() + timedelta(
                    seconds=settings.BATCH_LEASE_SECONDS
                )
                exhausted = not rows or len(rows) < limit
                if exhausted or search.total_results >= search.max_results:
                    search.status = DiscoverySearch.Status.COMPLETED
                    search.completed_at = timezone.now()
                    search.lease_owner = ""
                    search.leased_until = None
                search.save()
            if search.status == DiscoverySearch.Status.COMPLETED:
                return DiscoveryExecution(status=search.status)
        return DiscoveryExecution(status=DiscoverySearch.Status.COMPLETED)
    except (ProviderNotConfigured, ProviderPermanentError) as exc:
        with transaction.atomic():
            search = DiscoverySearch.objects.select_for_update().get(pk=search_id)
            search.status = DiscoverySearch.Status.FAILED
            search.last_error_code = type(exc).__name__
            search.last_error_message = str(exc)[:500]
            search.completed_at = timezone.now()
            search.lease_owner = ""
            search.leased_until = None
            search.save()
        return DiscoveryExecution(status=DiscoverySearch.Status.FAILED)
    except Exception as exc:
        with transaction.atomic():
            search = DiscoverySearch.objects.select_for_update().get(pk=search_id)
            retryable = search.attempt_count < search.max_attempts
            search.status = (
                DiscoverySearch.Status.QUEUED if retryable else DiscoverySearch.Status.FAILED
            )
            search.last_error_code = type(exc).__name__
            search.last_error_message = str(exc)[:500]
            search.completed_at = None if retryable else timezone.now()
            search.lease_owner = ""
            search.leased_until = None
            search.dispatched_at = None
            search.save()
        logger.exception("discovery_execution_failed", extra={"search_id": str(search_id)})
        return DiscoveryExecution(status=search.status, retryable=retryable)


@transaction.atomic
def create_discovery_batch(
    *,
    tenant: Tenant,
    search_id: UUID | str,
    name: str,
    idempotency_key: str,
    chunk_size: int = 500,
    result_ids: list[UUID] | None = None,
) -> Batch:
    key = _validate_idempotency_key(idempotency_key)
    if not 50 <= chunk_size <= 5_000:
        raise ValidationError({"chunk_size": "Use um tamanho entre 50 e 5.000."})
    existing = Batch.objects.filter(tenant=tenant, idempotency_key=key).first()
    if existing is not None:
        return existing
    search = DiscoverySearch.objects.select_for_update().get(pk=search_id, tenant=tenant)
    if search.status != DiscoverySearch.Status.COMPLETED:
        raise ValidationError({"search": "A descoberta precisa estar concluída."})
    queryset = search.results.order_by("rank")
    if result_ids:
        unique_ids = set(result_ids)
        queryset = queryset.filter(pk__in=unique_ids)
        if queryset.count() != len(unique_ids):
            raise ValidationError({"result_ids": "Há resultados inválidos ou de outra busca."})
    results = list(queryset[: settings.BATCH_MAX_ROWS + 1])
    if not results:
        raise ValidationError({"search": "A descoberta não possui resultados selecionados."})
    if len(results) > settings.BATCH_MAX_ROWS:
        raise ValidationError(
            {"search": f"Selecione no máximo {settings.BATCH_MAX_ROWS:,} resultados."}
        )
    try:
        with transaction.atomic():
            batch = Batch.objects.create(
                tenant=tenant,
                name=" ".join(name.split())[:160] or search.name,
                source_type=Batch.SourceType.DISCOVERY,
                status=Batch.Status.QUEUED,
                idempotency_key=key,
                current_stage=BatchChunk.Stage.HYGIENE,
                input_backend="DISCOVERY",
                input_original_name=search.name,
                input_sha256=fingerprint_value(
                    [result.source_fingerprint for result in results]
                ),
                chunk_size=chunk_size,
                total_rows=len(results),
            )
    except IntegrityError:
        return Batch.objects.get(tenant=tenant, idempotency_key=key)
    items: list[BatchItem] = []
    for row_number, result in enumerate(results, start=1):
        raw = {
            "cnpj": result.cnpj,
            "razao_social": result.legal_name,
            "nome_fantasia": result.trade_name,
        }
        hygiene = normalize_row(raw)
        normalized = {
            **hygiene.normalized,
            "registration_status": result.registration_status,
            "primary_cnae": result.primary_cnae,
            "company_size": result.company_size,
            "state": result.state,
            "city": result.city,
        }
        items.append(
            BatchItem(
                tenant=tenant,
                batch=batch,
                row_number=row_number,
                original_data=result.source_data,
                normalized_data=normalized,
                hygiene_state=hygiene.state,
                applied_rules=hygiene.rules,
                issues=hygiene.issues,
                fingerprint=hygiene.fingerprint,
            )
        )
    BatchItem.objects.bulk_create(items, batch_size=1_000)
    chunks: list[BatchChunk] = []
    for start in range(0, len(items), chunk_size):
        start_row = start + 1
        end_row = min(start + chunk_size, len(items))
        chunks.append(
            BatchChunk(
                tenant=tenant,
                batch=batch,
                stage=BatchChunk.Stage.HYGIENE,
                sequence=(start // chunk_size) + 1,
                start_row=start_row,
                end_row=end_row,
                checkpoint_row=start_row - 1,
            )
        )
    BatchChunk.objects.bulk_create(chunks, batch_size=500)
    transaction.on_commit(lambda: _publish_chunks([chunk.pk for chunk in chunks]))
    return batch


def recover_discovery_searches() -> int:
    now = timezone.now()
    stale_before = now - timedelta(seconds=settings.BATCH_LEASE_SECONDS)
    stale = DiscoverySearch.objects.filter(
        status=DiscoverySearch.Status.RUNNING, leased_until__lt=now
    )
    stale.update(
        status=DiscoverySearch.Status.QUEUED,
        lease_owner="",
        leased_until=None,
        dispatched_at=None,
        last_error_code="LEASE_EXPIRED",
        last_error_message="Busca retomada após expiração do worker.",
    )
    pending_ids = list(
        DiscoverySearch.objects.filter(status=DiscoverySearch.Status.QUEUED)
        .filter(dispatched_at__isnull=True)
        .filter(updated_at__lte=stale_before)
        .values_list("pk", flat=True)[:100]
    )
    for search_id in pending_ids:
        _publish_discovery(search_id)
    return len(pending_ids)


def discovery_worker_id(task_id: str) -> str:
    return f"{socket.gethostname()}:{task_id}"[:255]
