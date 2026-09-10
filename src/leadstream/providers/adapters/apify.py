from __future__ import annotations

from typing import Any

import httpx
from django.conf import settings

from leadstream.billing.models import DataBlock
from leadstream.providers.contracts import ProviderContext, ProviderResult
from leadstream.providers.exceptions import (
    ProviderNotConfigured,
    ProviderPermanentError,
    ProviderTemporaryError,
)

from .mapping import person_candidates


class ApifyDecisionMakerAdapter:
    slug = "apify-decision-maker"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    def is_configured(self) -> bool:
        return bool(settings.APIFY_TOKEN and settings.APIFY_DECISION_MAKER_ACTOR_ID)

    def enrich(self, context: ProviderContext) -> ProviderResult:
        if not self.is_configured():
            raise ProviderNotConfigured("Apify não configurada.")
        actor_id = settings.APIFY_DECISION_MAKER_ACTOR_ID
        token = settings.APIFY_TOKEN
        assert actor_id is not None and token is not None
        actor = actor_id.replace("/", "~")
        url = (
            f"{settings.APIFY_BASE_URL.rstrip('/')}/acts/{actor}/"
            "run-sync-get-dataset-items"
        )
        client = self._client or httpx.Client(timeout=settings.APIFY_TIMEOUT_SECONDS)
        payload = {
            "cnpj": context.cnpj,
            "companyName": context.item.normalized_data.get("legal_name", ""),
            "maxResults": settings.APIFY_MAX_RESULTS_PER_COMPANY,
        }
        try:
            response = client.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
                params={"clean": "true", "format": "json"},
            )
            response.raise_for_status()
            body: Any = response.json()
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ProviderTemporaryError("Falha temporária ao executar actor Apify.") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code >= 500 or exc.response.status_code == 429:
                raise ProviderTemporaryError("Apify indisponível ou limitada.") from exc
            raise ProviderPermanentError("Actor Apify rejeitou a execução.") from exc
        if not isinstance(body, list):
            raise ProviderPermanentError("Dataset Apify fora do contrato esperado.")
        people = person_candidates(body, source_url=url, confidence=70)
        delivered: set[str] = set()
        if people:
            delivered.add(DataBlock.DECISION_MAKER)
        if any(person.socials for person in people):
            delivered.add(DataBlock.SOCIAL_PROFILES)
        if any(person.contacts for person in people):
            delivered.update((DataBlock.DIRECT_EMAIL, DataBlock.DIRECT_PHONE))
        return ProviderResult(
            outcome="SUCCEEDED" if people else "ABSENT",
            confirmed_cost_cents=settings.APIFY_COST_CENTS,
            people=people,
            delivered_blocks=frozenset(delivered),
            external_request_id=response.headers.get("x-apify-request-id", ""),
        )
