from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from leadstream.billing.models import DataBlock
from leadstream.entities.normalization import fingerprint_value, only_digits
from leadstream.evidence.models import CaptureMethod, EvidenceStatus
from leadstream.intelligence.cpf_rfb import validate_cpf_with_details
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
from leadstream.providers.resilience import reserve_shared_rate_limit

RISK_ENDPOINTS: tuple[tuple[str, str, str], ...] = (
    ("CEIS", "ceis", "codigoSancionado"),
    ("CNEP", "cnep", "codigoSancionado"),
    ("CEPIM", "cepim", "cnpjSancionado"),
    ("ACORDO_LENIENCIA", "acordos-leniencia", "cnpjSancionado"),
)
CONTRACT_ENDPOINT = ("CONTRATOS", "contratos/cpf-cnpj", "cpfCnpj")


@dataclass(frozen=True)
class PortalPageResult:
    records: tuple[dict[str, Any], ...]
    pages_checked: int
    truncated: bool
    request_ids: tuple[str, ...]

# Lista publicada no cadastro da API. O limite reduzido é aplicado por requisição real,
# inclusive quando uma rota restrita é acionada pela cascata guiada por perfil.
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

PERSON_PROFESSIONAL_FLAGS = frozenset(
    {
        "favorecidoDespesas",
        "servidor",
        "beneficiarioDiarias",
        "permissionario",
        "contratado",
        "sancionadoCEIS",
        "sancionadoCNEP",
        "sancionadoCEAF",
        "portadorCPDC",
        "portadorCPGF",
        "favorecidoTransferencias",
        "favorecidoCPCC",
        "favorecidoCPDC",
        "favorecidoCPGF",
        "participanteLicitacao",
        "servidorInativo",
    }
)
SENSITIVE_PERSON_MARKERS = (
    "nis",
    "bolsafamilia",
    "peti",
    "safra",
    "segurodefeso",
    "bpc",
    "auxilioemergencial",
    "auxiliobrasil",
    "novobolsafamilia",
    "auxilioreconstrucao",
    "pensao",
    "pensionista",
    "instituidor",
    "remuneracao",
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


def _invoice_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": record.get("id"),
        "recipient_superior_body": record.get("orgaoSuperiorDestinatario"),
        "recipient_body": record.get("orgaoDestinatario"),
        "supplier_name": record.get("nomeFornecedor"),
        "supplier_cnpj": record.get("cnpjFornecedor"),
        "supplier_city": record.get("municipioFornecedor"),
        "invoice_key": record.get("chaveNotaFiscal"),
        "value": record.get("valorNotaFiscal"),
        "issued_on": record.get("dataEmissao"),
        "latest_event": record.get("tipoEventoMaisRecente"),
        "latest_event_on": record.get("dataTipoEventoMaisRecente"),
        "number": record.get("numero"),
        "series": record.get("serie"),
    }


def _minimize_company_payload(value: Any) -> Any:
    """Remove contatos e identificadores de PF de payloads empresariais aninhados."""

    if isinstance(value, list):
        return [_minimize_company_payload(item) for item in value]
    if not isinstance(value, dict):
        return value
    minimized: dict[str, Any] = {}
    for key, item in value.items():
        normalized_key = str(key).casefold()
        if any(
            marker in normalized_key
            for marker in ("cpf", "nis", "email", "telefone", "celular")
        ) and "cnpj" not in normalized_key:
            continue
        minimized[str(key)] = _minimize_company_payload(item)
    return minimized


def _minimize_person_payload(value: Any) -> Any:
    """Mantém sinais profissionais e remove documentos/benefícios/remuneração de PF."""

    if isinstance(value, list):
        return [_minimize_person_payload(item) for item in value]
    if not isinstance(value, dict):
        return value
    minimized: dict[str, Any] = {}
    for key, item in value.items():
        normalized_key = str(key).casefold().replace("_", "")
        if "cpf" in normalized_key or any(
            marker in normalized_key for marker in SENSITIVE_PERSON_MARKERS
        ):
            continue
        minimized[str(key)] = _minimize_person_payload(item)
    return minimized


