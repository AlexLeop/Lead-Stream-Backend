from __future__ import annotations

from datetime import timedelta
from decimal import ROUND_CEILING, Decimal
from typing import Any
from urllib.parse import quote

import httpx
from django.conf import settings
from django.utils import timezone

from leadstream.billing.models import ProviderCall
from leadstream.providers.contracts import ProviderContext, ProviderResult
from leadstream.providers.exceptions import (
    ProviderNotConfigured,
    ProviderPending,
    ProviderPermanentError,
    ProviderSubmissionUncertain,
)

from .mapping import person_candidates


class ApifyDecisionMakerAdapter:
    slug = "apify-decision-maker"
    resumable = True

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    def is_configured(self) -> bool:
        return bool(
            settings.APIFY_TOKEN
            and settings.APIFY_DECISION_MAKER_ACTOR_ID
            and settings.APIFY_USD_RATE_CENTS > 0
            and settings.APIFY_COST_CENTS > 0
        )

    def _save(self, context: ProviderContext, state: dict[str, Any], *, wait: bool = False) -> None:
        if not context.call_id:
            raise ProviderPermanentError("Apify exige uma chamada durável registrada.")
        changed = ProviderCall.objects.filter(
            pk=context.call_id,
            tenant=context.tenant,
            status="REQUESTED",
            execution_token=context.execution_token,
        ).update(
            provider_state=state,
            next_poll_at=timezone.now() + timedelta(seconds=settings.APIFY_POLL_SECONDS)
            if wait
            else None,
        )
        if not changed:
            raise ProviderPending("Execução remota passou a outro trabalhador.")

    def enrich(self, context: ProviderContext) -> ProviderResult:
        if not self.is_configured():
            raise ProviderNotConfigured("Apify exige actor, token, reserva e câmbio configurados.")
        if not context.call_id:
            raise ProviderPermanentError("Apify exige uma chamada durável registrada.")
        call = ProviderCall.objects.get(pk=context.call_id, tenant=context.tenant)
        state = dict(call.provider_state)
        if not state:
            if call.estimated_cost_cents <= 0:
                raise ProviderPermanentError("Defina uma reserva positiva para o actor.")
            actor_id = str(settings.APIFY_DECISION_MAKER_ACTOR_ID or "").replace("/", "~")
            base_url = str(settings.APIFY_BASE_URL or "").rstrip("/")
            state = {
                "phase": "SUBMITTING",
                "cost_status": "UNCONFIRMED",
                "fx_cents": settings.APIFY_USD_RATE_CENTS,
                "actor": actor_id,
                "max_results": min(max(settings.APIFY_MAX_RESULTS_PER_COMPANY, 1), 1000),
                "base_url": base_url,
            }
            self._save(context, state)
            submit = True
        else:
            submit = False
            if not state.get("run_id"):
                raise ProviderSubmissionUncertain("Envio Apify sem confirmação; reenvio bloqueado.")
        elapsed = (timezone.now() - call.started_at).total_seconds()
        if elapsed > settings.APIFY_RUN_TIMEOUT_SECONDS + 600:
            raise ProviderSubmissionUncertain("Apify excedeu o prazo de reconciliação automática.")
        client = self._client or httpx.Client(timeout=min(settings.APIFY_TIMEOUT_SECONDS, 30))
        try:
            return self._advance(context, call, state, client, submit=submit)
        finally:
            if self._client is None:
                client.close()

    def _advance(
        self,
        context: ProviderContext,
        call: ProviderCall,
        state: dict[str, Any],
        client: httpx.Client,
        *,
        submit: bool,
    ) -> ProviderResult:
        headers = {"Authorization": f"Bearer {settings.APIFY_TOKEN}"}
        base = state["base_url"]
        try:
            if submit:
                # Contrato do actor configurado: cnpj, companyName e maxResults.
                response = client.post(
                    f"{base}/actors/{quote(state['actor'], safe='~')}/runs",
                    headers=headers,
                    json={
                        "cnpj": context.cnpj,
                        "companyName": context.item.normalized_data.get("legal_name", ""),
                        "maxResults": state["max_results"],
                    },
                    params={
                        "waitForFinish": 0,
                        "timeout": settings.APIFY_RUN_TIMEOUT_SECONDS,
                        "maxItems": state["max_results"],
                        "maxTotalChargeUsd": str(
                            Decimal(call.estimated_cost_cents) / Decimal(state["fx_cents"])
                        ),
                    },
                )
            else:
                response = client.get(
                    f"{base}/actor-runs/{quote(state['run_id'], safe='')}",
                    headers=headers,
                )
            response.raise_for_status()
            run = response.json()["data"]
            if not isinstance(run, dict) or not isinstance(run.get("id"), str) or not run["id"]:
                raise ValueError("run inválida")
            state.update(
                run_id=run["id"],
                dataset_id=run.get("defaultDatasetId", ""),
                phase=run.get("status", "UNKNOWN"),
            )
            if "usageTotalUsd" in run:
                usd = Decimal(str(run["usageTotalUsd"]))
                if not usd.is_finite() or usd < 0:
                    raise ValueError("custo inválido")
                state["usage_total_usd"] = str(usd)
            self._save(context, state)
        except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
            self._save(context, state, wait=True)
            if submit:
                # A API de início não documenta uma chave de idempotência.
                # Timeout/5xx pode significar um actor pago já iniciado.
                msg = "Não foi possível confirmar o início Apify."
                raise ProviderSubmissionUncertain(msg) from exc
            raise ProviderPending("Consulta Apify temporariamente indisponível.") from exc
        if state["phase"] not in {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}:
            self._save(context, state, wait=True)
            raise ProviderPending("Actor Apify em processamento.")
        if "usage_total_usd" not in state:
            self._save(context, state, wait=True)
            raise ProviderPending("Aguardando custo final informado pelo Apify.")
        usage_decimal = Decimal(state["usage_total_usd"]) * Decimal(state["fx_cents"])
        cost = int(usage_decimal.to_integral_value(rounding=ROUND_CEILING))
        state["cost_status"] = "REPORTED"
        self._save(context, state)
        if state["phase"] != "SUCCEEDED":
            return ProviderResult(
                outcome="FAILED", confirmed_cost_cents=cost, external_request_id=state["run_id"]
            )
        if not state["dataset_id"]:
            raise ProviderPermanentError("Execução Apify concluída sem dataset.")
        rows: list[dict[str, Any]] = []
        try:
            # GETs são repetíveis; a memória é limitada por empresa, não pelo tamanho do lote.
            while len(rows) < state["max_results"]:
                limit = min(settings.APIFY_DATASET_PAGE_SIZE, state["max_results"] - len(rows))
                response = client.get(
                    f"{base}/datasets/{quote(state['dataset_id'], safe='')}/items",
                    headers=headers,
                    params={"format": "json", "offset": len(rows), "limit": limit},
                )
                response.raise_for_status()
                page = response.json()
                if (
                    not isinstance(page, list)
                    or len(page) > limit
                    or any(not isinstance(row, dict) for row in page)
                ):
                    raise ValueError("dataset inválido")
                rows.extend(page)
                if len(page) < limit:
                    break
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            self._save(context, state, wait=True)
            raise ProviderPending("Coleta do dataset Apify será retomada.") from exc
        people = person_candidates(
            rows,
            source_url=f"https://console.apify.com/actors/runs/{state['run_id']}",
            confidence=70,
        )
        return ProviderResult(
            outcome="SUCCEEDED" if people else "ABSENT",
            confirmed_cost_cents=cost,
            people=people,
            external_request_id=state["run_id"],
        )
