from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from leadstream.canonical.person_builder import CanonicalPersonBuilder
from leadstream.entities.models import ContactPoint
from leadstream.entities.normalization import only_digits
from leadstream.entities.services import create_contact_point, create_person
from leadstream.intelligence.consignado import (
    calculate_margem_consignavel,
    evaluate_filtro_perda,
    rank_mailing_telefones,
)
from leadstream.intelligence.cpf_rfb import (
    clean_cpf_digits,
    validate_cpf_with_details,
)
from leadstream.providers.adapters.bigdatacorp_person import BigDataCorpPersonAdapter, format_cpf_br
from leadstream.tenancy.models import Tenant
from leadstream.validation.phone_check import get_phone_operator_hint
from leadstream.validation.whatsapp_probe import (
    format_display_phone_br,
    format_e164_whatsapp_br,
    is_whatsapp_probe_configured,
    verify_whatsapp_active,
)

logger = logging.getLogger(__name__)


def validate_cpf_format_and_dv(digits: str) -> tuple[bool, str, str, str]:
    """Valida o formato e os dígitos verificadores do CPF via algoritmo oficial Módulo 11.

    Retorna: (is_valid, expected_dv, received_dv, suggested_cpf)
    """
    cleaned = clean_cpf_digits(digits)
    if len(cleaned) != 11 or len(set(cleaned)) == 1:
        return False, "", cleaned[9:] if len(cleaned) >= 11 else "", ""

    details = validate_cpf_with_details(cleaned)
    expected_dv = str(details.get("digitos_verificadores_calculados") or "")
    received_dv = str(details.get("digitos_verificadores_informados") or "")
    suggested_cpf = clean_cpf_digits(details.get("sugestao_cpf_corrigido") or "")
    if not suggested_cpf:
        suggested_cpf = f"{cleaned[:9]}{expected_dv}"
    return bool(details.get("valido")), expected_dv, received_dv, suggested_cpf


