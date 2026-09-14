from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx
from django.db import transaction
from django.utils import timezone

from leadstream.entities.models import Company, ContactPoint
from leadstream.entities.normalization import (
    DataValidationError,
    cnpj_root,
    normalize_cnpj,
    only_digits,
)
from leadstream.entities.services import (
    create_company,
    create_contact_point,
    create_person,
    create_relationship,
)
from leadstream.tenancy.models import Tenant

logger = logging.getLogger(__name__)


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


def format_currency_brl(value: float | int) -> str:
    """Formata valor monetário em Reais (BRL)."""
    try:
        val = float(value)
        formatted = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {formatted}"
    except (ValueError, TypeError):
        return "R$ 0,00"


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


def fetch_official_rfb_data(cnpj_digits: str) -> dict[str, Any] | None:
    """Consulta dados cadastrais oficiais na RFB via BrasilAPI / MinhaReceita."""
    # 1. Tentar BrasilAPI
    try:
        url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_digits}"
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                data: dict[str, Any] = resp.json()
                if isinstance(data, dict) and data.get("razao_social"):
                    return data
            elif resp.status_code == 404:
                return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha na consulta BrasilAPI para CNPJ %s: %s", cnpj_digits, exc)

    # 2. Fallback MinhaReceita
    try:
        url = f"https://minhareceita.org/{cnpj_digits}"
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and data.get("razao_social"):
                    return data
            elif resp.status_code == 404:
                return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha na consulta MinhaReceita para CNPJ %s: %s", cnpj_digits, exc)

    return None


