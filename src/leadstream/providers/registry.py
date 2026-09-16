from __future__ import annotations

from django.conf import settings

from leadstream.billing.models import DataBlock
from leadstream.tenancy.models import Tenant

from .adapters.apify import ApifyDecisionMakerAdapter
from .adapters.bigdatacorp import BigDataCorpAdapter
from .adapters.bigquery import BigQueryOpenCNPJAdapter
from .adapters.generic import GenericPeopleEnrichmentAdapter
from .adapters.portal_transparencia import PortalTransparenciaAdapter
from .contracts import ProviderAdapter
from .models import ProviderPolicy


def default_adapters() -> dict[str, ProviderAdapter]:
    adapters: tuple[ProviderAdapter, ...] = (
        BigQueryOpenCNPJAdapter(),
        PortalTransparenciaAdapter(),
        BigDataCorpAdapter(),
        ApifyDecisionMakerAdapter(),
        GenericPeopleEnrichmentAdapter(
            slug="open-enrich",
            base_url=settings.OPEN_ENRICH_URL or "",
            token=settings.OPEN_ENRICH_TOKEN or "",
            cost_cents=settings.OPEN_ENRICH_COST_CENTS,
            timeout_seconds=float(settings.OPEN_ENRICH_TIMEOUT_SECONDS),
            confidence=settings.OPEN_ENRICH_CONFIDENCE,
        ),
        GenericPeopleEnrichmentAdapter(
            slug="premium-enrich",
            base_url=settings.PREMIUM_ENRICH_URL or "",
            token=settings.PREMIUM_ENRICH_TOKEN or "",
            cost_cents=settings.PREMIUM_ENRICH_COST_CENTS,
            timeout_seconds=float(settings.PREMIUM_ENRICH_TIMEOUT_SECONDS),
            confidence=settings.PREMIUM_ENRICH_CONFIDENCE,
        ),
    )
    return {adapter.slug: adapter for adapter in adapters}


def ensure_provider_policies(tenant: Tenant) -> list[ProviderPolicy]:
    adapters = default_adapters()
    defaults = (
        (
            "open-cnpj-bigquery",
            "OpenCNPJ / BigQuery",
            settings.BIGQUERY_PROVIDER_PRIORITY,
            settings.BIGQUERY_COST_CENTS,
            [
                DataBlock.COMPANY_REGISTRY,
                DataBlock.DECISION_MAKER,
                DataBlock.DIRECT_EMAIL,
                DataBlock.DIRECT_PHONE,
            ],
        ),
        (
            "portal-transparencia",
            "Portal da Transparência / CGU",
            settings.PORTAL_TRANSPARENCIA_PROVIDER_PRIORITY,
            settings.PORTAL_TRANSPARENCIA_COST_CENTS,
            [DataBlock.GOVERNMENT_RISK, DataBlock.PUBLIC_SECTOR],
        ),
        (
            "bigdatacorp",
            "BigDataCorp",
            settings.BIGDATACORP_PROVIDER_PRIORITY,
            settings.BIGDATACORP_COST_CENTS,
            [DataBlock.DECISION_MAKER, DataBlock.DIRECT_EMAIL, DataBlock.DIRECT_PHONE],
        ),
        (
            "apify-decision-maker",
            "Apify — decisores públicos",
            settings.APIFY_PROVIDER_PRIORITY,
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
            settings.OPEN_ENRICH_PROVIDER_PRIORITY,
            settings.OPEN_ENRICH_COST_CENTS,
            [DataBlock.DECISION_MAKER, DataBlock.DIRECT_EMAIL, DataBlock.DIRECT_PHONE],
        ),
        (
            "premium-enrich",
            "Fallback premium",
            settings.PREMIUM_ENRICH_PROVIDER_PRIORITY,
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
        policy, created = ProviderPolicy.objects.get_or_create(
            tenant=tenant,
            provider=slug,
            defaults={
                "display_name": name,
                "enabled": adapters[slug].is_configured(),
                "priority": priority,
                "estimated_cost_cents": cost,
                "requests_per_minute": (
                    settings.PORTAL_TRANSPARENCIA_NIGHT_RPM
                    if slug == "portal-transparencia"
                    else 60
                ),
                "allowed_blocks": blocks,
                "config": (
                    {
                        "quota_scope": "portal-transparencia-api",
                        "day_rpm": settings.PORTAL_TRANSPARENCIA_DAY_RPM,
                        "night_rpm": settings.PORTAL_TRANSPARENCIA_NIGHT_RPM,
                        "restricted_rpm": settings.PORTAL_TRANSPARENCIA_RESTRICTED_RPM,
                        "terms_url": "https://portaldatransparencia.gov.br/api-de-dados",
                    }
                    if slug == "portal-transparencia"
                    else {}
                ),
            },
        )
        if not created:
            configured = adapters[slug].is_configured()
            if policy.enabled != configured:
                policy.enabled = configured
                policy.save(update_fields=("enabled",))
        policies.append(policy)
    return policies
