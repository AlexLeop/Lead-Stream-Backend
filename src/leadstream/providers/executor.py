from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, replace
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from leadstream.batches.models import BatchItem
from leadstream.billing.models import ProviderCall
from leadstream.billing.services import (
    ELIGIBLE_EVIDENCE_STATUSES,
    active_price_book,
    finalize_provider_call,
    record_billable_delivery,
    register_provider_call,
)
from leadstream.entities.normalization import fingerprint_value

from .contracts import ProviderAdapter, ProviderContext, ProviderQuota
from .exceptions import (
    ProviderError,
    ProviderNotConfigured,
    ProviderPending,
    ProviderPermanentError,
    ProviderRateLimited,
    ProviderSubmissionUncertain,
    ProviderTemporaryError,
)
from .models import ProviderPolicy
from .persistence import persist_provider_result
from .resilience import (
    _rate_limit,
    acquire_provider_gate,
    record_provider_failure,
    record_provider_success,
)


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


def _provider_quota(
    adapter: ProviderAdapter,
    policy: ProviderPolicy,
    context: ProviderContext,
) -> ProviderQuota:
    quota_factory = getattr(adapter, "quota_for", None)
    if not callable(quota_factory):
        return ProviderQuota(
            scope=policy.provider,
            requests_per_minute=policy.requests_per_minute,
        )
    quota = quota_factory(context)
    if not isinstance(quota, ProviderQuota):
        raise ValidationError("Adapter retornou uma definição de quota inválida.")
    return quota


@transaction.atomic
def _reserve(
    adapter: ProviderAdapter,
    policy: ProviderPolicy,
    context: ProviderContext,
) -> tuple[ProviderCall, str]:
    # Mesmo lock protege a consulta de orçamento E a inserção da reserva.
    locked = ProviderPolicy.objects.select_for_update().get(pk=policy.pk, tenant=context.tenant)
    if (
        context.batch.tenant_id != context.tenant.pk
        or context.item.tenant_id != context.tenant.pk
        or context.item.batch_id != context.batch.pk
    ):
        raise ValidationError("Contexto do provedor contém referências de outro lote/tenant.")
    base = _base_key(context, policy)
    quota = _provider_quota(adapter, locked, context)
    calls = ProviderCall.objects.filter(tenant=context.tenant, idempotency_key__startswith=base)
    completed = calls.filter(status__in=("SUCCEEDED", "ABSENT")).first()
    if completed is not None:
        return completed, ""
    if calls.filter(error_code="ProviderSubmissionUncertain").exists():
        raise ProviderSubmissionUncertain("Envio anterior exige reconciliação; não será repetido.")
    call = calls.filter(status="REQUESTED").first()
    now = timezone.now()
    if call is not None:
        if (call.leased_until and call.leased_until > now) or (
            call.next_poll_at and call.next_poll_at > now
        ):
            raise ProviderPending("Execução remota já está em andamento.")
        if not getattr(adapter, "resumable", False):
            raise ProviderSubmissionUncertain("Chamada interrompida sem confirmação remota.")
        _rate_limit(
            tenant=context.tenant,
            policy=locked,
            scope=quota.scope,
            requests_per_minute=quota.requests_per_minute,
            units=quota.units,
        )
    else:
        if not adapter.is_configured():
            raise ProviderNotConfigured(f"{policy.display_name} não está configurado.")
        technical_attempts = calls.exclude(error_code="ProviderRateLimited").count()
        if technical_attempts > locked.max_retries:
            raise ProviderPermanentError("Limite de tentativas do provedor atingido.")
        gate = acquire_provider_gate(
            tenant=context.tenant,
            policy=locked,
            batch=context.batch,
            rate_limit_scope=quota.scope,
            requests_per_minute=quota.requests_per_minute,
            rate_limit_units=quota.units,
        )
        call = register_provider_call(
            tenant=context.tenant,
            batch=context.batch,
            item=context.item,
            provider=locked.provider,
            operation="enrich",
            block=next(iter(sorted(context.missing_blocks))),
            idempotency_key=f"{base}:{calls.count() + 1}",
            estimated_cost_cents=gate.reserved_cost_cents,
        )
    token = str(uuid.uuid4())
    call.execution_token = token
    call.leased_until = now + timedelta(seconds=locked.timeout_seconds + 30)
    call.next_poll_at = None
    call.save(update_fields=("execution_token", "leased_until", "next_poll_at"))
    return call, token