def enrich_company_live(
    query: str,
    tenant: Tenant,
    capabilities: list[str] | None = None,
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
        existing_comp = Company.objects.filter(entity__tenant=tenant, cnpj_root=root).first()
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
                        "title": "Registro da Receita Federal",
                        "description": "Base de dados pública de pessoas jurídicas (RFB)",
                        "status": "unavailable",
                        "summary": "CNPJ não encontrado na base da Receita Federal.",
                        "errorMessage": (
                            f"O CNPJ {formatted_cnpj_str} não possui registro "
                            "ativo ou inativo na base oficial da Receita Federal."
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

    # --- 3. Extração dos dados oficiais reais ---
    razao_social = str(rfb_data.get("razao_social") or "").strip() if rfb_data else ""
    nome_fantasia = str(rfb_data.get("nome_fantasia") or "").strip() if rfb_data else ""
    situacao = (
        str(rfb_data.get("descricao_situacao_cadastral") or "ATIVA").strip()
        if rfb_data
        else "ATIVA"
    )
    data_abertura = str(rfb_data.get("data_inicio_atividade") or "").strip() if rfb_data else ""
    natureza_juridica = str(rfb_data.get("natureza_juridica") or "").strip() if rfb_data else ""
    porte = str(rfb_data.get("porte") or "").strip() if rfb_data else ""
    capital_social_val = float(rfb_data.get("capital_social") or 0.0) if rfb_data else 0.0
    cnae_principal_cod = str(rfb_data.get("cnae_fiscal") or "").strip() if rfb_data else ""
    cnae_principal_desc = (
        str(rfb_data.get("cnae_fiscal_descricao") or "").strip() if rfb_data else ""
    )
    matriz_filial = (
        str(rfb_data.get("descricao_identificador_matriz_filial") or "MATRIZ").strip()
        if rfb_data
        else "MATRIZ"
    )

    # Endereço
    tipo_logradouro = (
        str(rfb_data.get("descricao_tipo_de_logradouro") or "").strip() if rfb_data else ""
    )
    logradouro_nome = str(rfb_data.get("logradouro") or "").strip() if rfb_data else ""
    logradouro_completo = f"{tipo_logradouro} {logradouro_nome}".strip()
    numero_end = str(rfb_data.get("numero") or "").strip() if rfb_data else ""
    complemento_end = str(rfb_data.get("complemento") or "").strip() if rfb_data else ""
    bairro_end = str(rfb_data.get("bairro") or "").strip() if rfb_data else ""
    municipio_end = str(rfb_data.get("municipio") or "").strip() if rfb_data else ""
    uf_end = str(rfb_data.get("uf") or "").strip() if rfb_data else ""
    cep_end = str(rfb_data.get("cep") or "").strip() if rfb_data else ""
    cep_formatado = f"{cep_end[:5]}-{cep_end[5:]}" if len(cep_end) == 8 else cep_end

    # Tributação
    simples_nacional = bool(rfb_data.get("opcao_pelo_simples")) if rfb_data else False
    mei_enquadrado = bool(rfb_data.get("opcao_pelo_mei")) if rfb_data else False
    data_opcao_simples = str(rfb_data.get("data_opcao_pelo_simples") or "") if rfb_data else ""
    data_opcao_mei = str(rfb_data.get("data_opcao_pelo_mei") or "") if rfb_data else ""

    # Quadro de Sócios e Administradores (QSA) Real
    raw_qsa: list[dict[str, Any]] = rfb_data.get("qsa", []) if rfb_data else []
    qsa_socios: list[dict[str, Any]] = []
    for s in raw_qsa:
        nome_socio = str(s.get("nome_socio") or "").strip()
        if nome_socio:
            qsa_socios.append(
                {
                    "nome": nome_socio,
                    "qualificacao": str(s.get("qualificacao_socio") or "Sócio").strip(),
                    "faixaEtaria": str(s.get("faixa_etaria") or "Não informada").strip(),
                    "documentoMascarado": str(s.get("cnpj_cpf_do_socio") or "").strip(),
                    "dataEntrada": str(s.get("data_entrada_sociedade") or "").strip(),
                }
            )

    # CNAEs secundários reais
    raw_sec: list[dict[str, Any]] = rfb_data.get("cnaes_secundarios", []) if rfb_data else []
    cnaes_secundarios: list[dict[str, str]] = []
    for c in raw_sec:
        c_code = str(c.get("codigo") or "").strip()
        c_desc = str(c.get("descricao") or "").strip()
        if c_code:
            cnaes_secundarios.append({"codigo": c_code, "descricao": c_desc})

    # Contatos Oficiais declarados na RFB (NUNCA inventar dados!)
    telefones_oficiais: list[str] = []
    t1 = str(rfb_data.get("ddd_telefone_1") or "").strip() if rfb_data else ""
    t2 = str(rfb_data.get("ddd_telefone_2") or "").strip() if rfb_data else ""
    if t1 and len(only_digits(t1)) >= 8:
        telefones_oficiais.append(format_phone_br(t1))
    if t2 and len(only_digits(t2)) >= 8 and t2 != t1:
        telefones_oficiais.append(format_phone_br(t2))

    emails_oficiais: list[str] = []
    email_rfb = str(rfb_data.get("email") or "").strip() if rfb_data else ""
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
            is_headquarters=(matriz_filial.upper() == "MATRIZ"),
        )
        company_record = comp_identity.company

        # Persistir sócios no grafo de entidades
        for socio in qsa_socios:
            try:
                person = create_person(
                    tenant=tenant,
                    full_name=socio["nome"],
                )
                create_relationship(
                    tenant=tenant,
                    person=person,
                    company=company_record,
                    qualification=socio["qualificacao"],
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

    # --- 5. Construção das seções canônicas de exibição ---
    sections: list[dict[str, Any]] = []

    # 5.1 Seção Cadastral
    sections.append(
        {
            "id": "registry",
            "title": "Dados Cadastrais & RFB",
            "description": "Registro oficial de pessoa jurídica na Receita Federal do Brasil",
            "status": "available",
            "summary": (
                f"Situação cadastral {situacao} na Receita Federal. "
                f"Registro oficial de {matriz_filial}."
            ),
            "fields": [
                {"label": "CNPJ", "value": formatted_cnpj_str},
                {"label": "Razão Social", "value": razao_social or "Não informada"},
                {"label": "Nome Fantasia", "value": nome_fantasia or "Não informado"},
                {"label": "Situação Cadastral", "value": situacao},
                {"label": "Data de Abertura", "value": data_abertura or "Não informada"},
                {"label": "Natureza Jurídica", "value": natureza_juridica or "Não informada"},
                {"label": "Porte", "value": porte or "DEMAIS"},
                {"label": "Capital Social", "value": format_currency_brl(capital_social_val)},
                {"label": "Matriz / Filial", "value": matriz_filial},
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
                f"{len(qsa_items)} sócio(s) ou administrador(es) identificado(s) na base oficial."
                if qsa_items
                else "Nenhum sócio ou administrador constante no cadastro público da RFB."
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
            "description": "Domicílio fiscal registrado perante a Receita Federal",
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
    sections.append(
        {
            "id": "tax",
            "title": "Regime Tributário & Fiscal",
            "description": "Opção pelo Simples Nacional, MEI e regularidade",
            "status": "available",
            "summary": (
                f"Simples: {'Optante' if simples_nacional else 'Não optante'} · "
                f"MEI: {'Sim' if mei_enquadrado else 'Não'}"
            ),
            "fields": [
                {
                    "label": "Simples Nacional",
                    "value": "Optante" if simples_nacional else "Não optante",
                },
                {"label": "Microempreendedor (MEI)", "value": "Sim" if mei_enquadrado else "Não"},
                {"label": "Opção Simples Desde", "value": data_opcao_simples or "—"},
                {"label": "Opção MEI Desde", "value": data_opcao_mei or "—"},
            ],
            "items": [],
        }
    )

    # 5.6 Seção Contatos Oficiais RFB (Sem dados inventados!)
    has_contacts = bool(telefones_oficiais or emails_oficiais)
    contact_fields: list[dict[str, str]] = []
    for idx, tel in enumerate(telefones_oficiais, 1):
        contact_fields.append({"label": f"Telefone RFB {idx}", "value": tel})
    for idx, em in enumerate(emails_oficiais, 1):
        contact_fields.append({"label": f"E-mail Cadastral {idx}", "value": em})

    sections.append(
        {
            "id": "contacts",
            "title": "Contatos Cadastrais RFB",
            "description": "Canais de contato oficiais declarados perante a Receita Federal",
            "status": "available" if has_contacts else "empty",
            "summary": (
                f"{len(telefones_oficiais)} telefone(s) e {len(emails_oficiais)} e-mail(s) na RFB."
                if has_contacts
                else "Nenhum canal de contato informado no cadastro da Receita Federal."
            ),
            "fields": contact_fields
            if has_contacts
            else [{"label": "Canais Públicos Declarados", "value": "Ausentes no cadastro da RFB"}],
            "items": [],
        }
    )

    # Cobertura
    total_fields = sum(len(sec["fields"]) for sec in sections)
    total_records = len(qsa_items) + len(sec_cnae_items)
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
        "companySize": porte or "DEMAIS",
        "annualRevenue": format_currency_brl(capital_social_val),
        "city": municipio_end,
        "state": uf_end,
        "technologies": [],
        "branchCount": 0 if matriz_filial.upper() == "MATRIZ" else 1,
        "partnerCount": len(qsa_socios),
        "emailCount": len(emails_oficiais),
        "phoneCount": len(telefones_oficiais),
        "siteCount": 0,
        "observedAt": timezone.now().isoformat(),
    }

    return {
        "runId": run_id,
        "companyId": str(company_record.entity.id),
        "capabilities": applied_caps,
        "company": company_summary,
        "coverage": coverage,
        "sections": sections,
        "socioAdministradores": qsa_socios,
        "emailsValidados": [
            {"email": em, "status": "CADASTRO_RFB", "score": 85} for em in emails_oficiais
        ],
        "telefonesAtribuiveis": [
            {
                "numero": tel,
                "tipo": "Comercial (RFB)",
                "whatsappDisponivel": False,
                "atribuicao": "Cadastro Oficial RFB",
            }
            for tel in telefones_oficiais
        ],
        "capabilitiesApplied": applied_caps,
        "costCredits": 1,
    }
