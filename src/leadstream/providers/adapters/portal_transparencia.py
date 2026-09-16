from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from leadstream.billing.models import DataBlock
from leadstream.entities.normalization import fingerprint_value, only_digits
from leadstream.evidence.models import CaptureMethod, EvidenceStatus
from leadstream.providers.contracts import (
    FieldObservation,
    ProviderContext,
    ProviderQuota,
    ProviderResult,
)
from leadstream.providers.exceptions import (
    ProviderNotConfigured,
    ProviderPermanentError,
    ProviderRateLimited,
    ProviderTemporaryError,
)

RISK_ENDPOINTS: tuple[tuple[str, str, str], ...] = (
    ("CEIS", "ceis", "codigoSancionado"),
    ("CNEP", "cnep", "codigoSancionado"),
    ("CEPIM", "cepim", "cnpjSancionado"),
    ("ACORDO_LENIENCIA", "acordos-leniencia", "cnpjSancionado"),
)
CONTRACT_ENDPOINT = ("CONTRATOS", "contratos/cpf-cnpj", "cpfCnpj")

# Lista publicada no cadastro da API. Nenhuma destas rotas é utilizada pelo adapter atual,
# mas o contrato fica explícito para evitar que uma expansão futura use o teto incorreto.
RESTRICTED_ENDPOINTS = frozenset(
    {
        "despesas/documentos-por-favorecido",
        "bolsa-familia-disponivel-por-cpf-ou-nis",
        "bolsa-familia-por-municipio",
        "bolsa-familia-sacado-por-nis",
        "auxilio-emergencial-beneficiario-por-municipio",
        "auxilio-emergencial-por-cpf-ou-nis",
        "auxilio-emergencial-por-municipio",
        "seguro-defeso-codigo",
    }
)


def portal_requests_per_minute(
    *, restricted: bool = False, moment: datetime | None = None
) -> int:
    if restricted:
        return settings.PORTAL_TRANSPARENCIA_RESTRICTED_RPM
    local = timezone.localtime(moment or timezone.now())
    if 0 <= local.hour < 6:
        return settings.PORTAL_TRANSPARENCIA_NIGHT_RPM
    return settings.PORTAL_TRANSPARENCIA_DAY_RPM


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _document_matches(record: dict[str, Any], cnpj: str, source: str) -> bool:
    candidates: list[Any] = []
    if source in {"CEIS", "CNEP"}:
        candidates.extend(
            (
                _dict(record.get("sancionado")).get("codigoFormatado"),
                _dict(record.get("pessoa")).get("cnpjFormatado"),
            )
        )
    elif source == "CEPIM":
        candidates.append(_dict(record.get("pessoaJuridica")).get("cnpjFormatado"))
    elif source == "ACORDO_LENIENCIA":
        candidates.extend(
            company.get("cnpj") or company.get("cnpjFormatado")
            for company in record.get("sancoes", [])
            if isinstance(company, dict)
        )
    elif source == "CONTRATOS":
        candidates.append(_dict(record.get("fornecedor")).get("cnpjFormatado"))
    documents = [only_digits(_text(value)) for value in candidates if value]
    return not documents or cnpj in documents


def _sanction_record(record: dict[str, Any], source: str) -> dict[str, Any]:
    if source == "CEPIM":
        company = _dict(record.get("pessoaJuridica"))
        organ = _dict(record.get("orgaoSuperior"))
        agreement = _dict(record.get("convenio"))
        return {
            "source": source,
            "record_id": record.get("id"),
            "sanctioned_name": company.get("razaoSocialReceita") or company.get("nome"),
            "document": company.get("cnpjFormatado"),
            "reason": record.get("motivo"),
            "responsible_organ": organ.get("nome"),
            "agreement_number": agreement.get("numero"),
            "agreement_object": agreement.get("objeto"),
            "reference_date": record.get("dataReferencia"),
        }
    if source == "ACORDO_LENIENCIA":
        companies = [
            {
                "legal_name": item.get("razaoSocial")
                or item.get("nomeInformadoOrgaoResponsavel"),
                "trade_name": item.get("nomeFantasia"),
                "cnpj": item.get("cnpjFormatado") or item.get("cnpj"),
            }
            for item in record.get("sancoes", [])
            if isinstance(item, dict)
        ]
        return {
            "source": source,
            "record_id": record.get("id"),
            "status": record.get("situacaoAcordo"),
            "starts_on": record.get("dataInicioAcordo"),
            "ends_on": record.get("dataFimAcordo"),
            "responsible_organ": record.get("orgaoResponsavel"),
            "companies": companies,
        }
    sanctioned = _dict(record.get("sancionado"))
    person = _dict(record.get("pessoa"))
    sanction_type = _dict(record.get("tipoSancao"))
    organ = _dict(record.get("orgaoSancionador"))
    return {
        "source": source,
        "record_id": record.get("id"),
        "sanctioned_name": sanctioned.get("nome")
        or person.get("razaoSocialReceita")
        or person.get("nome"),
        "document": sanctioned.get("codigoFormatado") or person.get("cnpjFormatado"),
        "sanction_type": sanction_type.get("descricaoPortal")
        or sanction_type.get("descricaoResumida"),
        "sanctioning_organ": organ.get("nome"),
        "starts_on": record.get("dataInicioSancao"),
        "ends_on": record.get("dataFimSancao"),
        "published_on": record.get("dataPublicacaoSancao"),
        "publication_url": record.get("linkPublicacao"),
        "process_number": record.get("numeroProcesso"),
        "fine_value": record.get("valorMulta") if source == "CNEP" else None,
    }


