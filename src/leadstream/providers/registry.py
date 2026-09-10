from __future__ import annotations

from django.conf import settings

from leadstream.billing.models import DataBlock
from leadstream.tenancy.models import Tenant

from .adapters.apify import ApifyDecisionMakerAdapter
from .adapters.bigdatacorp import BigDataCorpAdapter
from .adapters.bigquery import BigQueryOpenCNPJAdapter
from .adapters.generic import GenericPeopleEnrichmentAdapter
from .contracts import ProviderAdapter
from .models import ProviderPolicy


def default_adapters() -> dict[str, ProviderAdapter]:
    adapters: tuple[ProviderAdapter, ...] = (
        BigQueryOpenCNPJAdapter(),
        BigDataCorpAdapter(),
        ApifyDecisionMakerAdapter(),
        GenericPeopleEnrichmentAdapter(
            slug="open-enrich",
            base_url=settings.OPEN_ENRICH_URL or "",
            token=settings.OPEN_ENRICH_TOKEN or "",
            cost_cents=settings.OPEN_ENRICH_COST_CENTS,
        ),
        GenericPeopleEnrichmentAdapter(
            slug="premium-enrich",
            base_url=settings.PREMIUM_ENRICH_URL or "",
            token=settings.PREMIUM_ENRICH_TOKEN or "",
            cost_cents=settings.PREMIUM_ENRICH_COST_CENTS,
        ),
    )
    return {adapter.slug: adapter for adapter in adapters}


def ensure_provider_policies(tenant: Tenant) -> list[ProviderPolicy]:
    adapters = default_adapters()
    defaults = (
        (
            "open-cnpj-bigquery",
            "OpenCNPJ / BigQuery",
            10,
            0,
            [DataBlock.COMPANY_REGISTRY, DataBlock.DECISION_MAKER],
        ),
        (
            "bigdatacorp",
            "BigDataCorp",
            20,
            settings.BIGDATACORP_COST_CENTS,
            [DataBlock.DECISION_MAKER, DataBlock.DIRECT_EMAIL, DataBlock.DIRECT_PHONE],
        ),
        (
            "apify-decision-maker",
            "Apify — decisores públicos",
            30,
            settings.APIFY_COST_CENTS,
            [
                DataBlock.DECISION_MAKER,
                DataBlock.DIRECT_EMAIL,
                DataBlock.DIRECT_PHONE,
                DataBlock.SOCIAL_PROFILES,
            ],
        ),
        (
            "open-enrich",
            "Open Enrich",
            40,
            settings.OPEN_ENRICH_COST_CENTS,
            [DataBlock.DECISION_MAKER, DataBlock.DIRECT_EMAIL, DataBlock.DIRECT_PHONE],
        ),
        (
            "premium-enrich",
            "Fallback premium",
            50,
            settings.PREMIUM_ENRICH_COST_CENTS,
            [
                DataBlock.DECISION_MAKER,
                DataBlock.DIRECT_EMAIL,
                DataBlock.DIRECT_PHONE,
                DataBlock.SOCIAL_PROFILES,
            ],
        ),
    )
    policies = []
    for slug, name, priority, cost, blocks in defaults:
        policy, _ = ProviderPolicy.objects.get_or_create(
            tenant=tenant,
            provider=slug,
            defaults={
                "display_name": name,
                "enabled": adapters[slug].is_configured(),
                "priority": priority,
                "estimated_cost_cents": cost,
                "allowed_blocks": blocks,
            },
        )
        policies.append(policy)
    return policies
