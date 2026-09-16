from __future__ import annotations

import logging
import unicodedata
import uuid
from typing import Any

import httpx
from django.db import transaction
from django.utils import timezone

from leadstream.batches.models import Batch, BatchItem
from leadstream.billing.models import BillableEvent, DataBlock
from leadstream.common.redaction import correlation_tag
from leadstream.entities.models import Company, ContactPoint, Relationship
from leadstream.entities.normalization import (
    DataValidationError,
    cnpj_root,
    normalize_cnpj,
    only_digits,
)
from leadstream.entities.projections import update_company_registry_projection
from leadstream.entities.services import (
    create_company,
    create_contact_point,
    create_person,
    create_relationship,
)
from leadstream.tenancy.models import Tenant

from .orchestrator import CascadeResult, run_enrichment_cascade

logger = logging.getLogger(__name__)


def normalize_external_qualification(value: str) -> str:
    normalized = value.strip().casefold()
    if "administrador" in normalized or "diretor" in normalized or "presidente" in normalized:
        return Relationship.Qualification.ADMINISTRATOR
    if "representante" in normalized or "procurador" in normalized:
        return Relationship.Qualification.LEGAL_REPRESENTATIVE
    if "sócio" in normalized or "socio" in normalized or "titular" in normalized:
        return Relationship.Qualification.PARTNER
    return Relationship.Qualification.OTHER


def calculate_expected_dv(base12: str) -> str:
    """Calcula os dígitos verificadores (Módulo 11) para uma base de 12 dígitos de CNPJ."""
    w1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
    w2 = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
    r1 = sum(int(n) * w for n, w in zip(base12, w1, strict=True)) % 11
    d1 = "0" if r1 < 2 else str(11 - r1)
    r2 = sum(int(n) * w for n, w in zip(base12 + d1, w2, strict=True)) % 11
    d2 = "0" if r2 < 2 else str(11 - r2)
    return d1 + d2


def format_cnpj(digits: str) -> str:
    """Formata 14 dígitos no padrão XX.XXX.XXX/XXXX-XX."""
    if len(digits) != 14:
        return digits
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"


def format_currency_brl(value: float | int | None) -> str:
    """Formata valor monetário em Reais (BRL)."""
    if value is None:
        return "Não informado"
    try:
        val = float(value)
        formatted = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {formatted}"
    except (ValueError, TypeError):
        return "Não informado"


def format_phone_br(digits: str) -> str:
    """Formata telefone brasileiro (DDD + número)."""
    d = only_digits(digits)
    if d.startswith("55") and len(d) > 10:
        d = d[2:]
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return digits


