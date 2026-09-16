from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from leadstream.canonical.person_builder import CanonicalPersonBuilder
from leadstream.common.redaction import correlation_tag, mask_cpf
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
from leadstream.providers.adapters.portal_transparencia import (
    PortalTransparenciaAdapter,
    public_person_portal_profile,
)
from leadstream.providers.exceptions import ProviderError
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
    """Valida formato e dígitos verificadores do CPF pelo cálculo Módulo 11.

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
        "government_intelligence",
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

    # 2. Validação estrutural de Módulo 11 (não consulta situação cadastral)
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
                    "description": "Validação estrutural local pelo cálculo Módulo 11",
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

    # Seção de formato estrutural. Isso não confirma existência ou regularidade cadastral.
    doc_fields = [
        {"label": "CPF Formatado", "value": formatted_cpf_str},
        {"label": "Dígitos Numéricos", "value": cleaned_digits},
        {"label": "Módulo 11", "value": f"Dígitos verificadores compatíveis ({expected_dv})"},
        {"label": "Origem da Validação", "value": "Cálculo estrutural local; sem consulta à RFB"},
    ]
    if regiao_info:
        doc_fields.extend(
            [
                {
                    "label": "Região de inscrição indicada pelo 9º dígito",
                    "value": f"{regiao_info['regiao']} (Código {regiao_info['codigo']})",
                },
                {"label": "UFs historicamente associadas", "value": regiao_info["jurisdicao"]},
                {"label": "Referência regional", "value": regiao_info["sede"]},
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

    doc_summary = f"CPF {formatted_cpf_str} possui formato e dígitos verificadores compatíveis."
    if regiao_info:
        doc_summary += (
            f" O 9º dígito indica a região de inscrição {regiao_info['regiao']} "
            f"({', '.join(regiao_info['ufs'])}); isso não indica domicílio atual."
        )

    sections.append(
        {
            "id": "document_validation",
            "title": "Validação Estrutural do Documento",
            "description": "Cálculo local de formato e dígitos; não confirma situação cadastral",
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
    enderecos: list[dict[str, Any]] = []
    beneficios_sociais: list[dict[str, Any]] = []
    restricoes_financeiras: dict[str, Any] = {}
    relacionamentos_bancarios: list[dict[str, Any]] = []
    dados_eleitorais: dict[str, Any] | None = None
    bloqueios_nmp: list[dict[str, Any]] | None = None
    bureau_result: dict[str, Any] | None = None
    bureau_identity_found = False
    government_intelligence: dict[str, Any] | None = None

    nome_pessoa = ""
    data_nascimento = None
    idade = None
    nome_mae = ""
    genero = ""
    situacao_cpf = "DESCONHECIDA"
    is_deceased: bool | None = None
    death_date = None

    if bureau_configured:
        try:
            bureau_result = bureau_adapter.enrich_cpf(cleaned_digits)
            if bureau_result.get("encontrado") and bureau_result.get("dados_cadastrais"):
                bureau_identity_found = True
                cad = bureau_result["dados_cadastrais"]
                nome_pessoa = cad.get("nome") or ""
                data_nascimento = cad.get("data_nascimento")
                idade = cad.get("idade")
                nome_mae = cad.get("nome_mae") or ""
                genero = cad.get("genero") or ""
                situacao_cpf = cad.get("situacao_cpf") or "DESCONHECIDA"
                is_deceased = cad.get("is_deceased")
                death_date = cad.get("death_date")

                candidate_phones = bureau_result.get("telefones", [])
                beneficios_inss = bureau_result.get("beneficios_inss", [])
                vinculos_empregaticios = bureau_result.get("vinculos_empregaticios", [])
                renda_data = bureau_result.get("renda", {})
                enderecos = bureau_result.get("enderecos", [])
                beneficios_sociais = bureau_result.get("beneficios_sociais", [])
                restricoes_financeiras = bureau_result.get("restricoes_financeiras", {})
                relacionamentos_bancarios = bureau_result.get(
                    "relacionamentos_bancarios", []
                )
                dados_eleitorais = bureau_result.get("dados_eleitorais")
                if bureau_result.get("nao_me_perturbe_consultado"):
                    bloqueios_nmp = bureau_result.get("bloqueios_nao_perturbe", [])

                sections.append(
                    {
                        "id": "cadastral_data",
                        "title": "Dados Cadastrais do Provedor",
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
                            {
                                "label": "Nome do Pai",
                                "value": cad.get("nome_pai") or "Não informado",
                            },
                            {"label": "Sexo", "value": genero or "Não informado"},
                            {
                                "label": "Estado Civil",
                                "value": cad.get("estado_civil") or "Não informado",
                            },
                            {
                                "label": "Instrução",
                                "value": cad.get("instrucao") or "Não informada",
                            },
                            {"label": "Situação Cadastral", "value": situacao_cpf},
                            {
                                "label": "Origem do CPF",
                                "value": cad.get("origem_cpf") or "Não informada",
                            },
                        ],
                        "items": [],
                    }
                )
                if enderecos:
                    address = enderecos[0]
                    sections.append(
                        {
                            "id": "address_data",
                            "title": "Endereço do Titular",
                            "description": "Endereço mais relevante localizado para o CPF",
                            "status": "available",
                            "summary": "Endereço cadastral localizado.",
                            "fields": [
                                {
                                    "label": "Logradouro",
                                    "value": address.get("logradouro") or "Não informado",
                                },
                                {
                                    "label": "Número",
                                    "value": address.get("numero") or "Não informado",
                                },
                                {
                                    "label": "Complemento",
                                    "value": address.get("complemento") or "Não informado",
                                },
                                {
                                    "label": "Bairro",
                                    "value": address.get("bairro") or "Não informado",
                                },
                                {
                                    "label": "Município",
                                    "value": address.get("municipio") or "Não informado",
                                },
                                {"label": "UF", "value": address.get("uf") or "Não informada"},
                                {"label": "CEP", "value": address.get("cep") or "Não informado"},
                            ],
                            "items": enderecos,
                        }
                    )
                if dados_eleitorais:
                    sections.append(
                        {
                            "id": "electoral_data",
                            "title": "Dados Eleitorais",
                            "description": "Situação e local de votação informados pelo provedor",
                            "status": "available",
                            "summary": "Registro eleitoral localizado.",
                            "fields": [
                                {
                                    "label": "Título de Eleitor",
                                    "value": dados_eleitorais.get("titulo_eleitor")
                                    or "Não informado",
                                },
                                {
                                    "label": "Status do Título",
                                    "value": dados_eleitorais.get("status_titulo")
                                    or "Não informado",
                                },
                                {
                                    "label": "Local de Votação",
                                    "value": dados_eleitorais.get("local_votacao")
                                    or "Não informado",
                                },
                                {
                                    "label": "Zona",
                                    "value": dados_eleitorais.get("zona") or "Não informada",
                                },
                                {
                                    "label": "Seção",
                                    "value": dados_eleitorais.get("secao") or "Não informada",
                                },
                            ],
                            "items": [],
                        }
                    )
                if beneficios_sociais:
                    sections.append(
                        {
                            "id": "social_benefits",
                            "title": "Benefícios Sociais e Previdenciários",
                            "description": (
                                "Programas, pagamentos e benefícios vinculados ao titular"
                            ),
                            "status": "available",
                            "summary": f"{len(beneficios_sociais)} benefício(s) localizado(s).",
                            "fields": [
                                {
                                    "label": item.get("programa") or "Benefício",
                                    "value": str(item.get("status") or "Status não informado"),
                                }
                                for item in beneficios_sociais[:10]
                            ],
                            "items": beneficios_sociais,
                        }
                    )
                if restricoes_financeiras:
                    sections.append(
                        {
                            "id": "financial_restrictions",
                            "title": "Pendências e Restrições Financeiras",
                            "description": (
                                "Indicadores financeiros observados no provedor contratado"
                            ),
                            "status": "available",
                            "summary": (
                                "Há indicador de pendência financeira."
                                if restricoes_financeiras.get("possui_pendencias") is True
                                else "Nenhuma pendência atual foi indicada."
                                if restricoes_financeiras.get("possui_pendencias") is False
                                else "Situação financeira sem confirmação conclusiva."
                            ),
                            "fields": [
                                {
                                    "label": "Pendências Financeiras",
                                    "value": (
                                        "Sim"
                                        if restricoes_financeiras.get("possui_pendencias")
                                        is True
                                        else "Não"
                                        if restricoes_financeiras.get("possui_pendencias")
                                        is False
                                        else "Não informado"
                                    ),
                                },
                                {
                                    "label": "Protestos",
                                    "value": (
                                        restricoes_financeiras.get("protestos")
                                        if restricoes_financeiras.get("protestos") is not None
                                        else "Não informado pelo plano contratado"
                                    ),
                                },
                                {
                                    "label": "Cheques sem Fundo",
                                    "value": (
                                        restricoes_financeiras.get("cheques_sem_fundo")
                                        if restricoes_financeiras.get("cheques_sem_fundo")
                                        is not None
                                        else "Não informado pelo plano contratado"
                                    ),
                                },
                                {
                                    "label": "Score de Risco",
                                    "value": restricoes_financeiras.get("score_risco")
                                    or "Não informado",
                                },
                            ],
                            "items": [],
                        }
                    )
                if relacionamentos_bancarios:
                    sections.append(
                        {
                            "id": "bank_relationships",
                            "title": "Instituições Bancárias Localizadas",
                            "description": "Vínculos bancários observados com contexto e origem",
                            "status": "available",
                            "summary": (
                                f"{len(relacionamentos_bancarios)} instituição(ões) "
                                "localizada(s)."
                            ),
                            "fields": [
                                {
                                    "label": item.get("instituicao") or "Instituição bancária",
                                    "value": "Destino de restituição de IR"
                                    if item.get("tipo_vinculo") == "DESTINO_RESTITUICAO_IR"
                                    else str(item.get("tipo_vinculo") or "Vínculo informado"),
                                }
                                for item in relacionamentos_bancarios[:10]
                            ],
                            "items": relacionamentos_bancarios,
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
            logger.error(
                "Erro ao enriquecer CPF %s [%s] na BigDataCorp: %s",
                mask_cpf(cleaned_digits),
                correlation_tag(cleaned_digits),
                exc.__class__.__name__,
            )
            sections.append(
                {
                    "id": "cadastral_data",
                    "title": "Dados Cadastrais do Titular",
                    "description": "Identificação civil e canais associados ao titular",
                    "status": "unavailable",
                    "summary": "Os dados complementares estão temporariamente indisponíveis.",
                    "fields": [{"label": "CPF validado", "value": formatted_cpf_str}],
                    "items": [],
                }
            )
    else:
        # Bureau NÃO configurado
        sections.append(
            {
                "id": "cadastral_data",
                "title": "Dados cadastrais complementares",
                "description": "Identificação civil, nome e histórico de contatos",
                "status": "empty",
                "summary": "Nenhum dado complementar foi retornado nesta consulta.",
                "fields": [
                    {"label": "CPF validado", "value": formatted_cpf_str},
                ],
                "items": [],
            }
        )

    # 4. Inteligência governamental completa, incluindo benefícios e rendimentos públicos.
    if "government_intelligence" in applied_caps:
        portal_adapter = PortalTransparenciaAdapter(client=http_client)
        if portal_adapter.is_configured():
            try:
                government_intelligence = portal_adapter.enrich_person(cleaned_digits)
                portal_name = str(
                    government_intelligence.get("profile", {}).get("name") or ""
                ).strip()
                if not nome_pessoa and portal_name:
                    nome_pessoa = portal_name
                pep = government_intelligence.get("pep", {})
                risk = government_intelligence.get("government_risk", {})
                public_sector = government_intelligence.get("public_sector", {})
                portal_social = government_intelligence.get("social_benefits", {})
                professional_records = sum(
                    len(public_sector.get(key) or [])
                    for key in (
                        "server_records",
                        "permission_records",
                        "contracts",
                        "travel_records",
                        "card_records",
                        "resources_received",
                        "expense_documents",
                        "remuneration_records",
                        "pension_records",
                    )
                )
                benefit_records = len(portal_social.get("records") or [])
                has_government_data = bool(
                    government_intelligence.get("indexed_in_portal")
                    or pep.get("has_matches")
                    or risk.get("has_matches")
                    or professional_records
                )
                sections.append(
                    {
                        "id": "government_intelligence",
                        "title": "Inteligência Governamental e Social",
                        "description": (
                            "PEP, sanções, vínculos públicos, benefícios, remunerações e pensões"
                        ),
                        "status": "available" if has_government_data else "empty",
                        "summary": (
                            "Vínculos profissionais governamentais localizados."
                            if has_government_data
                            else "Nenhum vínculo profissional localizado nas fontes acionadas."
                        ),
                        "fields": [
                            {
                                "label": "Indexado no Portal",
                                "value": (
                                    "Sim"
                                    if government_intelligence.get("indexed_in_portal")
                                    else "Não"
                                ),
                            },
                            {"label": "Registros PEP", "value": str(pep.get("match_count", 0))},
                            {
                                "label": "Ocorrências em sanções",
                                "value": str(risk.get("match_count", 0)),
                            },
                            {
                                "label": "Registros públicos",
                                "value": str(professional_records),
                            },
                            {
                                "label": "Benefícios sociais",
                                "value": str(benefit_records),
                            },
                            {
                                "label": "Remunerações",
                                "value": str(len(public_sector.get("remuneration_records") or [])),
                            },
                            {
                                "label": "Pensões",
                                "value": str(len(public_sector.get("pension_records") or [])),
                            },
                        ],
                        "items": (portal_social.get("records") or [])
                        + (public_sector.get("remuneration_records") or []),
                    }
                )
            except ProviderError as exc:
                logger.warning(
                    "Falha no Portal da Transparência para CPF %s [%s]: %s",
                    mask_cpf(cleaned_digits),
                    correlation_tag(cleaned_digits),
                    exc.__class__.__name__,
                )
                sections.append(
                    {
                        "id": "government_intelligence",
                        "title": "Inteligência Governamental Profissional",
                        "description": "Consulta a fontes oficiais por CPF",
                        "status": "unavailable",
                        "summary": "Os registros públicos estão temporariamente indisponíveis.",
                        "fields": [],
                        "items": [],
                    }
                )
        else:
            sections.append(
                {
                    "id": "government_intelligence",
                    "title": "Inteligência Governamental Profissional",
                    "description": "Consulta a fontes oficiais por CPF",
                    "status": "empty",
                    "summary": "Nenhum registro público foi retornado nesta consulta.",
                    "fields": [],
                    "items": [],
                }
            )

    # 5. Camada 1: Filtro de Perda (Óbito & RFB)
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
            "status": "available" if filtro_perda["status"] != "INCONCLUSIVO" else "unavailable",
            "summary": (
                filtro_perda["motivo_expurgo"]
                if not filtro_perda["elegivel_consignado"]
                else "Situação regular explicitamente informada pelo provedor cadastral."
            ),
            "fields": [
                {"label": "Status Cadastral", "value": filtro_perda["badge_texto"]},
                {
                    "label": "Indicador de Óbito",
                    "value": (
                        "Confirmado (falecido)"
                        if filtro_perda["is_deceased"] is True
                        else (
                            "Ausência de óbito informada pelo provedor"
                            if filtro_perda["is_deceased"] is False
                            else "Não verificado"
                        )
                    ),
                },
                {"label": "Data do Óbito", "value": filtro_perda["death_date"] or "N/A"},
                {"label": "Situação Receita Federal", "value": situacao_cpf},
                {
                    "label": "Elegibilidade Consignado",
                    "value": (
                        "Pré-requisito cadastral atendido"
                        if filtro_perda["elegivel_consignado"]
                        else (
                            "Não verificado"
                            if filtro_perda["status"] == "INCONCLUSIVO"
                            else "Inapto / Expurgado"
                        )
                    ),
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
            and bool(selected_ben.get("elegivel_consignado", False)),
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
            and selected_vinc.get("ativo") is True,
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
            "elegivel": False,
            "vinculoPrincipal": "Renda Estimada pelo Bureau",
            "numeroBeneficio": "N/A",
            "especieCodigo": "RENDA_ESTIMADA",
            "especieDescricao": f"Faixa de Renda: {renda_data.get('faixa_renda') or 'Padrão'}",
            "categoriaElegibilidade": "ESTIMATIVA_NAO_ELEGIVEL",
            "alerta": (
                "Renda estimada não comprova benefício, vínculo, margem disponível ou averbação."
            ),
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
            "alerta": "Dados insuficientes para cálculo de margem consignável.",
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
                "summary": "Nenhum benefício INSS ou salário foi localizado nesta consulta.",
                "fields": [
                    {
                        "label": "Situação de Vínculo",
                        "value": "Sem registros previdenciários disponíveis",
                    },
                    {"label": "Elegibilidade", "value": "Não determinada"},
                ],
                "items": [],
            }
        )

    # 6. Camada 3: Filtro de Não Me Perturbe (Anatel/Febraban)
    total_bloqueados_nmp = len(bloqueios_nmp) if bloqueios_nmp is not None else 0
    nmp_consultado = bloqueios_nmp is not None
    sections.append(
        {
            "id": "nao_me_perturbe",
            "title": "Camada 3: Higienização de Não Me Perturbe (Anatel / Febraban)",
            "description": "Proteção jurídica contra multas de telemarketing ativo em consignado",
            "status": "available" if nmp_consultado else "unavailable",
            "summary": (
                f"{total_bloqueados_nmp} registro(s) de bloqueio no Não Me Perturbe."
                if total_bloqueados_nmp > 0
                else (
                    "Nenhum bloqueio foi localizado na fonte consultada."
                    if nmp_consultado
                    else "A fonte de bloqueio não foi consultada; o resultado é inconclusivo."
                )
            ),
            "fields": [
                {
                    "label": "Conformidade Regulatória",
                    "value": "Anatel & Febraban (Sistema Não Me Perturbe)",
                },
                {"label": "Telefones Bloqueados", "value": str(total_bloqueados_nmp)},
                {
                    "label": "Risco de Multa (Procon)",
                    "value": (
                        "Alto para ligações de oferta"
                        if total_bloqueados_nmp > 0
                        else ("Não identificado" if nmp_consultado else "Desconhecido")
                    ),
                },
                {
                    "label": "Diretriz Operacional",
                    "value": (
                        "Não realizar oferta por telefone sem base legal e consentimento aplicáveis"
                        if total_bloqueados_nmp > 0
                        else (
                            "Aplicar demais regras de consentimento antes do contato"
                            if nmp_consultado
                            else "Bloquear discagem automática até concluir a consulta"
                        )
                    ),
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
                        "whatsappDisponivel": None,
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
            nmp_status = item["naoMePerturbe"]["status_consulta"]
            nmp_desc = {
                "BLOQUEADO": "Bloqueio localizado",
                "NAO_LOCALIZADO_NA_FONTE": "Bloqueio não localizado",
            }.get(nmp_status, "Conformidade não verificada")
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

    # Seção de verificação técnica de WhatsApp
    if whatsapp_garantido:
        sections.append(
            {
                "id": "whatsapp_verified",
                "title": "Conta WhatsApp tecnicamente confirmada",
                "description": "Verificação técnica ativa realizada na rede do WhatsApp",
                "status": "available",
                "summary": f"Conta WhatsApp confirmada para {whatsapp_garantido['numero']}.",
                "fields": [
                    {"label": "Número WhatsApp", "value": whatsapp_garantido["numero"]},
                    {"label": "Conta WhatsApp", "value": whatsapp_garantido["tipoConta"]},
                    {"label": "Link de Conversa Direta", "value": whatsapp_garantido["linkDireto"]},
                ],
                "items": [],
            }
        )
    elif not probe_configured:
        sections.append(
            {
                "id": "whatsapp_verified",
                "title": "Verificação de WhatsApp",
                "description": "Confirmação técnica de disponibilidade do canal",
                "status": "empty",
                "summary": "Nenhum número com WhatsApp confirmado foi retornado nesta consulta.",
                "fields": [
                    {
                        "label": "Telefones identificados",
                        "value": str(len(telefones_analisados)),
                    },
                ],
                "items": [],
            }
        )
    else:
        sections.append(
            {
                "id": "whatsapp_verified",
                "title": "Verificação técnica de WhatsApp",
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
            status_desc = (
                "WhatsApp confirmado"
                if t["whatsappDisponivel"] is True
                else (
                    "Sem conta WhatsApp no probe"
                    if t["whatsappDisponivel"] is False
                    else "WhatsApp não verificado"
                )
            )
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
    if nome_pessoa:
        try:
            with transaction.atomic():
                person_record = create_person(
                    tenant=tenant,
                    full_name=nome_pessoa,
                    cpf=cleaned_digits,
                    hash_key=settings.DATA_HASH_KEY,
                )
                if government_intelligence is not None:
                    person_record.government_profile = government_intelligence
                    person_record.government_profile_observed_at = timezone.now()
                    person_record.save(
                        update_fields=(
                            "government_profile",
                            "government_profile_observed_at",
                            "updated_at",
                        )
                    )
                if bureau_result is not None:
                    person_record.enrichment_profile = bureau_result
                    person_record.enrichment_profile_observed_at = timezone.now()
                    person_record.save(
                        update_fields=(
                            "enrichment_profile",
                            "enrichment_profile_observed_at",
                            "updated_at",
                        )
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
                "Falha ao persistir Person para CPF %s [%s]: %s",
                mask_cpf(cleaned_digits),
                correlation_tag(cleaned_digits),
                exc.__class__.__name__,
            )

    # 9. Cobertura e Resposta
    total_fields = sum(len(sec["fields"]) for sec in sections)
    coverage = {
        "requested": len(applied_caps),
        "available": sum(1 for sec in sections if sec["status"] == "available"),
        "fieldCount": total_fields,
        "recordCount": len(telefones_analisados),
    }

    # Resumo consolidado. O CPF formatado é devolvido ao chamador, mas nunca vai para logs.
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
        "id": str(person_record.entity.id) if person_record else "",
        "name": nome_pessoa or "Pessoa não identificada pelo provedor",
        "cpf": formatted_cpf_str,
        "birthDate": str(data_nascimento)[:10] if data_nascimento else None,
        "age": idade,
        "motherName": nome_mae or None,
        "fatherName": (
            bureau_result.get("dados_cadastrais", {}).get("nome_pai")
            if bureau_result
            else None
        ),
        "gender": genero or None,
        "maritalStatus": (
            bureau_result.get("dados_cadastrais", {}).get("estado_civil")
            if bureau_result
            else None
        ),
        "education": (
            bureau_result.get("dados_cadastrais", {}).get("instrucao")
            if bureau_result
            else None
        ),
        "taxStatus": situacao_cpf,
        "taxIdOrigin": (
            bureau_result.get("dados_cadastrais", {}).get("origem_cpf")
            if bureau_result
            else None
        ),
        "isDeceased": filtro_perda["is_deceased"],
        "deathDate": filtro_perda["death_date"],
        "phone": primary_phone,
        "whatsapp": whatsapp_garantido["numero"] if whatsapp_garantido else None,
        "hasWhatsApp": bool(whatsapp_garantido),
        "phones": [item.get("numero") for item in telefones_analisados[:3]],
        "address": enderecos[0] if enderecos else None,
        "electoral": dados_eleitorais,
        "financialRestrictions": restricoes_financeiras,
        "bankRelationships": relacionamentos_bancarios,
        "socialBenefits": beneficios_sociais,
        "inssBenefits": beneficios_inss,
        "observedAt": timezone.now().isoformat(),
    }

    # Regra estrita de cobrança de créditos:
    # 1. Se expurgado por óbito, NENHUM crédito é cobrado (costCredits = 0)
    # 2. Se nenhum dado útil localizado, costCredits = 0
    # 3. Se lead válido e vivo com dados entregues, costCredits = 1
    if filtro_perda["status"] == "EXPURGADO_OBITO":
        cost_credits = 0
    elif not (bureau_identity_found or whatsapp_garantido or mailing_top3):
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
        logger.warning(
            "Falha ao construir payload canônico para CPF %s [%s]: %s",
            mask_cpf(cleaned_digits),
            correlation_tag(cleaned_digits),
            exc.__class__.__name__,
        )

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
        "governmentIntelligence": (
            public_person_portal_profile(government_intelligence)
            if government_intelligence
            else None
        ),
        "canonical": canonical_payload,
    }
