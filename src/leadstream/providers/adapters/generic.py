from __future__ import annotations

from typing import Any

import httpx

from leadstream.billing.models import DataBlock
from leadstream.providers.contracts import ProviderContext, ProviderResult
from leadstream.providers.exceptions import ProviderNotConfigured, ProviderTemporaryError

from .mapping import person_candidates


class GenericPeopleEnrichmentAdapter:
    def __init__(
        self,
        *,
        slug: str,
        base_url: str,
        token: str,
        cost_cents: int,
        timeout_seconds: float = 30.0,
        confidence: int = 75,
        client: httpx.Client | None = None,
    ) -> None:
        self.slug = slug
        self.base_url = base_url
        self.token = token
        self.cost_cents = cost_cents
        self.timeout_seconds = timeout_seconds
        self.confidence = confidence
        self._client = client

    def is_configured(self) -> bool:
        return bool(self.base_url and self.token)

    def enrich(self, context: ProviderContext) -> ProviderResult:
        if not self.is_configured():
            raise ProviderNotConfigured(f"{self.slug} não configurado.")
        client = self._client or httpx.Client(timeout=self.timeout_seconds)
        try:
            response = client.post(
                self.base_url,
                headers={"Authorization": f"Bearer {self.token}"},
                json={"cnpj": context.cnpj, "blocks": sorted(context.missing_blocks)},
            )
            response.raise_for_status()
            body: Any = response.json()
        except httpx.HTTPError as exc:
            raise ProviderTemporaryError(f"Falha ao consultar {self.slug}.") from exc
        people = person_candidates(body, source_url=self.base_url, confidence=self.confidence)
        delivered: set[str] = set()
        if people:
            delivered.add(DataBlock.DECISION_MAKER)
        if any(person.contacts for person in people):
            delivered.update((DataBlock.DIRECT_EMAIL, DataBlock.DIRECT_PHONE))
        if any(person.socials for person in people):
            delivered.add(DataBlock.SOCIAL_PROFILES)
        return ProviderResult(
            outcome="SUCCEEDED" if people else "ABSENT",
            confirmed_cost_cents=self.cost_cents,
            people=people,
            delivered_blocks=frozenset(delivered),
            external_request_id=response.headers.get("x-request-id", ""),
        )