def optional_bool(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().casefold()
    if normalized in {"1", "true", "sim", "s", "yes"}:
        return True
    if normalized in {"0", "false", "não", "nao", "n", "no"}:
        return False
    return None


def display_bool(value: bool | None, *, yes: str, no: str) -> str:
    if value is None:
        return "Não informado"
    return yes if value else no


CAPABILITY_BLOCKS: dict[str, frozenset[str]] = {
    "cnpj_qsa": frozenset(
        {DataBlock.COMPANY_REGISTRY, DataBlock.DECISION_MAKER, DataBlock.SOCIAL_PROFILES}
    ),
    "emails_smtp": frozenset({DataBlock.DIRECT_EMAIL}),
    "phones_whatsapp": frozenset({DataBlock.DIRECT_PHONE, DataBlock.WHATSAPP}),
    "social_profiles": frozenset({DataBlock.SOCIAL_PROFILES}),
}


def _requested_blocks(capabilities: list[str]) -> frozenset[str]:
    blocks: set[str] = set()
    for capability in capabilities:
        blocks.update(CAPABILITY_BLOCKS.get(capability, ()))
    return frozenset(blocks or {DataBlock.COMPANY_REGISTRY, DataBlock.DECISION_MAKER})


def _individual_enrichment_context(
    *,
    execution_key: str,
    tenant: Tenant,
    company: Company,
    cnpj: str,
    normalized_data: dict[str, Any],
) -> tuple[Batch, BatchItem]:
    """Cria um contexto durável e idempotente para a cascata da consulta individual."""
    idempotency_key = f"individual:{execution_key}"[:128]
    batch, _ = Batch.objects.get_or_create(
        tenant=tenant,
        idempotency_key=idempotency_key,
        defaults={
            "name": f"Consulta individual · {format_cnpj(cnpj)}",
            "source_type": Batch.SourceType.DISCOVERY,
            "status": Batch.Status.RUNNING,
            "current_stage": "ENRICHMENT",
            "chunk_size": 50,
            "total_rows": 1,
            "processed_rows": 1,
            "succeeded_rows": 1,
            "started_at": timezone.now(),
        },
    )
    item, _ = BatchItem.objects.get_or_create(
        tenant=tenant,
        batch=batch,
        row_number=1,
        defaults={
            "original_data": {"cnpj": cnpj},
            "normalized_data": normalized_data,
            "hygiene_state": BatchItem.HygieneState.UNCHANGED,
            "status": BatchItem.Status.SUCCEEDED,
            "entity": company.entity,
            "processed_at": timezone.now(),
        },
    )
    changed: list[str] = []
    if item.entity_id != company.entity_id:
        item.entity = company.entity
        changed.append("entity")
    if item.normalized_data != normalized_data:
        item.normalized_data = normalized_data
        changed.append("normalized_data")
    if changed:
        item.save(update_fields=(*changed, "updated_at"))
    return batch, item


def _run_individual_cascade(
    *,
    execution_key: str,
    tenant: Tenant,
    company: Company,
    cnpj: str,
    capabilities: list[str],
    normalized_data: dict[str, Any],
) -> CascadeResult:
    batch, item = _individual_enrichment_context(
        execution_key=execution_key,
        tenant=tenant,
        company=company,
        cnpj=cnpj,
        normalized_data=normalized_data,
    )
    result = run_enrichment_cascade(
        tenant=tenant,
        batch=batch,
        item=item,
        requested_blocks=_requested_blocks(capabilities),
    )
    item.delivered_blocks = sorted(result.delivered_blocks)
    item.missing_blocks = sorted(result.missing_blocks)
    item.enrichment_errors = list(result.errors)
    item.enrichment_status = (
        BatchItem.EnrichmentStatus.SUCCEEDED
        if not result.missing_blocks
        else BatchItem.EnrichmentStatus.PARTIAL
        if result.delivered_blocks
        else BatchItem.EnrichmentStatus.FAILED
    )
    item.save(
        update_fields=(
            "delivered_blocks",
            "missing_blocks",
            "enrichment_errors",
            "enrichment_status",
            "updated_at",
        )
    )
    batch.status = Batch.Status.COMPLETED if result.delivered_blocks else Batch.Status.PARTIAL
    batch.current_stage = "ENRICHMENT"
    batch.completed_at = timezone.now()
    batch.save(update_fields=("status", "current_stage", "completed_at", "updated_at"))
    return result


def _normalized_person_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return " ".join(
        "".join(char for char in decomposed if not unicodedata.combining(char))
        .casefold()
        .split()
    )


def _decision_maker_dossier(company: Company) -> list[dict[str, Any]]:
    """Consolida pessoas duplicadas por nome para apresentação, sem inventar atribuição."""
    dossiers: dict[str, dict[str, Any]] = {}
    relationships = company.relationships.select_related("person", "person__entity").all()
    for relationship in relationships:
        person = relationship.person
        key = _normalized_person_name(person.full_name)
        dossier = dossiers.setdefault(
            key,
            {
                "name": person.full_name,
                "roles": set(),
                "seniorities": set(),
                "emails": set(),
                "phones": set(),
                "whatsapps": set(),
                "socials": {},
            },
        )
        role = relationship.observed_title or relationship.get_qualification_display()
        if role:
            dossier["roles"].add(role)
        if relationship.seniority != Relationship.Seniority.UNKNOWN:
            dossier["seniorities"].add(relationship.get_seniority_display())
        for contact in person.entity.contact_points.all():
            if contact.kind == ContactPoint.Kind.EMAIL:
                dossier["emails"].add(contact.original_value)
            elif contact.kind == ContactPoint.Kind.WHATSAPP:
                dossier["whatsapps"].add(format_phone_br(contact.original_value))
            elif contact.kind == ContactPoint.Kind.PHONE:
                dossier["phones"].add(format_phone_br(contact.original_value))
        for social in person.entity.social_profiles.all():
            dossier["socials"].setdefault(social.get_network_display(), set()).add(
                social.profile_url
            )
    result: list[dict[str, Any]] = []
    for dossier in dossiers.values():
        result.append(
            {
                "nome": dossier["name"],
                "funcoes": sorted(dossier["roles"]),
                "senioridades": sorted(dossier["seniorities"]),
                "emails": sorted(dossier["emails"]),
                "telefones": sorted(dossier["phones"]),
                "whatsapps": sorted(dossier["whatsapps"]),
                "redesSociais": {
                    network: sorted(urls) for network, urls in dossier["socials"].items()
                },
            }
        )
    return sorted(result, key=lambda item: item["nome"])


def fetch_official_rfb_data(cnpj_digits: str) -> dict[str, Any] | None:
    """Consulta espelhos públicos do cadastro empresarial via BrasilAPI/Minha Receita."""
    # 1. Tentar BrasilAPI
    try:
        url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_digits}"
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                data: dict[str, Any] = resp.json()
                if isinstance(data, dict) and data.get("razao_social"):
                    return {**data, "_leadstream_source": "BrasilAPI"}
            elif resp.status_code == 404:
                return None
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Falha na consulta BrasilAPI para CNPJ %s: %s",
            correlation_tag(cnpj_digits),
            type(exc).__name__,
        )

    # 2. Fallback MinhaReceita
    try:
        url = f"https://minhareceita.org/{cnpj_digits}"
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and data.get("razao_social"):
                    return {**data, "_leadstream_source": "Minha Receita"}
            elif resp.status_code == 404:
                return None
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Falha na consulta Minha Receita para CNPJ %s: %s",
            correlation_tag(cnpj_digits),
            type(exc).__name__,
        )

    return None