def execute_provider(
    *,
    adapter: ProviderAdapter,
    policy: ProviderPolicy,
    context: ProviderContext,
) -> ProviderExecution:
    if adapter.slug != policy.provider or not context.missing_blocks:
        raise ValidationError("Adapter, política ou blocos inválidos.")
    call, token = _reserve(adapter, policy, context)
    if not token:
        return ProviderExecution(call.status, frozenset(call.delivered_blocks), str(call.pk))
    started = time.monotonic()
    result = None
    try:
        result = adapter.enrich(replace(context, call_id=str(call.pk), execution_token=token))
        if result.outcome not in {"SUCCEEDED", "ABSENT"} or result.confirmed_cost_cents < 0:
            raise ProviderPermanentError("Resultado do provedor fora do contrato.")
        # Evidências, entrega, cobrança e finalização formam uma única transação.
        with transaction.atomic():
            BatchItem.objects.select_for_update().get(pk=context.item.pk)
            locked_call = ProviderCall.objects.select_for_update().get(pk=call.pk)
            if locked_call.execution_token != token or locked_call.status != "REQUESTED":
                raise ProviderPending("A execução foi retomada por outro trabalhador.")
            qualities = (
                persist_provider_result(
                    item=context.item,
                    policy=policy,
                    result=result,
                    call_id=call.pk,
                )
                if result.outcome == "SUCCEEDED"
                else {}
            )
            price_book = active_price_book(tenant=context.tenant)
            rules = {rule.block: rule for rule in price_book.rules.all()}
            delivered = set()
            for block, quality in qualities.items():
                rule = rules.get(block)
                if (
                    block not in context.missing_blocks
                    or rule is None
                    or quality.status not in ELIGIBLE_EVIDENCE_STATUSES
                    or quality.confidence < rule.minimum_confidence
                ):
                    continue
                record_billable_delivery(
                    tenant=context.tenant,
                    batch=context.batch,
                    item=context.item,
                    block=block,
                    delivered_value_fingerprint=quality.fingerprint,
                    evidence_status=quality.status,
                    confidence=quality.confidence,
                )
                delivered.add(block)
            finalized = finalize_provider_call(
                call=call,
                status=result.outcome,
                confirmed_cost_cents=result.confirmed_cost_cents,
                external_request_id=result.external_request_id,
                latency_ms=round((time.monotonic() - started) * 1000),
                delivered_blocks=delivered,
            )
        record_provider_success(policy=policy)
        return ProviderExecution(finalized.status, frozenset(delivered), str(call.pk))
    except ProviderPending:
        raise
    except Exception as exc:
        with transaction.atomic():
            locked_call = ProviderCall.objects.select_for_update().get(pk=call.pk)
            if locked_call.execution_token == token and locked_call.status == "REQUESTED":
                finalize_provider_call(
                    call=locked_call,
                    status="FAILED",
                    confirmed_cost_cents=result.confirmed_cost_cents if result else 0,
                    error_code=type(exc).__name__,
                    latency_ms=round((time.monotonic() - started) * 1000),
                )
        if not isinstance(exc, ProviderRateLimited):
            record_provider_failure(policy=policy, error_code=type(exc).__name__)
        if isinstance(exc, (ProviderError, ValidationError)):
            raise
        raise ProviderTemporaryError("Falha inesperada no provedor.") from exc
    finally:
        ProviderCall.objects.filter(pk=call.pk, execution_token=token).update(leased_until=None)
