from __future__ import annotations

from dataclasses import dataclass

from leadstream.batches.models import Batch, BatchItem
from leadstream.billing.models import DataBlock
from leadstream.tenancy.models import Tenant

from .contracts import ProviderAdapter, ProviderContext
from .exceptions import (
    ProviderBudgetExceeded,
    ProviderCircuitOpen,
    ProviderError,
    ProviderNotConfigured,
    ProviderRateLimited,
)
from .executor import execute_provider
from .models import ProviderPolicy
from .registry import default_adapters, ensure_provider_policies

DEFAULT_BLOCKS = frozenset(
    {
        DataBlock.COMPANY_REGISTRY,
        DataBlock.DECISION_MAKER,
        DataBlock.DIRECT_EMAIL,
        DataBlock.DIRECT_PHONE,
        DataBlock.WHATSAPP,
        DataBlock.SOCIAL_PROFILES,
    }
)


@dataclass(frozen=True)
class CascadeResult:
    delivered_blocks: frozenset[str]
    missing_blocks: frozenset[str]
    providers_called: int
    errors: tuple[str, ...]


def run_enrichment_cascade(
    *,
    tenant: Tenant,
    batch: Batch,
    item: BatchItem,
    requested_blocks: frozenset[str] = DEFAULT_BLOCKS,
    adapters: dict[str, ProviderAdapter] | None = None,
) -> CascadeResult:
    if item.tenant_id != tenant.pk or batch.tenant_id != tenant.pk or item.batch_id != batch.pk:
        raise ValueError("Lote ou item pertence a outro tenant.")
    cnpj = str(item.normalized_data.get("cnpj", ""))
    if not cnpj:
        return CascadeResult(frozenset(), requested_blocks, 0, ("CNPJ_ABSENT",))
    available = adapters or default_adapters()
    ensure_provider_policies(tenant)
    missing = set(requested_blocks)
    delivered: set[str] = set()
    errors: list[str] = []
    calls = 0
    policies = ProviderPolicy.objects.filter(tenant=tenant, enabled=True).order_by(
        "priority", "provider"
    )
    for policy in policies:
        eligible = missing.intersection(policy.allowed_blocks)
        adapter = available.get(policy.provider)
        if not eligible or adapter is None:
            continue
        context = ProviderContext(
            tenant=tenant,
            batch=batch,
            item=item,
            cnpj=cnpj,
            missing_blocks=frozenset(eligible),
        )
        try:
            execution = execute_provider(adapter=adapter, policy=policy, context=context)
        except (
            ProviderNotConfigured,
            ProviderCircuitOpen,
            ProviderRateLimited,
            ProviderBudgetExceeded,
        ) as exc:
            errors.append(f"{policy.provider}:{type(exc).__name__}")
            continue
        except ProviderError as exc:
            errors.append(f"{policy.provider}:{type(exc).__name__}")
            continue
        calls += 1
        delivered.update(execution.delivered_blocks)
        missing.difference_update(execution.delivered_blocks)
        if not missing:
            break
    return CascadeResult(
        delivered_blocks=frozenset(delivered),
        missing_blocks=frozenset(missing),
        providers_called=calls,
        errors=tuple(errors),
    )