def _stored_company_projection(company: Company, cnpj: str) -> dict[str, Any]:
    establishment = company.establishments.filter(cnpj=cnpj).first()
    if establishment is None:
        establishment = company.establishments.order_by("-is_headquarters", "created_at").first()
    data: dict[str, Any] = {
        "razao_social": company.legal_name,
        "nome_fantasia": company.trade_name,
        "descricao_situacao_cadastral": company.registration_status,
        "data_inicio_atividade": company.opened_on,
        "natureza_juridica": company.legal_nature,
        "porte": company.company_size,
        "capital_social": company.share_capital,
        "cnae_fiscal": company.primary_cnae,
        "cnae_fiscal_descricao": company.primary_cnae_description,
        "cnaes_secundarios": company.secondary_cnaes,
        "opcao_pelo_simples": company.simple_national,
        "opcao_pelo_mei": company.mei,
        "_leadstream_source": company.registry_source or "Base operacional",
        "_leadstream_cached": True,
        "_leadstream_observed_at": company.registry_observed_at,
    }
    if establishment is not None:
        data.update(
            {
                "descricao_identificador_matriz_filial": (
                    "MATRIZ" if establishment.is_headquarters else "FILIAL"
                ),
                "descricao_tipo_de_logradouro": establishment.street_type,
                "logradouro": establishment.street,
                "numero": establishment.number,
                "complemento": establishment.complement,
                "bairro": establishment.district,
                "municipio": establishment.city,
                "uf": establishment.state,
                "cep": establishment.postal_code,
                "codigo_municipio_ibge": establishment.municipality_ibge_code,
            }
        )
    return data


