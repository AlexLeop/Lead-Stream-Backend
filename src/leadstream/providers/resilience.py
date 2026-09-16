from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Case, F, IntegerField, Sum, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from leadstream.batches.models import Batch
from leadstream.billing.models import ProviderCall
from leadstream.tenancy.models import Tenant

from .exceptions import ProviderBudgetExceeded, ProviderCircuitOpen, ProviderRateLimited
from .models import ProviderHealth, ProviderPolicy


@dataclass(frozen=True)
class ProviderGate:
    policy: ProviderPolicy
    reserved_cost_cents: int


def _rate_limit(
    *,
    tenant: Tenant,
    policy: ProviderPolicy,
    scope: str | None = None,
    requests_per_minute: int | None = None,
    units: int = 1,
) -> None:
    del tenant  # As credenciais atuais são globais, compartilhadas pelos tenants.
    if units < 1:
        raise ValidationError("Unidades de quota devem ser positivas.")
    configured_limit = policy.requests_per_minute
    effective_limit = (
        min(configured_limit, requests_per_minute)
        if requests_per_minute is not None
        else configured_limit
    )
    timestamp = int(timezone.now().timestamp())
    minute = timestamp // 60
    retry_after = 60 - (timestamp % 60)
    key = f"provider-rate:{scope or policy.provider}:{minute}"
    if effective_limit == 0:
        raise ProviderRateLimited(f"Provedor {policy.provider} está pausado por quota zero.")
    if cache.add(key, units, timeout=120):
        if units > effective_limit:
            raise ProviderRateLimited(
                f"Limite por minuto atingido para {policy.provider}.",
                retry_after_seconds=retry_after,
            )
        return
    try:
        count = cache.incr(key, delta=units)
    except ValueError:
        cache.set(key, units, timeout=120)
        count = units
    if count > effective_limit:
        raise ProviderRateLimited(
            f"Limite por minuto atingido para {policy.provider}.",
            retry_after_seconds=retry_after,
        )


def _spent(*, tenant: Tenant, policy: ProviderPolicy, batch: Batch | None) -> int:
    queryset = ProviderCall.objects.filter(
        tenant=tenant,
        provider=policy.provider,
    )
    if batch is not None:
        queryset = queryset.filter(batch=batch)
    else:
        queryset = queryset.filter(started_at__date=timezone.localdate())
    value = queryset.aggregate(
        total=Coalesce(
            Sum(
                Case(
                    When(status=ProviderCall.Status.REQUESTED, then=F("estimated_cost_cents")),
                    default=F("confirmed_cost_cents"),
                    output_field=IntegerField(),
                )
            ),
            0,
        )
    )["total"]
    return int(value)


@transaction.atomic
def acquire_provider_gate(
    *,
    tenant: Tenant,
    policy: ProviderPolicy,
    batch: Batch,
    rate_limit_scope: str | None = None,
    requests_per_minute: int | None = None,
    rate_limit_units: int = 1,
) -> ProviderGate:
    if policy.tenant_id != tenant.pk or batch.tenant_id != tenant.pk:
        raise ValidationError("Política ou lote pertence a outro tenant.")
    locked = ProviderPolicy.objects.select_for_update().get(pk=policy.pk, tenant=tenant)
    if not locked.enabled:
        raise ValidationError(f"Provedor {locked.provider} está desabilitado.")
    health, _ = ProviderHealth.objects.select_for_update().get_or_create(
        tenant=tenant, policy=locked
    )
    now = timezone.now()
    if health.circuit_open_until and health.circuit_open_until > now:
        raise ProviderCircuitOpen(f"Circuito de {locked.provider} está temporariamente aberto.")
    reserve = locked.estimated_cost_cents
    daily_spent = _spent(tenant=tenant, policy=locked, batch=None)
    batch_spent = _spent(tenant=tenant, policy=locked, batch=batch)
    if locked.daily_budget_cents and daily_spent + reserve > locked.daily_budget_cents:
        raise ProviderBudgetExceeded(f"Orçamento diário de {locked.provider} atingido.")
    if locked.batch_budget_cents and batch_spent + reserve > locked.batch_budget_cents:
        raise ProviderBudgetExceeded(f"Orçamento do lote para {locked.provider} atingido.")
    _rate_limit(
        tenant=tenant,
        policy=locked,
        scope=rate_limit_scope,
        requests_per_minute=requests_per_minute,
        units=rate_limit_units,
    )
    return ProviderGate(policy=locked, reserved_cost_cents=reserve)


@transaction.atomic
def record_provider_success(*, policy: ProviderPolicy) -> None:
    health, _ = ProviderHealth.objects.select_for_update().get_or_create(
        tenant=policy.tenant, policy=policy
    )
    health.consecutive_failures = 0
    health.circuit_open_until = None
    health.last_success_at = timezone.now()
    health.last_error_code = ""
    health.save()


@transaction.atomic
def record_provider_failure(*, policy: ProviderPolicy, error_code: str) -> None:
    health, _ = ProviderHealth.objects.select_for_update().get_or_create(
        tenant=policy.tenant, policy=policy
    )
    health.consecutive_failures += 1
    health.last_failure_at = timezone.now()
    health.last_error_code = error_code[:64]
    if health.consecutive_failures >= policy.failure_threshold:
        health.circuit_open_until = timezone.now() + timedelta(seconds=policy.recovery_seconds)
    health.save()