def _ceaf_record(record: dict[str, Any]) -> dict[str, Any]:
    person = _dict(record.get("pessoa"))
    punishment = _dict(record.get("punicao"))
    punishment_type = _dict(record.get("tipoPunicao"))
    organ = _dict(record.get("orgaoLotacao"))
    state = _dict(record.get("ufLotacaoPessoa"))
    return {
        "source": "CEAF",
        "record_id": record.get("id"),
        "sanctioned_name": person.get("nome") or person.get("razaoSocialReceita"),
        "published_on": record.get("dataPublicacao"),
        "reference_date": record.get("dataReferencia"),
        "reason": punishment.get("descricao") or punishment.get("nome"),
        "sanction_type": punishment_type.get("descricao") or punishment_type.get("nome"),
        "sanctioning_organ": organ.get("nome") or organ.get("descricao"),
        "state": state.get("sigla") or state.get("descricao"),
        "position": record.get("cargoEfetivo") or record.get("cargoComissao"),
        "legal_basis": _minimize_person_payload(record.get("fundamentacao", [])),
    }


class PortalTransparenciaAdapter:
    slug = "portal-transparencia"
    resumable = True

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    def is_configured(self) -> bool:
        return bool(settings.PORTAL_TRANSPARENCIA_TOKEN)

    def quota_for(self, context: ProviderContext) -> ProviderQuota:
        del context
        return ProviderQuota(
            scope="portal-transparencia-api",
            requests_per_minute=portal_requests_per_minute(),
            # O plano é dinâmico e respostas em cache não consomem a quota oficial.
            units=0,
        )

    def _request(
        self,
        *,
        client: httpx.Client,
        endpoint: str,
        params: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], str]:
        cache_key = "portal-transparencia:" + fingerprint_value(
            {"endpoint": endpoint, "params": params}
        )
        cached = cache.get(cache_key)
        if isinstance(cached, dict) and isinstance(cached.get("items"), list):
            return cached["items"], _text(cached.get("request_id"))
        reserve_shared_rate_limit(
            scope="portal-transparencia-api",
            requests_per_minute=portal_requests_per_minute(
                restricted=endpoint in RESTRICTED_ENDPOINTS
            ),
            provider_label="portal-transparencia",
        )
        url = f"{settings.PORTAL_TRANSPARENCIA_BASE_URL.rstrip('/')}/{endpoint}"
        try:
            response = client.get(
                url,
                headers={
                    "chave-api-dados": str(settings.PORTAL_TRANSPARENCIA_TOKEN),
                    "Accept": "application/json",
                    "User-Agent": "LeadStream/1.0",
                },
                params=params,
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

    def _request_pages(
        self,
        *,
        client: httpx.Client,
        endpoint: str,
        params: dict[str, Any],
    ) -> PortalPageResult:
        records: list[dict[str, Any]] = []
        request_ids: list[str] = []
        pages_checked = 0
        max_pages = max(int(settings.PORTAL_TRANSPARENCIA_MAX_PAGES), 1)
        last_page_had_records = False
        seen: set[str] = set()
        for page in range(1, max_pages + 1):
            items, request_id = self._request(
                client=client,
                endpoint=endpoint,
                params={**params, "pagina": page},
            )
            pages_checked += 1
            if request_id:
                request_ids.append(request_id)
            if not items:
                last_page_had_records = False
                break
            last_page_had_records = True
            for item in items:
                digest = fingerprint_value(item)
                if digest not in seen:
                    seen.add(digest)
                    records.append(item)
        return PortalPageResult(
            records=tuple(records),
            pages_checked=pages_checked,
            truncated=last_page_had_records and pages_checked == max_pages,
            request_ids=tuple(dict.fromkeys(request_ids)),
        )

    def _profile(
        self,
        *,
        client: httpx.Client,
        cnpj: str,
    ) -> tuple[dict[str, Any], str]:
        records, request_id = self._request(
            client=client,
            endpoint="pessoa-juridica",
            params={"cnpj": cnpj},
        )
        for record in records:
            document = only_digits(_text(record.get("cnpj")))
            if not document or document == cnpj:
                return record, request_id
        return {}, request_id

    def _person_profile(
        self,
        *,
        client: httpx.Client,
        cpf: str,
    ) -> tuple[dict[str, Any], str]:
        records, request_id = self._request(
            client=client,
            endpoint="pessoa-fisica",
            params={"cpf": cpf},
        )
        return (records[0] if records else {}), request_id

    def enrich_person(self, cpf: str) -> dict[str, Any]:
        """Consulta apenas sinais públicos profissionais de PF, nunca benefícios/remuneração."""

        if not self.is_configured():
            raise ProviderNotConfigured("Portal da Transparência não configurado.")
        digits = only_digits(cpf)
        if not validate_cpf_with_details(digits).get("valido"):
            raise ProviderPermanentError("CPF inválido para consulta governamental.")
        if self._client is not None:
            return self._enrich_person_with_client(cpf=digits, client=self._client)
        with httpx.Client(
            timeout=settings.PORTAL_TRANSPARENCIA_TIMEOUT_SECONDS,
            follow_redirects=True,
        ) as client:
            return self._enrich_person_with_client(cpf=digits, client=client)

    def _enrich_person_with_client(
        self,
        *,
        cpf: str,
        client: httpx.Client,
    ) -> dict[str, Any]:
        request_ids: list[str] = []
        executed_endpoints: list[str] = []
        skipped_endpoints: list[dict[str, str]] = []
        coverage: dict[str, dict[str, Any]] = {}

        def fetch_pages(
            endpoint: str,
            params: dict[str, Any],
            *,
            coverage_key: str | None = None,
        ) -> PortalPageResult:
            result = self._request_pages(client=client, endpoint=endpoint, params=params)
            executed_endpoints.append(endpoint)
            request_ids.extend(result.request_ids)
            coverage[coverage_key or endpoint] = {
                "records": len(result.records),
                "pages_checked": result.pages_checked,
                "truncated": result.truncated,
            }
            return result

        def skip(endpoint: str, reason: str) -> None:
            skipped_endpoints.append({"endpoint": endpoint, "reason": reason})

        profile, profile_request_id = self._person_profile(client=client, cpf=cpf)
        executed_endpoints.append("pessoa-fisica")
        if profile_request_id:
            request_ids.append(profile_request_id)
        coverage["pessoa-fisica"] = {
            "records": 1 if profile else 0,
            "pages_checked": 1,
            "truncated": False,
        }
        professional_flags = {
            key: bool(profile.get(key)) for key in sorted(PERSON_PROFESSIONAL_FLAGS)
        }

        # PEP não possui flag no perfil-resumo; é a única consulta adicional incondicional.
        pep_page = fetch_pages("peps", {"cpf": cpf})
        pep_records = _minimize_person_payload(list(pep_page.records))

        server_records: list[dict[str, Any]] = []
        if professional_flags["servidor"] or professional_flags["servidorInativo"]:
            server_records = _minimize_person_payload(
                list(fetch_pages("servidores", {"cpf": cpf}).records)
            )
        else:
            skip("servidores", "perfil_sem_vinculo_servidor")

        permission_records: list[dict[str, Any]] = []
        if professional_flags["permissionario"]:
            permission_records = _minimize_person_payload(
                list(fetch_pages("permissionarios", {"cpfOcupante": cpf}).records)
            )
        else:
            skip("permissionarios", "perfil_sem_imovel_funcional")

        risk_records: list[dict[str, Any]] = []
        checked_risk_sources: list[str] = []
        for flag, source, endpoint, parameter in (
            ("sancionadoCEIS", "CEIS", "ceis", "codigoSancionado"),
            ("sancionadoCNEP", "CNEP", "cnep", "codigoSancionado"),
            ("sancionadoCEAF", "CEAF", "ceaf", "cpfSancionado"),
        ):
            if professional_flags[flag]:
                page = fetch_pages(endpoint, {parameter: cpf})
                checked_risk_sources.append(source)
                if source == "CEAF":
                    risk_records.extend(_ceaf_record(record) for record in page.records)
                else:
                    risk_records.extend(
                        _sanction_record(record, source) for record in page.records
                    )
            else:
                skip(endpoint, f"perfil_{flag}_falso")

        contracts: list[dict[str, Any]] = []
        if professional_flags["contratado"]:
            contracts = [
                _contract_record(record)
                for record in fetch_pages(
                    "contratos/cpf-cnpj", {"cpfCnpj": cpf}
                ).records
            ]
        else:
            skip("contratos/cpf-cnpj", "perfil_sem_contratacao")

        travel_records: list[dict[str, Any]] = []
        if professional_flags["beneficiarioDiarias"]:
            travel_records = _minimize_person_payload(
                list(fetch_pages("viagens-por-cpf", {"cpf": cpf}).records)
            )
        else:
            skip("viagens-por-cpf", "perfil_sem_diarias")

        card_records: list[dict[str, Any]] = []
        if professional_flags["portadorCPDC"] or professional_flags["portadorCPGF"]:
            card_records.extend(
                _minimize_person_payload(
                    list(fetch_pages("cartoes", {"cpfPortador": cpf}).records)
                )
            )
        else:
            skip("cartoes:portador", "perfil_sem_cartao_como_portador")
        if any(
            professional_flags[key]
            for key in ("favorecidoCPCC", "favorecidoCPDC", "favorecidoCPGF")
        ):
            card_records.extend(
                _minimize_person_payload(
                    list(
                        fetch_pages(
                            "cartoes",
                            {"cpfCnpjFavorecido": cpf},
                            coverage_key="cartoes:favorecido",
                        ).records
                    )
                )
            )
        else:
            skip("cartoes:favorecido", "perfil_sem_cartao_como_favorecido")

        resources_received: list[dict[str, Any]] = []
        expense_documents: list[dict[str, Any]] = []
        has_public_expense = bool(
            professional_flags["favorecidoDespesas"]
            or professional_flags["favorecidoTransferencias"]
        )
        if has_public_expense:
            today = timezone.localdate()
            lookback_years = max(
                min(int(settings.PORTAL_TRANSPARENCIA_EXPENSE_LOOKBACK_YEARS), 10), 1
            )
            for year in range(today.year - lookback_years + 1, today.year + 1):
                end_month = today.month if year == today.year else 12
                resources_received.extend(
                    _minimize_person_payload(
                        list(
                            fetch_pages(
                                "despesas/recursos-recebidos",
                                {
                                    "mesAnoInicio": f"01/{year}",
                                    "mesAnoFim": f"{end_month:02d}/{year}",
                                    "codigoFavorecido": cpf,
                                },
                                coverage_key=f"despesas/recursos-recebidos:{year}",
                            ).records
                        )
                    )
                )
            if professional_flags["favorecidoDespesas"]:
                for year in range(today.year - lookback_years + 1, today.year + 1):
                    for phase in (1, 2, 3):
                        expense_documents.extend(
                            _minimize_person_payload(
                                list(
                                    fetch_pages(
                                        "despesas/documentos-por-favorecido",
                                        {"codigoPessoa": cpf, "fase": phase, "ano": year},
                                        coverage_key=(
                                            "despesas/documentos-por-favorecido:"
                                            f"{year}:fase-{phase}"
                                        ),
                                    ).records
                                )
                            )
                        )
        else:
            skip("despesas/recursos-recebidos", "perfil_sem_recursos_publicos")
            skip("despesas/documentos-por-favorecido", "perfil_sem_despesas")

        return {
            "indexed_in_portal": bool(profile),
            "profile": {
                "name": _text(profile.get("nome")),
                "professional_flags": professional_flags,
            },
            "pep": {
                "has_matches": bool(pep_records),
                "match_count": len(pep_records),
                "records": pep_records,
            },
            "government_risk": {
                "status": (
                    "MATCH_FOUND"
                    if risk_records
                    else (
                        "NO_MATCH_ON_CHECKED_SOURCES"
                        if checked_risk_sources
                        else "NOT_QUERIED_NO_PROFILE_FLAG"
                    )
                ),
                "has_matches": bool(risk_records),
                "match_count": len(risk_records),
                "checked_sources": checked_risk_sources,
                "records": risk_records,
            },
            "public_sector": {
                "server_records": server_records,
                "permission_records": permission_records,
                "contracts": contracts,
                "travel_records": travel_records,
                "card_records": card_records,
                "resources_received": resources_received,
                "expense_documents": expense_documents,
                "unresolved_signals": {
                    "procurement_participant": professional_flags["participanteLicitacao"]
                },
            },
            "coverage": coverage,
            "executed_endpoints": list(dict.fromkeys(executed_endpoints)),
            "skipped_endpoints": skipped_endpoints,
            "strategy": "PROFILE_GUIDED_PROFESSIONAL_ONLY",
            "sensitive_sources_excluded": [
                "beneficios_sociais",
                "remuneracao",
                "pensoes",
            ],
            "external_request_id": ",".join(dict.fromkeys(request_ids))[:255],
            "observed_at": timezone.now().isoformat(),
        }

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

        profile: dict[str, Any] = {}
        executed_endpoints: list[str] = []
        skipped_endpoints: list[dict[str, str]] = []
        coverage: dict[str, dict[str, Any]] = {}
        if DataBlock.PUBLIC_SECTOR in context.missing_blocks:
            profile, profile_request_id = self._profile(client=client, cnpj=cnpj)
            if profile_request_id:
                request_ids.append(profile_request_id)
            executed_endpoints.append("pessoa-juridica")
            coverage["pessoa-juridica"] = {
                "records": 1 if profile else 0,
                "pages_checked": 1,
                "truncated": False,
            }

        def fetch_pages(
            endpoint: str,
            params: dict[str, Any],
            *,
            coverage_key: str | None = None,
        ) -> PortalPageResult:
            result = self._request_pages(client=client, endpoint=endpoint, params=params)
            executed_endpoints.append(endpoint)
            request_ids.extend(result.request_ids)
            coverage[coverage_key or endpoint] = {
                "records": len(result.records),
                "pages_checked": result.pages_checked,
                "truncated": result.truncated,
            }
            return result

        def fetch_once(
            endpoint: str,
            params: dict[str, Any],
            *,
            coverage_key: str | None = None,
        ) -> list[dict[str, Any]]:
            records, request_id = self._request(
                client=client,
                endpoint=endpoint,
                params=params,
            )
            executed_endpoints.append(endpoint)
            if request_id:
                request_ids.append(request_id)
            coverage[coverage_key or endpoint] = {
                "records": len(records),
                "pages_checked": 1,
                "truncated": False,
            }
            return records

        def skip(endpoint: str, reason: str) -> None:
            skipped_endpoints.append({"endpoint": endpoint, "reason": reason})

        if DataBlock.GOVERNMENT_RISK in context.missing_blocks:
            risk_records: list[dict[str, Any]] = []
            checked_sources: list[str] = []
            risk_pagination: dict[str, dict[str, Any]] = {}
            for source, endpoint, parameter in RISK_ENDPOINTS:
                page = fetch_pages(endpoint, {parameter: cnpj})
                checked_sources.append(source)
                risk_pagination[source] = coverage[endpoint]
                risk_records.extend(
                    _sanction_record(record, source)
                    for record in page.records
                    if _document_matches(record, cnpj, source)
                )
            risk = {
                "status": "MATCH_FOUND" if risk_records else "NO_MATCH_ON_CHECKED_SOURCES",
                "has_matches": bool(risk_records),
                "match_count": len(risk_records),
                "checked_sources": checked_sources,
                "records": risk_records,
                "pagination": risk_pagination,
                "profile_indexed": bool(profile),
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
            contracts: list[dict[str, Any]] = []
            invoices: list[dict[str, Any]] = []
            tax_waivers: dict[str, list[dict[str, Any]]] = {
                "values": [],
                "immune_or_exempt": [],
                "enabled_benefits": [],
            }
            resources_received: list[dict[str, Any]] = []
            expense_documents: list[dict[str, Any]] = []
            card_transactions: list[dict[str, Any]] = []

            if profile.get("possuiContratacao"):
                source, endpoint, parameter = CONTRACT_ENDPOINT
                page = fetch_pages(endpoint, {parameter: cnpj})
                raw_contracts = [
                    record
                    for record in page.records
                    if _document_matches(record, cnpj, source)
                ]
                detail_limit = max(int(settings.PORTAL_TRANSPARENCIA_MAX_DETAIL_RECORDS), 0)
                for index, record in enumerate(raw_contracts):
                    contract = _contract_record(record)
                    record_id = record.get("id")
                    if record_id is not None and index < detail_limit:
                        details: dict[str, Any] = {}
                        details["amendments"] = _minimize_company_payload(
                            fetch_once(
                                "contratos/termo-aditivo",
                                {"id": record_id},
                                coverage_key=f"contratos/termo-aditivo:{record_id}",
                            )
                        )
                        details["items"] = _minimize_company_payload(
                            list(
                                fetch_pages(
                                    "contratos/itens-contratados",
                                    {"id": record_id},
                                    coverage_key=f"contratos/itens-contratados:{record_id}",
                                ).records
                            )
                        )
                        details["documents"] = _minimize_company_payload(
                            fetch_once(
                                "contratos/documentos-relacionados",
                                {"id": record_id},
                                coverage_key=f"contratos/documentos-relacionados:{record_id}",
                            )
                        )
                        details["price_adjustments"] = _minimize_company_payload(
                            fetch_once(
                                "contratos/apostilamento",
                                {"id": record_id},
                                coverage_key=f"contratos/apostilamento:{record_id}",
                            )
                        )
                        contract["details"] = details
                    contracts.append(contract)
            else:
                skip("contratos/cpf-cnpj", "perfil_sem_contratacao")

            if profile.get("emitiuNFe"):
                page = fetch_pages("notas-fiscais", {"cnpjEmitente": cnpj})
                detail_limit = max(int(settings.PORTAL_TRANSPARENCIA_MAX_DETAIL_RECORDS), 0)
                for index, record in enumerate(page.records):
                    invoice = _invoice_record(record)
                    invoice_key = _text(record.get("chaveNotaFiscal"))
                    if invoice_key and index < detail_limit:
                        invoice["details"] = _minimize_company_payload(
                            fetch_once(
                                "notas-fiscais-por-chave",
                                {"chaveUnicaNotaFiscal": invoice_key},
                                coverage_key=f"notas-fiscais-por-chave:{index + 1}",
                            )
                        )
                    invoices.append(invoice)
            else:
                skip("notas-fiscais", "perfil_sem_nfe")

            tax_routes = (
                (
                    "beneficiadoRenunciaFiscal",
                    "renuncias-valor",
                    "values",
                ),
                (
                    "isentoImuneRenunciaFiscal",
                    "renuncias-fiscais-empresas-imunes-isentas",
                    "immune_or_exempt",
                ),
                (
                    "habilitadoRenunciaFiscal",
                    "renuncias-fiscais-empresas-habilitadas-beneficios-fiscais",
                    "enabled_benefits",
                ),
            )
            for flag, endpoint, result_key in tax_routes:
                if profile.get(flag):
                    page = fetch_pages(endpoint, {"cnpj": cnpj})
                    tax_waivers[result_key] = _minimize_company_payload(list(page.records))
                else:
                    skip(endpoint, f"perfil_{flag}_falso")

            has_public_expense = bool(
                profile.get("favorecidoDespesas") or profile.get("favorecidoTransferencias")
            )
            if has_public_expense:
                today = timezone.localdate()
                lookback_years = max(
                    min(int(settings.PORTAL_TRANSPARENCIA_EXPENSE_LOOKBACK_YEARS), 10), 1
                )
                for year in range(today.year - lookback_years + 1, today.year + 1):
                    end_month = today.month if year == today.year else 12
                    page = fetch_pages(
                        "despesas/recursos-recebidos",
                        {
                            "mesAnoInicio": f"01/{year}",
                            "mesAnoFim": f"{end_month:02d}/{year}",
                            "codigoFavorecido": cnpj,
                        },
                        coverage_key=f"despesas/recursos-recebidos:{year}",
                    )
                    resources_received.extend(
                        _minimize_company_payload(list(page.records))
                    )

                if profile.get("favorecidoDespesas"):
                    for year in range(today.year - lookback_years + 1, today.year + 1):
                        for phase in (1, 2, 3):
                            page = fetch_pages(
                                "despesas/documentos-por-favorecido",
                                {"codigoPessoa": cnpj, "fase": phase, "ano": year},
                                coverage_key=(
                                    f"despesas/documentos-por-favorecido:{year}:fase-{phase}"
                                ),
                            )
                            expense_documents.extend(
                                _minimize_company_payload(list(page.records))
                            )
                    card_page = fetch_pages("cartoes", {"cpfCnpjFavorecido": cnpj})
                    card_transactions = _minimize_company_payload(list(card_page.records))
            else:
                skip("despesas/recursos-recebidos", "perfil_sem_recursos_publicos")
                skip("despesas/documentos-por-favorecido", "perfil_sem_despesas")
                skip("cartoes", "perfil_sem_despesas")

            profile_flags = {
                key: value
                for key, value in profile.items()
                if isinstance(value, bool)
            }
            public_sector = {
                "indexed_in_portal": bool(profile),
                "profile": {
                    "legal_name": profile.get("razaoSocial"),
                    "trade_name": profile.get("nomeFantasia"),
                    "flags": profile_flags,
                },
                "has_federal_contracts": bool(contracts),
                "contract_count": len(contracts),
                "contracts": contracts,
                "invoice_count": len(invoices),
                "invoices": invoices,
                "tax_waivers": tax_waivers,
                "resources_received_count": len(resources_received),
                "resources_received": resources_received,
                "expense_document_count": len(expense_documents),
                "expense_documents": expense_documents,
                "card_transaction_count": len(card_transactions),
                "card_transactions": card_transactions,
                "unresolved_signals": {
                    "agreements": bool(profile.get("convenios")),
                    "procurement_participant": bool(profile.get("participanteLicitacao")),
                },
                "coverage": coverage,
                "executed_endpoints": list(dict.fromkeys(executed_endpoints)),
                "skipped_endpoints": skipped_endpoints,
                "strategy": "PROFILE_GUIDED_WITH_BOUNDED_DETAILS",
            }
            payload_for_hash["public_sector"] = public_sector
            observations.append(
                FieldObservation(
                    field_path="company.public_sector_profile",
                    value=public_sector,
                    confidence=100,
                    evidence_status=EvidenceStatus.TECHNICALLY_VALIDATED,
                    method=CaptureMethod.API,
                    source_url=f"{base_url}/pessoa-juridica",
                    external_id=f"public-sector:{cnpj}",
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