def enrich_company_live(
    query: str,
    tenant: Tenant,
    capabilities: list[str] | None = None,
    execution_key: str | None = None,
) -> dict[str, Any]:
    """Executa o pipeline real de enriquecimento cadastral de empresa brasileira.

    Valida CNPJ, consulta bases oficiais públicas e provedores, persiste as entidades no
    banco de dados do tenant e retorna o dossiê completo canônico.
    """
    applied_caps = capabilities or ["cnpj_qsa", "emails_smtp", "phones_whatsapp"]
    run_id = f"run_{uuid.uuid4().hex[:10]}"
    cleaned_digits = only_digits(query)

    # --- 1. Validação de formato e dígitos verificadores ---
    if len(cleaned_digits) != 14:
        err_msg = (
            f"O termo informado possui {len(cleaned_digits)} dígitos numéricos. "
            "Para consulta na Receita Federal é necessário informar os 14 dígitos do CNPJ."
        )
        return {
            "runId": run_id,
            "companyId": "",
            "capabilities": applied_caps,
            "company": None,
            "coverage": {
                "requested": len(applied_caps),
                "available": 0,
                "fieldCount": 0,
                "recordCount": 0,
            },
            "sections": [
                {
                    "id": "validation_error",
                    "title": "Validação Cadastral",
                    "description": "Verificação de conformidade do documento informado",
                    "status": "unavailable",
                    "summary": "Documento não atende aos requisitos de tamanho do CNPJ.",
                    "errorMessage": err_msg,
                    "fields": [
                        {"label": "Entrada Informada", "value": query},
                        {
                            "label": "Dígitos Identificados",
                            "value": f"{len(cleaned_digits)} de 14 dígitos",
                        },
                    ],
                    "items": [],
                }
            ],
            "socioAdministradores": [],
            "emailsValidados": [],
            "telefonesAtribuiveis": [],
            "capabilitiesApplied": applied_caps,
            "costCredits": 0,
        }

    try:
        normalized_cnpj = normalize_cnpj(cleaned_digits)
    except DataValidationError:
        expected_dv = calculate_expected_dv(cleaned_digits[:12])
        formatted_input = format_cnpj(cleaned_digits)
        suggested_cnpj = f"{cleaned_digits[:12]}{expected_dv}"
        formatted_suggested = format_cnpj(suggested_cnpj)
        err_msg = (
            f"O CNPJ {formatted_input} possui dígitos verificadores incorretos "
            f"(esperado '{expected_dv}', recebido '{cleaned_digits[12:]}'). "
            f"Sugestão corrigida com a mesma base: {formatted_suggested}."
        )
        return {
            "runId": run_id,
            "companyId": "",
            "capabilities": applied_caps,
            "company": None,
            "coverage": {
                "requested": len(applied_caps),
                "available": 0,
                "fieldCount": 0,
                "recordCount": 0,
            },
            "sections": [
                {
                    "id": "validation_error",
                    "title": "Validação de Dígitos Verificadores",
                    "description": "Algoritmo oficial Módulo 11 da Receita Federal do Brasil",
                    "status": "unavailable",
                    "summary": "Dígitos verificadores incorretos.",
                    "errorMessage": err_msg,
                    "fields": [
                        {"label": "CNPJ Informado", "value": formatted_input},
                        {"label": "Dígitos Verificadores Recebidos", "value": cleaned_digits[12:]},
                        {"label": "Dígitos Verificadores Esperados", "value": expected_dv},
                        {"label": "Sugestão Corrigida", "value": formatted_suggested},
                    ],
                    "items": [],
                }
            ],
            "socioAdministradores": [],
            "emailsValidados": [],
            "telefonesAtribuiveis": [],
            "capabilitiesApplied": applied_caps,
            "costCredits": 0,
        }

    formatted_cnpj_str = format_cnpj(normalized_cnpj)

    # --- 2. Consulta à base da Receita Federal ---
    rfb_data = fetch_official_rfb_data(normalized_cnpj)
    if not rfb_data:
        root = cnpj_root(normalized_cnpj)
        existing_comp = (
            Company.objects.filter(entity__tenant=tenant, cnpj_root=root)
            .prefetch_related("establishments")
            .first()
        )
        if not existing_comp:
            return {
                "runId": run_id,
                "companyId": "",
                "capabilities": applied_caps,
                "company": None,
                "coverage": {
                    "requested": len(applied_caps),
                    "available": 0,
                    "fieldCount": 0,
                    "recordCount": 0,
                },
                "sections": [
                    {
                        "id": "not_found",
                        "title": "Cadastro empresarial público",
                        "description": "Fontes públicas configuradas para consulta cadastral",
                        "status": "unavailable",
                        "summary": "CNPJ não localizado nas fontes públicas configuradas.",
                        "errorMessage": (
                            f"O CNPJ {formatted_cnpj_str} não foi localizado. "
                            "A fonte também pode estar temporariamente indisponível."
                        ),
                        "fields": [{"label": "CNPJ Consultado", "value": formatted_cnpj_str}],
                        "items": [],
                    }
                ],
                "socioAdministradores": [],
                "emailsValidados": [],
                "telefonesAtribuiveis": [],
                "capabilitiesApplied": applied_caps,
                "costCredits": 0,
            }
        rfb_data = _stored_company_projection(existing_comp, normalized_cnpj)

    # --- 3. Extração dos dados oficiais reais ---
    source_name = str(rfb_data.get("_leadstream_source") or "Fonte pública configurada")
    source_observed_at = rfb_data.get("_leadstream_observed_at") or timezone.now()
    razao_social = str(rfb_data.get("razao_social") or "").strip()
    nome_fantasia = str(rfb_data.get("nome_fantasia") or "").strip()
    situacao = str(rfb_data.get("descricao_situacao_cadastral") or "").strip()
    data_abertura = str(rfb_data.get("data_inicio_atividade") or "").strip()
    natureza_juridica = str(rfb_data.get("natureza_juridica") or "").strip()
    porte = str(rfb_data.get("porte") or "").strip()
    raw_capital_social = rfb_data.get("capital_social")
    try:
        capital_social_val = (
            float(str(raw_capital_social)) if raw_capital_social not in (None, "") else None
        )
    except (TypeError, ValueError):
        capital_social_val = None
    cnae_principal_cod = str(rfb_data.get("cnae_fiscal") or "").strip()
    cnae_principal_desc = (
        str(rfb_data.get("cnae_fiscal_descricao") or "").strip()
    )
    matriz_filial = str(rfb_data.get("descricao_identificador_matriz_filial") or "").strip()

    # Endereço
    tipo_logradouro = (
        str(rfb_data.get("descricao_tipo_de_logradouro") or "").strip()
    )
    logradouro_nome = str(rfb_data.get("logradouro") or "").strip()
    logradouro_completo = f"{tipo_logradouro} {logradouro_nome}".strip()
    numero_end = str(rfb_data.get("numero") or "").strip()
    complemento_end = str(rfb_data.get("complemento") or "").strip()
    bairro_end = str(rfb_data.get("bairro") or "").strip()
    municipio_end = str(rfb_data.get("municipio") or "").strip()
    uf_end = str(rfb_data.get("uf") or "").strip()
    cep_end = str(rfb_data.get("cep") or "").strip()
    cep_formatado = f"{cep_end[:5]}-{cep_end[5:]}" if len(cep_end) == 8 else cep_end

    # Tributação
    simples_nacional = optional_bool(rfb_data.get("opcao_pelo_simples"))
    mei_enquadrado = optional_bool(rfb_data.get("opcao_pelo_mei"))
    data_opcao_simples = str(rfb_data.get("data_opcao_pelo_simples") or "")
    data_opcao_mei = str(rfb_data.get("data_opcao_pelo_mei") or "")

    # Quadro de Sócios e Administradores (QSA) Real
    raw_qsa: list[dict[str, Any]] = rfb_data.get("qsa", [])
    qsa_socios: list[dict[str, Any]] = []
    for s in raw_qsa:
        nome_socio = str(s.get("nome_socio") or "").strip()
        if nome_socio:
            qsa_socios.append(
                {
                    "nome": nome_socio,
                    "qualificacao": str(s.get("qualificacao_socio") or "").strip(),
                    "faixaEtaria": str(s.get("faixa_etaria") or "Não informada").strip(),
                    "documentoMascarado": str(s.get("cnpj_cpf_do_socio") or "").strip(),
                    "dataEntrada": str(s.get("data_entrada_sociedade") or "").strip(),
                }
            )

    # CNAEs secundários reais
    raw_sec: list[dict[str, Any]] = rfb_data.get("cnaes_secundarios", [])
    cnaes_secundarios: list[dict[str, str]] = []
    for c in raw_sec:
        c_code = str(c.get("codigo") or "").strip()
        c_desc = str(c.get("descricao") or "").strip()
        if c_code:
            cnaes_secundarios.append({"codigo": c_code, "descricao": c_desc})

    # Contatos Oficiais declarados na RFB (NUNCA inventar dados!)
    telefones_oficiais: list[str] = []
    t1 = str(rfb_data.get("ddd_telefone_1") or "").strip()
    t2 = str(rfb_data.get("ddd_telefone_2") or "").strip()
    if t1 and len(only_digits(t1)) >= 8:
        telefones_oficiais.append(format_phone_br(t1))
    if t2 and len(only_digits(t2)) >= 8 and t2 != t1:
        telefones_oficiais.append(format_phone_br(t2))

    emails_oficiais: list[str] = []
    email_rfb = str(rfb_data.get("email") or "").strip()
    if email_rfb and "@" in email_rfb:
        emails_oficiais.append(email_rfb.lower())

    # --- 4. Persistência atômica no PostgreSQL do tenant ---
    with transaction.atomic():
        comp_identity = create_company(
            tenant=tenant,
            cnpj=normalized_cnpj,
            legal_name=razao_social or f"Empresa {formatted_cnpj_str}",
            trade_name=nome_fantasia,
            registration_status=situacao,
            is_headquarters=(
                True
                if matriz_filial.upper() == "MATRIZ"
                else False
                if matriz_filial.upper() == "FILIAL"
                else None
            ),
        )
        company_record = comp_identity.company
        if not rfb_data.get("_leadstream_cached"):
            update_company_registry_projection(
                company=company_record,
                data={
                    "legal_name": razao_social,
                    "trade_name": nome_fantasia,
                    "registration_status": situacao,
                    "opened_on": data_abertura,
                    "legal_nature": natureza_juridica,
                    "company_size": porte,
                    "share_capital": raw_capital_social,
                    "primary_cnae": cnae_principal_cod,
                    "primary_cnae_description": cnae_principal_desc,
                    "secondary_cnaes": cnaes_secundarios,
                    "simple_national": rfb_data.get("opcao_pelo_simples"),
                    "mei": rfb_data.get("opcao_pelo_mei"),
                    "street_type": tipo_logradouro,
                    "street": logradouro_nome,
                    "number": numero_end,
                    "complement": complemento_end,
                    "district": bairro_end,
                    "city": municipio_end,
                    "state": uf_end,
                    "postal_code": cep_end,
                    "municipality_ibge_code": rfb_data.get("codigo_municipio_ibge"),
                },
                source=source_name,
                observed_at=source_observed_at,
            )

        # Persistir sócios no grafo de entidades
        for socio in qsa_socios:
            try:
                person = create_person(
                    tenant=tenant,
                    full_name=socio["nome"],
                    external_key=(
                        f"registry:{normalized_cnpj}:"
                        f"{_normalized_person_name(socio['nome'])}"
                    ),
                )
                create_relationship(
                    tenant=tenant,
                    person=person,
                    company=company_record,
                    qualification=normalize_external_qualification(socio["qualificacao"]),
                    observed_title=socio["qualificacao"],
                )
            except (KeyError, ValueError, TypeError) as exc:
                logger.debug("Falha menor ao persistir sócio %s: %s", socio["nome"], exc)

        # Persistir contatos oficiais se existirem
        for em in emails_oficiais:
            try:
                create_contact_point(
                    tenant=tenant,
                    owner=company_record.entity,
                    kind=ContactPoint.Kind.EMAIL,
                    value=em,
                    status=ContactPoint.Status.OBSERVED,
                )
            except (ValueError, TypeError):
                pass

        for tel in telefones_oficiais:
            try:
                create_contact_point(
                    tenant=tenant,
                    owner=company_record.entity,
                    kind=ContactPoint.Kind.PHONE,
                    value=tel,
                    status=ContactPoint.Status.OBSERVED,
                )
            except (ValueError, TypeError):
                pass

    cascade_result: CascadeResult | None = None
    if execution_key:
        cascade_result = _run_individual_cascade(
            execution_key=execution_key,
            tenant=tenant,
            company=company_record,
            cnpj=normalized_cnpj,
            capabilities=applied_caps,
            normalized_data={
                "cnpj": normalized_cnpj,
                "legal_name": razao_social,
                "trade_name": nome_fantasia,
                "municipio": municipio_end,
                "qsa": raw_qsa,
            },
        )
        company_record.refresh_from_db()
        company_contacts = company_record.entity.contact_points.all()
        emails_oficiais = sorted(
            {
                contact.original_value.lower()
                for contact in company_contacts
                if contact.kind == ContactPoint.Kind.EMAIL
            }
        )
        telefones_oficiais = sorted(
            {
                format_phone_br(contact.original_value)
                for contact in company_contacts
                if contact.kind in {ContactPoint.Kind.PHONE, ContactPoint.Kind.WHATSAPP}
            }
        )

    decision_makers = _decision_maker_dossier(company_record)

    # --- 5. Construção das seções canônicas de exibição ---
    sections: list[dict[str, Any]] = []

    # 5.1 Seção Cadastral
    sections.append(
        {
            "id": "registry",
            "title": "Dados cadastrais",
            "description": f"Dados observados em {source_name}",
            "status": "available" if razao_social else "empty",
            "summary": (
                f"Situação cadastral: {situacao or 'não informada'}. "
                f"Unidade: {matriz_filial or 'não informada'}."
            ),
            "fields": [
                {"label": "CNPJ", "value": formatted_cnpj_str},
                {"label": "Razão Social", "value": razao_social or "Não informada"},
                {"label": "Nome Fantasia", "value": nome_fantasia or "Não informado"},
                {"label": "Situação Cadastral", "value": situacao or "Não informada"},
                {"label": "Data de Abertura", "value": data_abertura or "Não informada"},
                {"label": "Natureza Jurídica", "value": natureza_juridica or "Não informada"},
                {"label": "Porte", "value": porte or "Não informado"},
                {"label": "Capital Social", "value": format_currency_brl(capital_social_val)},
                {"label": "Matriz / Filial", "value": matriz_filial or "Não informado"},
                {"label": "Fonte", "value": source_name},
            ],
            "items": [],
        }
    )

    # 5.2 Seção QSA
    qsa_items: list[dict[str, Any]] = []
    for s in qsa_socios:
        fields_s = [{"label": "Qualificação", "value": s["qualificacao"]}]
        if s["faixaEtaria"] and s["faixaEtaria"] != "Não informada":
            fields_s.append({"label": "Faixa Etária", "value": s["faixaEtaria"]})
        if s["documentoMascarado"]:
            fields_s.append({"label": "CPF/CNPJ Mascarado", "value": s["documentoMascarado"]})
        if s["dataEntrada"]:
            fields_s.append({"label": "Entrada na Sociedade", "value": s["dataEntrada"]})
        qsa_items.append({"title": s["nome"], "fields": fields_s})

    sections.append(
        {
            "id": "qsa",
            "title": "Quadro de Sócios e Administradores (QSA)",
            "description": "Sócios, diretores e administradores registrados no contrato social",
            "status": "available" if qsa_items else "empty",
            "summary": (
                f"{len(qsa_items)} sócio(s) ou administrador(es) observado(s) em {source_name}."
                if qsa_items
                else "Nenhum sócio ou administrador foi informado pela fonte consultada."
            ),
            "fields": [
                {"label": "Total de Integrantes", "value": str(len(qsa_items))},
            ],
            "items": qsa_items,
        }
    )

    # 5.3 Seção Atividade Econômica (CNAE)
    sec_cnae_items: list[dict[str, Any]] = []
    for c in cnaes_secundarios[:8]:
        sec_cnae_items.append(
            {
                "title": f"CNAE {c['codigo']}",
                "fields": [{"label": "Descrição", "value": c["descricao"]}],
            }
        )

    sections.append(
        {
            "id": "cnae",
            "title": "Atividade Econômica & CNAE",
            "description": "Classificação Nacional de Atividades Econômicas (CNAE)",
            "status": "available" if cnae_principal_cod else "empty",
            "summary": f"CNAE Principal: {cnae_principal_cod} — {cnae_principal_desc}"
            if cnae_principal_cod
            else "CNAE não informado.",
            "fields": [
                {
                    "label": "CNAE Principal",
                    "value": f"{cnae_principal_cod} — {cnae_principal_desc}"
                    if cnae_principal_cod
                    else "Não informado",
                },
                {
                    "label": "Atividades Secundárias",
                    "value": f"{len(cnaes_secundarios)} atividade(s) secundária(s) registrada(s)",
                },
            ],
            "items": sec_cnae_items,
        }
    )

    # 5.4 Seção Endereço
    has_address = bool(logradouro_completo or municipio_end or uf_end)
    sections.append(
        {
            "id": "address",
            "title": "Endereço & Localização",
            "description": f"Domicílio fiscal observado em {source_name}",
            "status": "available" if has_address else "empty",
            "summary": f"{municipio_end} / {uf_end} — CEP {cep_formatado}"
            if has_address
            else "Endereço não informado no cadastro público.",
            "fields": [
                {"label": "Logradouro", "value": logradouro_completo or "Não informado"},
                {"label": "Número", "value": numero_end or "S/N"},
                {"label": "Complemento", "value": complemento_end or "—"},
                {"label": "Bairro", "value": bairro_end or "Não informado"},
                {
                    "label": "Município / UF",
                    "value": f"{municipio_end} / {uf_end}" if municipio_end else "Não informado",
                },
                {"label": "CEP", "value": cep_formatado or "Não informado"},
            ],
            "items": [],
        }
    )

    # 5.5 Seção Regime Tributário
    has_tax_data = simples_nacional is not None or mei_enquadrado is not None
    if mei_enquadrado is True:
        tax_summary = "MEI (SIMEI), modalidade vinculada ao Simples Nacional."
        tax_fields = [
            {"label": "Enquadramento", "value": "Microempreendedor Individual (MEI / SIMEI)"},
            {"label": "Regime associado", "value": "Simples Nacional"},
            {"label": "MEI desde", "value": data_opcao_mei or "Não informado"},
            {"label": "Simples desde", "value": data_opcao_simples or "Não informado"},
        ]
    else:
        tax_summary = (
            "Simples Nacional: "
            f"{display_bool(simples_nacional, yes='Optante', no='Não optante')} · "
            f"MEI: {display_bool(mei_enquadrado, yes='Enquadrado', no='Não enquadrado')}."
            if has_tax_data
            else "A fonte consultada não informou o enquadramento tributário."
        )
        tax_fields = [
            {
                "label": "Simples Nacional",
                "value": display_bool(simples_nacional, yes="Optante", no="Não optante"),
            },
            {
                "label": "Microempreendedor Individual (MEI)",
                "value": display_bool(mei_enquadrado, yes="Enquadrado", no="Não enquadrado"),
            },
            {"label": "Simples desde", "value": data_opcao_simples or "Não informado"},
        ]
    sections.append(
        {
            "id": "tax",
            "title": "Regime tributário",
            "description": "Enquadramento informado no cadastro empresarial",
            "status": "available" if has_tax_data else "empty",
            "summary": tax_summary,
            "fields": tax_fields,
            "items": [],
        }
    )

    # 5.6 Contatos cadastrais da empresa. Nunca atribuir estes canais a uma pessoa.
    has_contacts = bool(telefones_oficiais or emails_oficiais)
    contact_fields: list[dict[str, str]] = []
    for idx, tel in enumerate(telefones_oficiais, 1):
        contact_fields.append({"label": f"Telefone cadastral {idx}", "value": tel})
    for idx, em in enumerate(emails_oficiais, 1):
        contact_fields.append({"label": f"E-mail Cadastral {idx}", "value": em})

    sections.append(
        {
            "id": "contacts",
            "title": "Contatos cadastrais da empresa",
            "description": f"Canais empresariais observados em {source_name}; não são do decisor",
            "status": "available" if has_contacts else "empty",
            "summary": (
                f"{len(telefones_oficiais)} telefone(s) e "
                f"{len(emails_oficiais)} e-mail(s) cadastral(is)."
                if has_contacts
                else "Nenhum canal de contato empresarial foi informado pela fonte."
            ),
            "fields": contact_fields
            if has_contacts
            else [{"label": "Canais públicos", "value": "Ausentes na fonte consultada"}],
            "items": [],
        }
    )

    decision_items: list[dict[str, Any]] = []
    for decision_maker in decision_makers:
        fields = [
            {
                "label": "Função",
                "value": ", ".join(decision_maker["funcoes"]) or "Não informada",
            },
        ]
        if decision_maker["senioridades"]:
            fields.append(
                {
                    "label": "Senioridade",
                    "value": ", ".join(decision_maker["senioridades"]),
                }
            )
        for index, email in enumerate(decision_maker["emails"], 1):
            fields.append({"label": f"E-mail {index}", "value": email})
        for index, phone in enumerate(decision_maker["telefones"], 1):
            fields.append({"label": f"Telefone {index}", "value": phone})
        for index, whatsapp in enumerate(decision_maker["whatsapps"], 1):
            fields.append({"label": f"WhatsApp {index}", "value": whatsapp})
        for network, urls in decision_maker["redesSociais"].items():
            for index, url in enumerate(urls, 1):
                suffix = f" {index}" if len(urls) > 1 else ""
                fields.append({"label": f"{network}{suffix}", "value": url})
        decision_items.append({"title": decision_maker["nome"], "fields": fields})
    sections.append(
        {
            "id": "decision_makers",
            "title": "Decisores e canais atribuíveis",
            "description": "Pessoas vinculadas à empresa e dados associados a cada titular",
            "status": "available" if decision_items else "empty",
            "summary": (
                f"{len(decision_items)} pessoa(s) vinculada(s) à empresa."
                if decision_items
                else "Nenhuma pessoa com vínculo empresarial foi localizada nesta consulta."
            ),
            "fields": [],
            "items": decision_items,
        }
    )

    # Cobertura
    total_fields = sum(len(sec["fields"]) for sec in sections)
    total_records = len(qsa_items) + len(sec_cnae_items) + len(decision_items)
    coverage = {
        "requested": len(applied_caps),
        "available": sum(1 for sec in sections if sec["status"] == "available"),
        "fieldCount": total_fields,
        "recordCount": total_records,
    }

    company_summary: dict[str, Any] = {
        "name": nome_fantasia or razao_social or f"Empresa {formatted_cnpj_str}",
        "legalName": razao_social or f"Empresa {formatted_cnpj_str}",
        "cnpj": formatted_cnpj_str,
        "domain": "",
        "status": situacao,
        "industry": cnae_principal_desc or "Atividade empresarial",
        "cnae": f"{cnae_principal_cod} — {cnae_principal_desc}" if cnae_principal_cod else "",
        "companySize": porte,
        "annualRevenue": "",
        "capitalSocial": format_currency_brl(capital_social_val),
        "city": municipio_end,
        "state": uf_end,
        "technologies": [],
        "branchCount": None,
        "partnerCount": len(qsa_socios),
        "emailCount": len(emails_oficiais),
        "phoneCount": len(telefones_oficiais),
        "siteCount": 0,
        "observedAt": source_observed_at.isoformat(),
    }

    return {
        "runId": run_id,
        "companyId": str(company_record.entity.id),
        "capabilities": applied_caps,
        "company": company_summary,
        "registryEvidence": {
            "source": source_name,
            "observedAt": source_observed_at.isoformat(),
            "method": "CACHE" if rfb_data.get("_leadstream_cached") else "API",
            "status": "OBSERVED",
        },
        "coverage": coverage,
        "sections": sections,
        "socioAdministradores": qsa_socios,
        "decisores": decision_makers,
        "emailsValidados": sorted(
            {email for person in decision_makers for email in person["emails"]}
        ),
        "telefonesAtribuiveis": sorted(
            {
                phone
                for person in decision_makers
                for phone in (*person["telefones"], *person["whatsapps"])
            }
        ),
        "contatosCadastraisEmpresa": [
            {"tipo": "EMAIL", "valor": em, "fonte": source_name}
            for em in emails_oficiais
        ]
        + [
            {
                "tipo": "TELEFONE",
                "valor": tel,
                "fonte": source_name,
            }
            for tel in telefones_oficiais
        ],
        "capabilitiesApplied": applied_caps,
        "providerCoverage": {
            "delivered": sorted(cascade_result.delivered_blocks) if cascade_result else [],
            "missing": sorted(cascade_result.missing_blocks) if cascade_result else [],
        },
        "costCredits": (
            BillableEvent.objects.filter(
                tenant=tenant,
                item__batch__idempotency_key=f"individual:{execution_key}"[:128],
            ).count()
            if execution_key
            else 1
        ),
    }