def _contract_record(record: dict[str, Any]) -> dict[str, Any]:
    managing_unit = _dict(record.get("unidadeGestora"))
    return {
        "record_id": record.get("id"),
        "number": record.get("numero"),
        "object": record.get("objeto"),
        "process_number": record.get("numeroProcesso"),
        "status": record.get("situacaoContrato"),
        "signed_on": record.get("dataAssinatura"),
        "starts_on": record.get("dataInicioVigencia"),
        "ends_on": record.get("dataFimVigencia"),
        "managing_unit": managing_unit.get("nome"),
        "initial_value": record.get("valorInicialCompra"),
        "final_value": record.get("valorFinalCompra"),
    }


class PortalTransparenciaAdapter:
    slug = "portal-transparencia"
    resumable = True

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    def is_configured(self) -> bool:
        return bool(settings.PORTAL_TRANSPARENCIA_TOKEN)

    def quota_for(self, context: ProviderContext) -> ProviderQuota:
        units = 0
        if DataBlock.GOVERNMENT_RISK in context.missing_blocks:
            units += len(RISK_ENDPOINTS)
        if DataBlock.PUBLIC_SECTOR in context.missing_blocks:
            units += 1
        return ProviderQuota(
            scope="portal-transparencia-api",
            requests_per_minute=portal_requests_per_minute(),
            units=max(units, 1),
        )

    def _request(
        self,
        *,
        client: httpx.Client,
        endpoint: str,
        parameter: str,
        cnpj: str,
    ) -> tuple[list[dict[str, Any]], str]:
        cache_key = f"portal-transparencia:{endpoint}:{cnpj}:page-1"
        cached = cache.get(cache_key)
        if isinstance(cached, dict) and isinstance(cached.get("items"), list):
            return cached["items"], _text(cached.get("request_id"))
        url = f"{settings.PORTAL_TRANSPARENCIA_BASE_URL.rstrip('/')}/{endpoint}"
        try:
            response = client.get(
                url,
                headers={
                    "chave-api-dados": str(settings.PORTAL_TRANSPARENCIA_TOKEN),
                    "Accept": "application/json",
                },
                params={parameter: cnpj, "pagina": 1},
            )
            response.raise_for_status()
            payload: Any = response.json()
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ProviderTemporaryError(
                "Portal da Transparência temporariamente indisponível."
            ) from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raw_retry_after = exc.response.headers.get("Retry-After", "60")
                try:
                    retry_after = int(raw_retry_after)
                except ValueError:
                    retry_after = 60
                raise ProviderRateLimited(
                    "Quota do Portal da Transparência atingida.",
                    retry_after_seconds=retry_after,
                ) from exc
            if exc.response.status_code >= 500:
                raise ProviderTemporaryError(
                    "Portal da Transparência temporariamente indisponível."
                ) from exc
            if exc.response.status_code in {401, 403}:
                raise ProviderNotConfigured(
                    "Token do Portal da Transparência inválido ou sem acesso."
                ) from exc
            raise ProviderPermanentError("Consulta ao Portal da Transparência rejeitada.") from exc
        except ValueError as exc:
            raise ProviderPermanentError(
                "Resposta do Portal da Transparência não contém JSON válido."
            ) from exc
        if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
            raise ProviderPermanentError(
                "Resposta do Portal da Transparência fora do contrato esperado."
            )
        request_id = response.headers.get("x-request-id", "")
        items = list(payload)
        cache.set(
            cache_key,
            {"items": items, "request_id": request_id},
            timeout=settings.PORTAL_TRANSPARENCIA_CACHE_SECONDS,
        )
        return items, request_id

    def enrich(self, context: ProviderContext) -> ProviderResult:
        if not self.is_configured():
            raise ProviderNotConfigured("Portal da Transparência não configurado.")
        cnpj = only_digits(context.cnpj)
        if len(cnpj) != 14:
            raise ProviderPermanentError("CNPJ inválido para consulta governamental.")
        if self._client is not None:
            return self._enrich_with_client(context=context, cnpj=cnpj, client=self._client)
        with httpx.Client(
            timeout=settings.PORTAL_TRANSPARENCIA_TIMEOUT_SECONDS,
            follow_redirects=True,
        ) as client:
            return self._enrich_with_client(context=context, cnpj=cnpj, client=client)

    def _enrich_with_client(
        self,
        *,
        context: ProviderContext,
        cnpj: str,
        client: httpx.Client,
    ) -> ProviderResult:
        observations: list[FieldObservation] = []
        delivered: set[str] = set()
        request_ids: list[str] = []
        payload_for_hash: dict[str, Any] = {}
        base_url = settings.PORTAL_TRANSPARENCIA_BASE_URL.rstrip("/")

        if DataBlock.GOVERNMENT_RISK in context.missing_blocks:
            risk_records: list[dict[str, Any]] = []
            checked_sources: list[str] = []
            for source, endpoint, parameter in RISK_ENDPOINTS:
                records, request_id = self._request(
                    client=client,
                    endpoint=endpoint,
                    parameter=parameter,
                    cnpj=cnpj,
                )
                checked_sources.append(source)
                if request_id:
                    request_ids.append(request_id)
                risk_records.extend(
                    _sanction_record(record, source)
                    for record in records
                    if _document_matches(record, cnpj, source)
                )
            risk = {
                "status": "MATCH_FOUND" if risk_records else "NO_MATCH_ON_CHECKED_SOURCES",
                "has_matches": bool(risk_records),
                "match_count": len(risk_records),
                "checked_sources": checked_sources,
                "records": risk_records,
                "pagination": "FIRST_PAGE_PER_SOURCE",
            }
            payload_for_hash["government_risk"] = risk
            observations.append(
                FieldObservation(
                    field_path="company.government_risk",
                    value=risk,
                    confidence=100,
                    evidence_status=EvidenceStatus.TECHNICALLY_VALIDATED,
                    method=CaptureMethod.API,
                    source_url=f"{base_url}/ceis",
                    external_id=f"risk:{cnpj}",
                    metadata={"official_source": "CGU", "queried_by": "CNPJ"},
                )
            )
            delivered.add(DataBlock.GOVERNMENT_RISK)

        if DataBlock.PUBLIC_SECTOR in context.missing_blocks:
            source, endpoint, parameter = CONTRACT_ENDPOINT
            records, request_id = self._request(
                client=client,
                endpoint=endpoint,
                parameter=parameter,
                cnpj=cnpj,
            )
            if request_id:
                request_ids.append(request_id)
            contracts = [
                _contract_record(record)
                for record in records
                if _document_matches(record, cnpj, source)
            ]
            public_sector = {
                "has_federal_contracts": bool(contracts),
                "contract_count": len(contracts),
                "contracts": contracts,
                "pagination": "FIRST_PAGE",
            }
            payload_for_hash["public_sector"] = public_sector
            observations.append(
                FieldObservation(
                    field_path="company.public_sector_profile",
                    value=public_sector,
                    confidence=100,
                    evidence_status=EvidenceStatus.TECHNICALLY_VALIDATED,
                    method=CaptureMethod.API,
                    source_url=f"{base_url}/{endpoint}",
                    external_id=f"contracts:{cnpj}",
                    metadata={"official_source": "CGU", "queried_by": "CNPJ"},
                )
            )
            delivered.add(DataBlock.PUBLIC_SECTOR)

        return ProviderResult(
            outcome="SUCCEEDED" if observations else "ABSENT",
            confirmed_cost_cents=settings.PORTAL_TRANSPARENCIA_COST_CENTS,
            observations=tuple(observations),
            delivered_blocks=frozenset(delivered),
            external_request_id=",".join(dict.fromkeys(request_ids))[:255],
            raw_payload_hash=fingerprint_value(payload_for_hash) if payload_for_hash else "",
        )
