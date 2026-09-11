from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from django.conf import settings

import re
from leadstream.billing.models import DataBlock
from leadstream.evidence.models import CaptureMethod, EvidenceStatus
from leadstream.providers.contracts import (
    ContactCandidate,
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
        query_parameters: list[Any] = []
        for name, value in parameters.items():
            if isinstance(value, (list, tuple)):
                query_parameters.append(bigquery.ArrayQueryParameter(name, "STRING", list(value)))
                continue
            parameter_type = (
                "BOOL"
                if isinstance(value, bool)
                else "INT64"
                if isinstance(value, int)
                else "STRING"
            )
            query_parameters.append(bigquery.ScalarQueryParameter(name, parameter_type, value))
        job_config = bigquery.QueryJobConfig(
            query_parameters=query_parameters,
            maximum_bytes_billed=settings.BIGQUERY_MAXIMUM_BYTES_BILLED or None,
            use_query_cache=True,
        )
        client_kwargs: dict[str, Any] = {"project": settings.BIGQUERY_PROJECT_ID}
        creds_json = getattr(settings, "GOOGLE_CREDENTIALS_JSON", None)
        creds_file = getattr(settings, "GOOGLE_APPLICATION_CREDENTIALS", None)
        if creds_json:
            from google.oauth2 import service_account

            try:
                info = json.loads(creds_json) if isinstance(creds_json, str) else creds_json
                client_kwargs["credentials"] = (
                    service_account.Credentials.from_service_account_info(  # type: ignore[no-untyped-call]
                        info
                    )
                )
            except (ValueError, TypeError, json.JSONDecodeError, OSError):
                pass
        elif creds_file:
            from google.oauth2 import service_account

            try:
                client_kwargs["credentials"] = (
                    service_account.Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
                        creds_file
                    )
                )
            except (ValueError, TypeError, OSError):
                pass
        client = bigquery.Client(**client_kwargs)
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

        contacts: list[ContactCandidate] = []
        email = pick(row, "email")
        if email and "@" in str(email):
            contacts.append(
                ContactCandidate(
                    kind="EMAIL",
                    value=str(email).strip().lower(),
                    confidence=getattr(settings, "BIGQUERY_CONFIDENCE", 100),
                    evidence_status=EvidenceStatus.CONFIRMED,
                    source_url="",
                    external_id=context.cnpj,
                )
            )
        ddd = str(pick(row, "ddd_1", "ddd", default="") or "").strip()
        phone = str(pick(row, "telefone_1", "telefone", default="") or "").strip()
        if phone:
            phone_clean = "".join(c for c in f"{ddd}{phone}" if c.isdigit())
            if len(phone_clean) in (10, 11):
                contacts.append(
                    ContactCandidate(
                        kind="PHONE",
                        value=phone_clean,
                        confidence=getattr(settings, "BIGQUERY_CONFIDENCE", 100),
                        evidence_status=EvidenceStatus.CONFIRMED,
                        source_url="",
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
                confidence = getattr(settings, "BIGQUERY_CONFIDENCE", 100)
                people.append(
                    PersonCandidate(
                        full_name=name,
                        external_key=str(
                            pick(partner, "documento", "id", default=f"{context.cnpj}:{index}")
                        ),
                        qualification=qualification[:80],
                        observed_title=qualification[:160],
                        confidence=confidence,
                        evidence_status=EvidenceStatus.CONFIRMED,
                    )
                )

        if not people:
            natureza = str(pick(row, "natureza_juridica", default=""))
            legal_name = str(pick(row, "razao_social", "legal_name", default=""))
            if (natureza == "2135" or str(pick(row, "porte", default="")) == "1") and legal_name:
                clean_name = re.sub(r"^[0-9.\/\-\s]+", "", legal_name).strip()
                if clean_name:
                    people.append(
                        PersonCandidate(
                            full_name=clean_name,
                            external_key=f"{context.cnpj}:titular",
                            qualification="PROPRIETARIO",
                            observed_title="Empresário / Titular",
                            confidence=getattr(settings, "BIGQUERY_CONFIDENCE", 100),
                            evidence_status=EvidenceStatus.CONFIRMED,
                        )
                    )

        if contacts and people:
            primary = people[0]
            people[0] = PersonCandidate(
                full_name=primary.full_name,
                external_key=primary.external_key,
                qualification=primary.qualification,
                observed_title=primary.observed_title,
                seniority=primary.seniority,
                buying_role=primary.buying_role,
                buying_role_is_inferred=primary.buying_role_is_inferred,
                confidence=primary.confidence,
                evidence_status=primary.evidence_status,
                contacts=tuple(contacts),
                socials=primary.socials,
                source_url=primary.source_url,
            )

        delivered = {DataBlock.COMPANY_REGISTRY}
        if people:
            delivered.add(DataBlock.DECISION_MAKER)
        if any(c.kind == "EMAIL" for c in contacts):
            delivered.add(DataBlock.DIRECT_EMAIL)
        if any(c.kind == "PHONE" for c in contacts):
            delivered.add(DataBlock.DIRECT_PHONE)

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

    def is_discovery_configured(self) -> bool:
        return bool(settings.BIGQUERY_PROJECT_ID and settings.OPEN_CNPJ_DISCOVERY_SQL)

    def discover(self, filters: dict[str, Any], *, limit: int, offset: int) -> QueryResponse:
        if not self.is_discovery_configured():
            raise ProviderNotConfigured("Descoberta BigQuery/OpenCNPJ não configurada.")
        sql = settings.OPEN_CNPJ_DISCOVERY_SQL
        if not sql:
            raise ProviderPermanentError("SQL de descoberta não configurado.")
        parameters: dict[str, Any] = {**filters, "limit": limit, "offset": offset}
        return self._runner(sql, parameters)