def enrich_person_live(
    query: str,
    tenant: Tenant,
    capabilities: list[str] | None = None,
    http_client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Executa o pipeline especializado de 4 camadas para Crédito Consignado e PF (CPF).

    Camadas:
    1. Validação Cadastral & Filtro de Perda (Expurgo de Óbito & RFB com Zero Créditos).
    2. Core do Consignado (Benefício INSS / SIAPE e Cálculo de Margens 35% + 5% RMC + 5% RCC = 45%).
    3. Filtro de Conformidade 'Não Me Perturbe' (Anatel/Febraban) contra multas do Procon.
    4. Mailing Higienizado (Top 3 Celulares) com Operadora e Probe Ativo de WhatsApp.
    """
    applied_caps = capabilities or [
        "cpf_cadastral",
        "consignado_core",
        "filtro_perda_obito",
        "nao_me_perturbe",
        "mailing_top3_discagem",
        "phones_whatsapp_garantido",
    ]
    run_id = f"run_{uuid.uuid4().hex[:10]}"
    cleaned_digits = only_digits(query)

    # 1. Validação de tamanho
    if len(cleaned_digits) != 11:
        err_msg = (
            f"O termo informado possui {len(cleaned_digits)} dígitos numéricos. "
            "Para consulta de Pessoa Física é necessário informar os 11 dígitos do CPF."
        )
        return {
            "runId": run_id,
            "personId": "",
            "entityType": "PERSON",
            "capabilities": applied_caps,
            "person": None,
            "filtroPerda": None,
            "consignado": None,
            "mailingTop3": [],
            "coverage": {
                "requested": len(applied_caps),
                "available": 0,
                "fieldCount": 0,
                "recordCount": 0,
            },
            "sections": [
                {
                    "id": "validation_error",
                    "title": "Validação Cadastral de CPF",
                    "description": "Verificação de conformidade do documento informado",
                    "status": "unavailable",
                    "summary": "Documento não atende ao padrão de 11 dígitos do CPF.",
                    "errorMessage": err_msg,
                    "fields": [
                        {"label": "Entrada Informada", "value": query},
                        {
                            "label": "Dígitos Identificados",
                            "value": f"{len(cleaned_digits)} de 11 dígitos",
                        },
                    ],
                    "items": [],
                }
            ],
            "telefonesAtribuiveis": [],
            "whatsappGarantido": None,
            "capabilitiesApplied": applied_caps,
            "costCredits": 0,
        }

    # 2. Validação de Módulo 11 (DVs) e Inteligência Fiscal RFB
    details_val = validate_cpf_with_details(cleaned_digits)
    is_valid_dv = bool(details_val.get("valido"))
    expected_dv = str(details_val.get("digitos_verificadores_calculados") or "")
    received_dv = str(details_val.get("digitos_verificadores_informados") or "")
    suggested_cpf = clean_cpf_digits(details_val.get("sugestao_cpf_corrigido") or "")
    regiao_info = details_val.get("regiao_fiscal")
    auditoria_mod11 = details_val.get("auditoria_modulo_11") or {}

    if not is_valid_dv:
        formatted_input = format_cpf_br(cleaned_digits)
        formatted_suggested = format_cpf_br(suggested_cpf) if suggested_cpf else ""
        err_msg = (
            f"O CPF {formatted_input} possui dígitos verificadores incorretos "
            f"(esperado '{expected_dv}', recebido '{received_dv}'). "
            + (f"Sugestão com a mesma raiz: {formatted_suggested}." if suggested_cpf else "")
        )
        return {
            "runId": run_id,
            "personId": "",
            "entityType": "PERSON",
            "capabilities": applied_caps,
            "person": None,
            "filtroPerda": None,
            "consignado": None,
            "mailingTop3": [],
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
                        {"label": "CPF Informado", "value": formatted_input},
                        {"label": "Dígitos Recebidos", "value": received_dv},
                        {"label": "Dígitos Esperados", "value": expected_dv},
                        {"label": "Sugestão Corrigida", "value": formatted_suggested or "N/A"},
                    ],
                    "items": [],
                }
            ],
            "telefonesAtribuiveis": [],
            "whatsappGarantido": None,
            "capabilitiesApplied": applied_caps,
            "costCredits": 0,
        }

    formatted_cpf_str = format_cpf_br(cleaned_digits)
    sections: list[dict[str, Any]] = []

    # Seção Documento Validado com Região Fiscal da RFB
    doc_fields = [
        {"label": "CPF Formatado", "value": formatted_cpf_str},
        {"label": "Dígitos Numéricos", "value": cleaned_digits},
        {"label": "Módulo 11", "value": f"Dígitos Verificadores Autênticos ({expected_dv})"},
        {"label": "Origem da Validação", "value": "Validação Criptográfica Módulo 11 (RFB)"},
    ]
    if regiao_info:
        doc_fields.extend(
            [
                {
                    "label": "Região Fiscal RFB",
                    "value": f"{regiao_info['regiao']} (Código {regiao_info['codigo']})",
                },
                {"label": "Jurisdição Fiscal", "value": regiao_info["jurisdicao"]},
                {"label": "Sede Regional", "value": regiao_info["sede"]},
            ]
        )
    if auditoria_mod11:
        dv1_data = auditoria_mod11.get("dv1", {})
        dv2_data = auditoria_mod11.get("dv2", {})
        soma1_desc = f"1º DV: Soma {dv1_data.get('soma')} -> DV {dv1_data.get('digito_calculado')}"
        soma2_desc = f"2º DV: Soma {dv2_data.get('soma')} -> DV {dv2_data.get('digito_calculado')}"
        doc_fields.append(
            {
                "label": "Demonstrativo Módulo 11",
                "value": f"{soma1_desc} | {soma2_desc}",
            }
        )

    doc_summary = f"CPF {formatted_cpf_str} válido perante os algoritmos da RFB."
    if regiao_info:
        doc_summary += f" Origem fiscal: {regiao_info['regiao']} ({', '.join(regiao_info['ufs'])})."

    sections.append(
        {
            "id": "document_validation",
            "title": "Validação Cadastral do Documento",
            "description": "Conformidade estrutural com os algoritmos oficiais da Receita Federal",
            "status": "available",
            "summary": doc_summary,
            "fields": doc_fields,
            "items": [],
        }
    )

    # 3. Consulta ao Bureau Cadastral (BigDataCorp PF)
    bureau_adapter = BigDataCorpPersonAdapter(client=http_client)
    bureau_configured = bureau_adapter.is_configured()

    candidate_phones: list[dict[str, Any]] = []
    beneficios_inss: list[dict[str, Any]] = []
    vinculos_empregaticios: list[dict[str, Any]] = []
    renda_data: dict[str, Any] = {}
    bloqueios_nmp: list[dict[str, Any]] = []
    bureau_result: dict[str, Any] | None = None

    nome_pessoa = ""
    data_nascimento = None
    idade = None
    nome_mae = ""
    genero = ""
    situacao_cpf = "REGULAR"
    is_deceased = False
    death_date = None

    if bureau_configured:
        try:
            bureau_result = bureau_adapter.enrich_cpf(cleaned_digits)
            if bureau_result.get("encontrado") and bureau_result.get("dados_cadastrais"):
                cad = bureau_result["dados_cadastrais"]
                nome_pessoa = cad.get("nome") or ""
                data_nascimento = cad.get("data_nascimento")
                idade = cad.get("idade")
                nome_mae = cad.get("nome_mae") or ""
                genero = cad.get("genero") or ""
                situacao_cpf = cad.get("situacao_cpf") or "REGULAR"
                is_deceased = bool(cad.get("is_deceased"))
                death_date = cad.get("death_date")

                candidate_phones = bureau_result.get("telefones", [])
                beneficios_inss = bureau_result.get("beneficios_inss", [])
                vinculos_empregaticios = bureau_result.get("vinculos_empregaticios", [])
                renda_data = bureau_result.get("renda", {})
                bloqueios_nmp = bureau_result.get("bloqueios_nao_perturbe", [])

                sections.append(
                    {
                        "id": "cadastral_data",
                        "title": "Dados Cadastrais Oficiais",
                        "description": "Identificação e dados civis consolidados na base cadastral",
                        "status": "available",
                        "summary": f"Registro cadastral localizado: {nome_pessoa}.",
                        "fields": [
                            {"label": "Nome Completo", "value": nome_pessoa or "Não informado"},
                            {"label": "CPF", "value": formatted_cpf_str},
                            {
                                "label": "Data de Nascimento",
                                "value": str(data_nascimento or "Não informada"),
                            },
                            {
                                "label": "Idade Aproximada",
                                "value": f"{idade} anos" if idade else "Não informada",
                            },
                            {"label": "Nome da Mãe", "value": nome_mae or "Não informado"},
                            {"label": "Situação Cadastral", "value": situacao_cpf},
                        ],
                        "items": [],
                    }
                )
            else:
                sections.append(
                    {
                        "id": "cadastral_data",
                        "title": "Dados Cadastrais do Titular",
                        "description": "Consulta na base cadastral da BigDataCorp",
                        "status": "empty",
                        "summary": "Nenhum dado cadastral civil localizado para este CPF.",
                        "fields": [
                            {"label": "CPF Consultado", "value": formatted_cpf_str},
                            {"label": "Situação no Bureau", "value": "Sem registros prévios"},
                        ],
                        "items": [],
                    }
                )
        except Exception as exc:  # noqa: BLE001
            logger.error("Erro ao enriquecer CPF %s na BigDataCorp: %s", cleaned_digits, exc)
            sections.append(
                {
                    "id": "cadastral_data",
                    "title": "Dados Cadastrais do Titular",
                    "description": "Consulta à base BigDataCorp",
                    "status": "unavailable",
                    "summary": "Falha na comunicação com o bureau.",
                    "errorMessage": f"Erro ao consultar bureau cadastral: {exc}",
                    "fields": [{"label": "Status", "value": "Indisponível temporariamente"}],
                    "items": [],
                }
            )
    else:
        # Bureau NÃO configurado
        sections.append(
            {
                "id": "cadastral_data",
                "title": "Dados Cadastrais do Titular (Bureau BigDataCorp)",
                "description": "Identificação civil, nome e histórico de contatos",
                "status": "unavailable",
                "summary": "Bureau BigDataCorp não configurado no ambiente.",
                "errorMessage": (
                    "Para obter o nome civil, nascimento e candidatos telefônicos do CPF, "
                    "configure BIGDATACORP_ACCESS_TOKEN e BIGDATACORP_TOKEN_ID."
                ),
                "fields": [
                    {"label": "CPF Validado", "value": formatted_cpf_str},
                    {"label": "Status do Bureau", "value": "Credenciais não configuradas"},
                ],
                "items": [],
            }
        )

    # 4. Camada 1: Filtro de Perda (Óbito & RFB)
    filtro_perda = evaluate_filtro_perda(
        is_deceased=is_deceased,
        death_date=death_date,
        tax_status=situacao_cpf,
    )
    sections.append(
        {
            "id": "filtro_perda",
            "title": "Camada 1: Filtro de Perda Cadastral (Óbito & RFB)",
            "description": "Expurgo preventivo de titulares falecidos ou com irregularidade na RFB",
            "status": "available",
            "summary": (
                filtro_perda["motivo_expurgo"]
                if not filtro_perda["elegivel_consignado"]
                else "Titular ativo e regular no cadastro central de pessoas físicas."
            ),
            "fields": [
                {"label": "Status Cadastral", "value": filtro_perda["badge_texto"]},
                {
                    "label": "Indicador de Óbito",
                    "value": "Confirmado (Falecido)"
                    if filtro_perda["is_deceased"]
                    else "Não consta óbito",
                },
                {"label": "Data do Óbito", "value": filtro_perda["death_date"] or "N/A"},
                {"label": "Situação Receita Federal", "value": situacao_cpf},
                {
                    "label": "Elegibilidade Consignado",
                    "value": "Apto para Operação"
                    if filtro_perda["elegivel_consignado"]
                    else "Inapto / Expurgado",
                },
                {
                    "label": "Tarifa de Consulta",
                    "value": "Cobrança Padrão (1 Crédito)"
                    if filtro_perda["deve_cobrar_credito"]
                    else "Isento / Zero Créditos (Expurgo Automático)",
                },
            ],
            "items": [],
        }
    )

    # 5. Camada 2: Core Consignado (INSS / SIAPE / Cálculo de Margens)
    consignado_data: dict[str, Any] = {}
    base_salary_val = 0.0

    if beneficios_inss:
        # Priorizar benefícios aptos
        aptos = [b for b in beneficios_inss if b.get("categoria") == "APTO_CONSIGNAVEL"]
        selected_ben = aptos[0] if aptos else beneficios_inss[0]
        base_salary_val = float(
            selected_ben.get("valor_beneficio") or renda_data.get("renda_estimada") or 0.0
        )
        margens = calculate_margem_consignavel(base_salary_val)

        consignado_data = {
            "elegivel": filtro_perda["elegivel_consignado"]
            and selected_ben.get("elegivel_consignado", True),
            "vinculoPrincipal": "INSS - Previdência Social",
            "numeroBeneficio": selected_ben.get("numero_beneficio") or "Não informado",
            "especieCodigo": selected_ben.get("especie_codigo"),
            "especieDescricao": selected_ben.get("especie_descricao"),
            "categoriaElegibilidade": selected_ben.get("categoria"),
            "alerta": selected_ben.get("alerta"),
            "salarioBase": margens["salario_base"],
            "margemEmprestimo35": margens["margem_emprestimo_35"],
            "margemRmcCartao5": margens["margem_rmc_cartao_5"],
            "margemRccBeneficio5": margens["margem_rcc_beneficio_5"],
            "margemTotal45": margens["margem_total_45"],
            "percentualTotal": 45.0,
        }
    elif vinculos_empregaticios:
        servidores = [v for v in vinculos_empregaticios if v.get("eh_servidor_publico")]
        selected_vinc = servidores[0] if servidores else vinculos_empregaticios[0]
        base_salary_val = float(
            selected_vinc.get("salario") or renda_data.get("renda_estimada") or 0.0
        )
        margens = calculate_margem_consignavel(base_salary_val)

        vinc_label = (
            "SIAPE / Servidor Público"
            if selected_vinc.get("eh_servidor_publico")
            else "CLT / Emprego Formal"
        )
        consignado_data = {
            "elegivel": filtro_perda["elegivel_consignado"]
            and bool(selected_vinc.get("ativo", True)),
            "vinculoPrincipal": vinc_label,
            "numeroBeneficio": selected_vinc.get("matricula") or "N/A",
            "especieCodigo": "SIAPE" if selected_vinc.get("eh_servidor_publico") else "CLT",
            "especieDescricao": (
                f"{selected_vinc.get('cargo') or 'Cargo não informado'} ("
                f"{selected_vinc.get('orgao_siape') or selected_vinc.get('empregador') or 'Órgão'})"
            ),
            "categoriaElegibilidade": (
                "APTO_CONSIGNAVEL"
                if selected_vinc.get("eh_servidor_publico")
                else "CONSIGNADO_PRIVADO"
            ),
            "alerta": None
            if selected_vinc.get("eh_servidor_publico")
            else "Convênio consignado depende de acordo da empresa empregadora.",
            "salarioBase": margens["salario_base"],
            "margemEmprestimo35": margens["margem_emprestimo_35"],
            "margemRmcCartao5": margens["margem_rmc_cartao_5"],
            "margemRccBeneficio5": margens["margem_rcc_beneficio_5"],
            "margemTotal45": margens["margem_total_45"],
            "percentualTotal": 45.0,
        }
    elif renda_data.get("renda_estimada", 0) > 0:
        base_salary_val = float(renda_data.get("renda_estimada", 0))
        margens = calculate_margem_consignavel(base_salary_val)
        consignado_data = {
            "elegivel": filtro_perda["elegivel_consignado"],
            "vinculoPrincipal": "Renda Estimada pelo Bureau",
            "numeroBeneficio": "N/A",
            "especieCodigo": "RENDA_ESTIMADA",
            "especieDescricao": f"Faixa de Renda: {renda_data.get('faixa_renda') or 'Padrão'}",
            "categoriaElegibilidade": "ANALISE_MANUAL",
            "alerta": "Sem benefício INSS averbado. Margem estimada sobre poder aquisitivo.",
            "salarioBase": margens["salario_base"],
            "margemEmprestimo35": margens["margem_emprestimo_35"],
            "margemRmcCartao5": margens["margem_rmc_cartao_5"],
            "margemRccBeneficio5": margens["margem_rcc_beneficio_5"],
            "margemTotal45": margens["margem_total_45"],
            "percentualTotal": 45.0,
        }
    else:
        consignado_data = {
            "elegivel": False,
            "vinculoPrincipal": "Sem Vínculo Previdenciário",
            "numeroBeneficio": "N/A",
            "especieCodigo": "N/A",
            "especieDescricao": "Nenhum benefício ou vínculo salarial registrado",
            "categoriaElegibilidade": "INAPTO",
            "alerta": "Dados insuficientes no bureau para cálculo de margem consignável.",
            "salarioBase": 0.0,
            "margemEmprestimo35": 0.0,
            "margemRmcCartao5": 0.0,
            "margemRccBeneficio5": 0.0,
            "margemTotal45": 0.0,
            "percentualTotal": 45.0,
        }

    if consignado_data["salarioBase"] > 0:
        sections.append(
            {
                "id": "consignado_core",
                "title": "Camada 2: Core Consignado (INSS / SIAPE & Margem 45%)",
                "description": "Cálculo de margem consignável segundo a Lei Federal nº 14.431/2022",
                "status": "available",
                "summary": (
                    f"{consignado_data['vinculoPrincipal']}: Margem de "
                    f"R$ {consignado_data['margemTotal45']:,.2f} (35% emp. + 5% RMC + 5% RCC)."
                ),
                "fields": [
                    {"label": "Vínculo Identificado", "value": consignado_data["vinculoPrincipal"]},
                    {
                        "label": "Número do Benefício (NB)",
                        "value": consignado_data["numeroBeneficio"],
                    },
                    {
                        "label": "Espécie Previdenciária",
                        "value": consignado_data["especieDescricao"],
                    },
                    {
                        "label": "Classificação de Aptidão",
                        "value": consignado_data["categoriaElegibilidade"],
                    },
                    {
                        "label": "Salário / Benefício Base",
                        "value": f"R$ {consignado_data['salarioBase']:,.2f}",
                    },
                    {
                        "label": "Margem Empréstimo (35%)",
                        "value": f"R$ {consignado_data['margemEmprestimo35']:,.2f}",
                    },
                    {
                        "label": "Margem Cartão RMC (5%)",
                        "value": f"R$ {consignado_data['margemRmcCartao5']:,.2f}",
                    },
                    {
                        "label": "Margem Cartão Benefício RCC (5%)",
                        "value": f"R$ {consignado_data['margemRccBeneficio5']:,.2f}",
                    },
                    {
                        "label": "Margem Total Estimada (45%)",
                        "value": f"R$ {consignado_data['margemTotal45']:,.2f}",
                    },
                    {
                        "label": "Alerta Operacional",
                        "value": consignado_data["alerta"] or "Nenhum bloqueio detectado",
                    },
                ],
                "items": [],
            }
        )
    else:
        sections.append(
            {
                "id": "consignado_core",
                "title": "Camada 2: Core Consignado (INSS / SIAPE)",
                "description": "Identificação de benefícios previdenciários e margem consignável",
                "status": "empty",
                "summary": "Nenhum benefício INSS ou salário localizado no bureau.",
                "fields": [
                    {
                        "label": "Situação de Vínculo",
                        "value": "Sem registros previdenciários no bureau",
                    },
                    {"label": "Elegibilidade", "value": "Requer averiguação manual"},
                ],
                "items": [],
            }
        )

    # 6. Camada 3: Filtro de Não Me Perturbe (Anatel/Febraban)
    total_bloqueados_nmp = len(bloqueios_nmp) if bloqueios_nmp else 0
    sections.append(
        {
            "id": "nao_me_perturbe",
            "title": "Camada 3: Higienização de Não Me Perturbe (Anatel / Febraban)",
            "description": "Proteção jurídica contra multas de telemarketing ativo em consignado",
            "status": "available",
            "summary": (
                f"{total_bloqueados_nmp} registro(s) de bloqueio no Não Me Perturbe."
                if total_bloqueados_nmp > 0
                else "Nenhum bloqueio no Não Me Perturbe cadastrado para os números do titular."
            ),
            "fields": [
                {
                    "label": "Conformidade Regulatória",
                    "value": "Anatel & Febraban (Sistema Não Me Perturbe)",
                },
                {"label": "Telefones Bloqueados", "value": str(total_bloqueados_nmp)},
                {
                    "label": "Risco de Multa (Procon)",
                    "value": "Alto para ligações frias"
                    if total_bloqueados_nmp > 0
                    else "Baixo / Conforme",
                },
                {
                    "label": "Diretriz Operacional",
                    "value": "Priorizar canais autorizados ou WhatsApp conforme ranking"
                    if total_bloqueados_nmp > 0
                    else "Discagem telefônica livre",
                },
            ],
            "items": [],
        }
    )

    # 7. Camada 4: WhatsApp Probe Ativo & Mailing Top 3
    probe_configured = is_whatsapp_probe_configured()
    whatsapp_garantido: dict[str, Any] | None = None
    telefones_analisados: list[dict[str, Any]] = []

    if candidate_phones:
        for p in candidate_phones:
            num = p["numero"]
            ddd = p["ddd"]
            clean_full = format_e164_whatsapp_br(num, ddd=ddd)
            display_num = format_display_phone_br(clean_full)
            operadora = p.get("operadora") or get_phone_operator_hint(ddd, num)

            if probe_configured:
                probe_res = verify_whatsapp_active(phone=num, ddd=ddd, client=http_client)
                has_wa = bool(probe_res.get("tem_whatsapp"))
                tipo_conta = str(probe_res.get("tipo_conta") or "NENHUMA")
                jid = probe_res.get("jid")
                foto = probe_res.get("foto_perfil")

                tel_item = {
                    "numero": display_num,
                    "numeroE164": clean_full,
                    "ddd": ddd,
                    "tipo": "Celular" if p.get("is_celular") else "Fixo",
                    "operadora": operadora,
                    "whatsappDisponivel": has_wa,
                    "tipoConta": tipo_conta,
                    "jid": jid,
                    "fotoPerfil": foto,
                    "linkWhatsApp": f"https://wa.me/{clean_full}" if has_wa else None,
                    "atribuicao": "Probe Ativo em Tempo Real (Evolution/WPPConnect)",
                    "scoreBureau": p.get("score", 0),
                }
                telefones_analisados.append(tel_item)

                if has_wa and not whatsapp_garantido:
                    whatsapp_garantido = {
                        "garantido": True,
                        "numero": display_num,
                        "numeroE164": clean_full,
                        "tipoConta": tipo_conta,
                        "jid": jid,
                        "fotoPerfil": foto,
                        "linkDireto": f"https://wa.me/{clean_full}",
                        "verificadoEm": probe_res.get("verificado_em"),
                        "provedorProbe": probe_res.get("provedor"),
                    }
            else:
                # Probe não configurado
                telefones_analisados.append(
                    {
                        "numero": display_num,
                        "numeroE164": clean_full,
                        "ddd": ddd,
                        "tipo": "Celular" if p.get("is_celular") else "Fixo",
                        "operadora": operadora,
                        "whatsappDisponivel": False,
                        "tipoConta": "NAO_VERIFICADO",
                        "jid": None,
                        "fotoPerfil": None,
                        "linkWhatsApp": None,
                        "atribuicao": "Bureau Cadastral (Sem Probe Ativo)",
                        "scoreBureau": p.get("score", 0),
                    }
                )

    # Ranking Mailing Top 3
    mailing_top3 = rank_mailing_telefones(
        candidate_phones=telefones_analisados,
        block_records=bloqueios_nmp,
        max_count=3,
    )

    if mailing_top3:
        m_fields = []
        for item in mailing_top3:
            wa_desc = "WhatsApp Confirmado" if item["whatsappDisponivel"] else "Sem WhatsApp"
            nmp_desc = (
                "⛔ Não Me Perturbe"
                if item["naoMePerturbe"]["inscrito_nao_me_perturbe"]
                else "✅ Liberado Telemarketing"
            )
            score_info = f"(Score {item['scoreAssertividade']}/100)"
            m_fields.append(
                {
                    "label": f"Opção {item['ordemRecomendada']} ({item['operadora']})",
                    "value": f"{item['numeroFormatado']} - {wa_desc} | {nmp_desc} {score_info}",
                }
            )

        sections.append(
            {
                "id": "mailing_top3",
                "title": "Camada 4: Mailing Higienizado (Top 3 Celulares & Score de Discagem)",
                "description": "Ordenação por assertividade de contato e conformidade legal",
                "status": "available",
                "summary": (
                    f"{len(mailing_top3)} telefone(s) selecionado(s) para contato prioritário."
                ),
                "fields": m_fields,
                "items": [],
            }
        )

    # Seção WhatsApp Garantido
    if whatsapp_garantido:
        sections.append(
            {
                "id": "whatsapp_verified",
                "title": "WhatsApp Verificado com Garantia",
                "description": "Verificação técnica ativa realizada na rede do WhatsApp",
                "status": "available",
                "summary": f"WhatsApp ativo e garantido: {whatsapp_garantido['numero']}.",
                "fields": [
                    {"label": "Número WhatsApp", "value": whatsapp_garantido["numero"]},
                    {"label": "Conta WhatsApp", "value": whatsapp_garantido["tipoConta"]},
                    {"label": "JID do Contato", "value": str(whatsapp_garantido["jid"])},
                    {"label": "Link de Conversa Direta", "value": whatsapp_garantido["linkDireto"]},
                    {
                        "label": "Origem da Validação",
                        "value": str(whatsapp_garantido["provedorProbe"]),
                    },
                ],
                "items": [],
            }
        )
    elif not probe_configured:
        sections.append(
            {
                "id": "whatsapp_verified",
                "title": "Verificação de WhatsApp (Probe)",
                "description": "Checagem de conectividade de conta WhatsApp",
                "status": "unavailable",
                "summary": "Gateway de WhatsApp Probe não está configurado no servidor.",
                "errorMessage": (
                    "Para garantia técnica de entrega do número de WhatsApp, configure "
                    "WHATSAPP_PROBE_URL e WHATSAPP_PROBE_API_KEY no EasyPanel/ambiente."
                ),
                "fields": [
                    {"label": "Status do Probe", "value": "Não configurado"},
                    {
                        "label": "Telefones Identificados",
                        "value": f"{len(telefones_analisados)} encontrados no bureau",
                    },
                ],
                "items": [],
            }
        )
    else:
        sections.append(
            {
                "id": "whatsapp_verified",
                "title": "WhatsApp Verificado com Garantia",
                "description": "Verificação técnica ativa na rede do WhatsApp",
                "status": "empty",
                "summary": "Nenhum dos telefones candidatos possui conta ativa no WhatsApp.",
                "fields": [
                    {"label": "Telefones Testados", "value": str(len(telefones_analisados))},
                    {"label": "Status", "value": "Nenhum WhatsApp ativo confirmado"},
                ],
                "items": [],
            }
        )

    # Seção Telefones Candidatos
    if telefones_analisados:
        tel_fields = []
        for idx, t in enumerate(telefones_analisados, 1):
            status_desc = "WhatsApp Ativo" if t["whatsappDisponivel"] else "Sem WhatsApp"
            tel_fields.append(
                {
                    "label": f"Telefone {idx} ({t.get('operadora', 'N/A')})",
                    "value": f"{t['numero']} ({status_desc})",
                }
            )

        sections.append(
            {
                "id": "phones_list",
                "title": "Canais Telefônicos do Titular",
                "description": "Linhas telefônicas vinculadas ao CPF submetidas à verificação",
                "status": "available",
                "summary": f"{len(telefones_analisados)} telefone(s) analisado(s).",
                "fields": tel_fields,
                "items": [],
            }
        )

    # 8. Persistência Canônica no Banco de Dados do Tenant
    person_record = None
    try:
        with transaction.atomic():
            person_record = create_person(
                tenant=tenant,
                full_name=nome_pessoa or f"Titular CPF {formatted_cpf_str}",
                cpf=cleaned_digits,
                hash_key=getattr(settings, "DATA_HASH_KEY", "dev-only-data-hash-key"),
            )
            if whatsapp_garantido and whatsapp_garantido.get("numeroE164"):
                create_contact_point(
                    tenant=tenant,
                    owner=person_record.entity,
                    kind=ContactPoint.Kind.WHATSAPP,
                    value=whatsapp_garantido["numeroE164"],
                    status=ContactPoint.Status.CONFIRMED,
                    capabilities={
                        "whatsapp": True,
                        "business": whatsapp_garantido["tipoConta"] == "WHATSAPP_BUSINESS",
                        "jid": whatsapp_garantido.get("jid"),
                        "foto_perfil": whatsapp_garantido.get("fotoPerfil"),
                        "verified_at": whatsapp_garantido.get("verificadoEm"),
                    },
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Falha ao persistir registro canônico de Person para CPF %s: %s", cleaned_digits, exc
        )

    # 9. Cobertura e Resposta
    total_fields = sum(len(sec["fields"]) for sec in sections)
    coverage = {
        "requested": len(applied_caps),
        "available": sum(1 for sec in sections if sec["status"] == "available"),
        "fieldCount": total_fields,
        "recordCount": len(telefones_analisados),
    }

    # Resumo consolidado da Pessoa (exibindo CPF em texto claro!)
    primary_phone = (
        whatsapp_garantido["numero"]
        if whatsapp_garantido
        else (
            mailing_top3[0]["numeroFormatado"]
            if mailing_top3
            else (telefones_analisados[0]["numero"] if telefones_analisados else "")
        )
    )

    person_summary = {
        "id": str(person_record.entity.id) if person_record else str(uuid.uuid4()),
        "name": nome_pessoa or f"Titular CPF {formatted_cpf_str}",
        "cpf": formatted_cpf_str,
        "cpfDigits": cleaned_digits,
        "birthDate": str(data_nascimento)[:10] if data_nascimento else None,
        "age": idade,
        "motherName": nome_mae or None,
        "gender": genero or None,
        "taxStatus": situacao_cpf,
        "isDeceased": filtro_perda["is_deceased"],
        "deathDate": filtro_perda["death_date"],
        "phone": primary_phone,
        "whatsapp": whatsapp_garantido["numero"] if whatsapp_garantido else None,
        "hasWhatsApp": bool(whatsapp_garantido),
        "observedAt": timezone.now().isoformat(),
    }

    # Regra estrita de cobrança de créditos:
    # 1. Se expurgado por óbito, NENHUM crédito é cobrado (costCredits = 0)
    # 2. Se nenhum dado útil localizado, costCredits = 0
    # 3. Se lead válido e vivo com dados entregues, costCredits = 1
    if filtro_perda["status"] == "EXPURGADO_OBITO":
        cost_credits = 0
    elif not (nome_pessoa or whatsapp_garantido or mailing_top3):
        cost_credits = 0
    else:
        cost_credits = 1

    # Construção do Payload Canônico Completo (CanonicalPersonPayload)
    canonical_payload: dict[str, Any] | None = None
    try:
        builder = CanonicalPersonBuilder(tenant=tenant)
        bureau_data_for_canonical = bureau_result if (bureau_configured and bureau_result) else None
        canonical_payload = builder.build(
            query=cleaned_digits,
            bureau_data=bureau_data_for_canonical,
            http_client=http_client,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao construir payload canônico para CPF %s: %s", cleaned_digits, exc)

    return {
        "runId": run_id,
        "personId": person_summary["id"],
        "entityType": "PERSON",
        "capabilities": applied_caps,
        "person": person_summary,
        "filtroPerda": filtro_perda,
        "consignado": consignado_data,
        "mailingTop3": mailing_top3,
        "coverage": coverage,
        "sections": sections,
        "telefonesAtribuiveis": telefones_analisados,
        "whatsappGarantido": whatsapp_garantido,
        "capabilitiesApplied": applied_caps,
        "costCredits": cost_credits,
        "regiaoFiscal": regiao_info,
        "canonical": canonical_payload,
    }
