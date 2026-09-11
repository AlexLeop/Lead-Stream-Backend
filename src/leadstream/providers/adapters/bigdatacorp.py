from __future__ import annotations

from typing import Any

import httpx
from django.conf import settings

from leadstream.billing.models import DataBlock
from leadstream.evidence.models import CaptureMethod, EvidenceStatus
from leadstream.providers.contracts import FieldObservation, ProviderContext, ProviderResult
from leadstream.providers.exceptions import (
    ProviderNotConfigured,
    ProviderPermanentError,
    ProviderTemporaryError,
)

from .mapping import person_candidates, pick


class BigDataCorpAdapter:
    slug = "bigdatacorp"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    def is_configured(self) -> bool:
        return bool(settings.BIGDATACORP_ACCESS_TOKEN and settings.BIGDATACORP_TOKEN_ID)

    def enrich(self, context: ProviderContext) -> ProviderResult:
        if not self.is_configured():
            raise ProviderNotConfigured("BigDataCorp não configurada.")
        access_token = settings.BIGDATACORP_ACCESS_TOKEN
        token_id = settings.BIGDATACORP_TOKEN_ID
        assert access_token is not None and token_id is not None
        url = f"{settings.BIGDATACORP_BASE_URL.rstrip('/')}/empresas"
        headers = {
            "AccessToken": access_token,
            "TokenId": token_id,
            "Accept": "application/json",
        }
        payload = {"q": f"doc{{{context.cnpj}}}", "Datasets": settings.BIGDATACORP_DATASETS}
        client = self._client or httpx.Client(timeout=settings.BIGDATACORP_TIMEOUT_SECONDS)
        try:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            body: Any = response.json()
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ProviderTemporaryError("Falha temporária na BigDataCorp.") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code >= 500 or exc.response.status_code == 429:
                raise ProviderTemporaryError("BigDataCorp indisponível ou limitada.") from exc
            raise ProviderPermanentError("Consulta BigDataCorp rejeitada.") from exc
        if not isinstance(body, (dict, list)):
            raise ProviderPermanentError("Resposta BigDataCorp fora do contrato esperado.")
        confidence = getattr(settings, "BIGDATACORP_CONFIDENCE", 80)
        people = person_candidates(body, source_url=url, confidence=confidence)
        root = body if isinstance(body, dict) else {}
        observations: list[FieldObservation] = []
        company_fields = {
            "company.email_generic": ("emails", "email"),
            "company.phone_generic": ("phones", "telefones", "phone"),
            "company.website": ("website", "site", "domain"),
        }
        for field_path, aliases in company_fields.items():
            value = pick(root, *aliases)
            if value not in (None, "", []):
                observations.append(
                    FieldObservation(
                        field_path=field_path,
                        value=value,
                        confidence=confidence,
                        evidence_status=EvidenceStatus.OBSERVED,
                        method=CaptureMethod.API,
                        source_url=url,
                    )
                )
        delivered: set[str] = set()
        if people:
            delivered.add(DataBlock.DECISION_MAKER)
        if any(person.contacts for person in people):
            delivered.update((DataBlock.DIRECT_EMAIL, DataBlock.DIRECT_PHONE))
        return ProviderResult(
            outcome="SUCCEEDED" if observations or people else "ABSENT",
            confirmed_cost_cents=settings.BIGDATACORP_COST_CENTS,
            observations=tuple(observations),
            people=people,
            delivered_blocks=frozenset(delivered),
            external_request_id=response.headers.get("x-request-id", ""),
        )
