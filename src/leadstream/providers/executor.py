from __future__ import annotations

import time
from dataclasses import dataclass

from django.core.exceptions import ValidationError as DjangoValidationError

from leadstream.billing.models import ProviderCall
from leadstream.billing.services import (
    finalize_provider_call,
    record_billable_delivery,
    register_provider_call,
)
from leadstream.entities.normalization import DataValidationError, fingerprint_value

from .contracts import ProviderAdapter, ProviderContext, ProviderResult
from .exceptions import (
    ProviderError,
    ProviderNotConfigured,
    ProviderPermanentError,
    ProviderTemporaryError,
)
from .models import ProviderPolicy
from .persistence import persist_provider_result
from .resilience import acquire_provider_gate, record_provider_failure, record_provider_success


@dataclass(frozen=True)
class ProviderExecution:
    status: str
    delivered_blocks: frozenset[str]
    call_id: str | None


def _base_key(context: ProviderContext, policy: ProviderPolicy) -> str:
    return fingerprint_value(
        {
            "tenant": str(context.tenant.pk),
            "batch": str(context.batch.pk),
            "item": str(context.item.pk),
            "provider": policy.provider,
            "blocks": sorted(context.missing_blocks),
        }
    )


def execute_provider(
    *, adapter: ProviderAdapter, policy: ProviderPolicy, context: ProviderContext
) -> ProviderExecution:
    if adapter.slug != policy.provider:
        raise DjangoValidationError("Adapter e política não correspondem.")
    if not adapter.is_configured():
        raise ProviderNotConfigured(f"{policy.display_name} não está configurado.")
    gate = acquire_provider_gate(tenant=context.tenant, policy=policy, batch=context.batch)
    base_key = _base_key(context, policy)
    previous = ProviderCall.objects.filter(
        tenant=context.tenant,
        idempotency_key__startswith=base_key,
        status__in=(ProviderCall.Status.SUCCEEDED, ProviderCall.Status.ABSENT),
    ).order_by("created_at").first()
    if previous is not None:
        return ProviderExecution(
            status=previous.status,
            delivered_blocks=frozenset(previous.delivered_blocks),
            call_id=str(previous.pk),
        )
    attempts = ProviderCall.objects.filter(
        tenant=context.tenant, idempotency_key__startswith=base_key
    ).count()
    call = register_provider_call(
        tenant=context.tenant,
        batch=context.batch,
        item=context.item,
        provider=policy.provider,
        operation="enrich",
        block=next(iter(sorted(context.missing_blocks))),
        idempotency_key=f"{base_key}:{attempts + 1}",
        estimated_cost_cents=gate.reserved_cost_cents,
    )
    started = time.monotonic()
    try:
        result: ProviderResult = adapter.enrich(context)
        if result.outcome not in {ProviderCall.Status.SUCCEEDED, ProviderCall.Status.ABSENT}:
            raise ProviderPermanentError("Provedor retornou estado fora do contrato.")
        qualities = persist_provider_result(
            item=context.item, policy=policy, result=result, call_id=call.pk
        ) if result.outcome == ProviderCall.Status.SUCCEEDED else {}
        latency_ms = round((time.monotonic() - started) * 1000)
        final_cost = result.confirmed_cost_cents or gate.reserved_cost_cents
        finalized = finalize_provider_call(
            call=call,
            status=result.outcome,
            confirmed_cost_cents=final_cost,
            external_request_id=result.external_request_id,
            latency_ms=latency_ms,
            delivered_blocks=result.delivered_blocks,
        )
        record_provider_success(policy=policy)
        for block, quality in qualities.items():
            record_billable_delivery(
                tenant=context.tenant,
                batch=context.batch,
                item=context.item,
                block=block,
                delivered_value_fingerprint=quality.fingerprint,
                evidence_status=quality.status,
                confidence=quality.confidence,
            )
        return ProviderExecution(
            status=finalized.status,
            delivered_blocks=frozenset(finalized.delivered_blocks),
            call_id=str(finalized.pk),
        )
    except ProviderError as exc:
        record_provider_failure(policy=policy, error_code=type(exc).__name__)
        finalize_provider_call(
            call=call,
            status=ProviderCall.Status.FAILED,
            confirmed_cost_cents=0,
            error_code=type(exc).__name__,
            latency_ms=round((time.monotonic() - started) * 1000),
        )
        raise
    except (DataValidationError, DjangoValidationError) as exc:
        finalize_provider_call(
            call=call,
            status=ProviderCall.Status.FAILED,
            confirmed_cost_cents=0,
            error_code=type(exc).__name__,
            latency_ms=round((time.monotonic() - started) * 1000),
        )
        raise
    except Exception as exc:
        record_provider_failure(policy=policy, error_code=type(exc).__name__)
        finalize_provider_call(
            call=call,
            status=ProviderCall.Status.FAILED,
            confirmed_cost_cents=0,
            error_code=type(exc).__name__,
            latency_ms=round((time.monotonic() - started) * 1000),
        )
        raise ProviderTemporaryError("Falha inesperada no provedor.") from exc
