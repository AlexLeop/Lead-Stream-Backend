from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from django.conf import settings

from leadstream.billing.models import DataBlock
from leadstream.evidence.models import CaptureMethod, EvidenceStatus
from leadstream.providers.contracts import (
    FieldObservation,
    PersonCandidate,
    ProviderContext,
    ProviderResult,
)
from leadstream.providers.exceptions import ProviderNotConfigured, ProviderPermanentError

from .mapping import pick


@dataclass(frozen=True)
class QueryResponse:
    rows: tuple[dict[str, Any], ...]
    billed_bytes: int


QueryRunner = Callable[[str, dict[str, Any]], QueryResponse]


class BigQueryOpenCNPJAdapter:
    slug = "open-cnpj-bigquery"

    def __init__(self, runner: QueryRunner | None = None) -> None:
        self._runner = runner or self._run_query

    def is_configured(self) -> bool:
        return bool(settings.BIGQUERY_PROJECT_ID and settings.OPEN_CNPJ_BIGQUERY_SQL)

    def _run_query(self, sql: str, parameters: dict[str, Any]) -> QueryResponse:
        try:
            from google.cloud import bigquery
        except ImportError as exc:
            raise ProviderNotConfigured("Instale google-cloud-bigquery.") from exc
        query_parameters = [
            bigquery.ScalarQueryParameter(
                name,
                (
                    "BOOL"
                    if isinstance(value, bool)
                    else "INT64"
                    if isinstance(value, int)
                    else "STRING"
                ),
                value,
            )
            for name, value in parameters.items()
        ]
        job_config = bigquery.QueryJobConfig(
            query_parameters=query_parameters,
            maximum_bytes_billed=settings.BIGQUERY_MAXIMUM_BYTES_BILLED or None,
            use_query_cache=True,
        )
        client = bigquery.Client(project=settings.BIGQUERY_PROJECT_ID)
        job = client.query(sql, job_config=job_config)
        rows = tuple(
            dict(row.items()) for row in job.result(timeout=settings.BIGQUERY_TIMEOUT_SECONDS)
        )
        return QueryResponse(rows=rows, billed_bytes=int(job.total_bytes_billed or 0))

    def enrich(self, context: ProviderContext) -> ProviderResult:
        if not self.is_configured():
            raise ProviderNotConfigured("BigQuery/OpenCNPJ não configurado.")
        sql = settings.OPEN_CNPJ_BIGQUERY_SQL
        assert sql is not None
        response = self._runner(sql, {"cnpj": context.cnpj})
        if not response.rows:
            return ProviderResult(outcome="ABSENT", confirmed_cost_cents=self._cost(response))
        row = response.rows[0]
        observations: list[FieldObservation] = []
        field_map = {
            "company.legal_name": ("razao_social", "legal_name", "nome_empresarial"),
            "company.trade_name": ("nome_fantasia", "trade_name"),
            "company.registration_status": ("situacao_cadastral", "registration_status"),
            "company.primary_cnae": ("cnae_fiscal", "cnae_principal", "primary_cnae"),
            "company.city": ("municipio", "cidade", "city"),
            "company.state": ("uf", "estado", "state"),
        }
        for field_path, aliases in field_map.items():
            value = pick(row, *aliases)
            if value not in (None, "", []):
                observations.append(
                    FieldObservation(
                        field_path=field_path,
                        value=value,
                        confidence=100,
                        evidence_status=EvidenceStatus.CONFIRMED,
                        method=CaptureMethod.DATASET,
                        external_id=context.cnpj,
                    )
                )
        people: list[PersonCandidate] = []
        partners = pick(row, "socios", "qsa", "partners", default=[])
        if isinstance(partners, list):
            for index, partner in enumerate(partners):
                if not isinstance(partner, dict):
                    continue
                name = str(pick(partner, "nome_socio", "nome", "name")).strip()
                if not name:
                    continue
                qualification = str(
                    pick(partner, "qualificacao_socio", "qualificacao", "role", default="SOCIO")
                )
                people.append(
                    PersonCandidate(
                        full_name=name,
                        external_key=str(
                            pick(partner, "documento", "id", default=f"{context.cnpj}:{index}")
                        ),
                        qualification=qualification[:80],
                        observed_title=qualification[:160],
                        confidence=100,
                        evidence_status=EvidenceStatus.CONFIRMED,
                    )
                )
        delivered = {DataBlock.COMPANY_REGISTRY}
        if people:
            delivered.add(DataBlock.DECISION_MAKER)
        return ProviderResult(
            outcome="SUCCEEDED",
            confirmed_cost_cents=self._cost(response),
            observations=tuple(observations),
            people=tuple(people),
            delivered_blocks=frozenset(delivered),
            external_request_id=context.cnpj,
        )

    def _cost(self, response: QueryResponse) -> int:
        tebibytes = response.billed_bytes / (1024**4)
        return math.ceil(tebibytes * settings.BIGQUERY_COST_CENTS_PER_TIB)

    def discover(self, filters: dict[str, str], *, limit: int, offset: int) -> QueryResponse:
        sql = settings.OPEN_CNPJ_DISCOVERY_SQL
        if not sql:
            raise ProviderPermanentError("SQL de descoberta não configurado.")
        parameters: dict[str, Any] = {**filters, "limit": limit, "offset": offset}
        return self._runner(sql, parameters)
