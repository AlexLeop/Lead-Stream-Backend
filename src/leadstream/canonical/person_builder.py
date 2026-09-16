from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from leadstream.canonical.contracts import CanonicalPersonPayload
from leadstream.common.redaction import correlation_tag, mask_cpf
from leadstream.entities.models import ContactPoint
from leadstream.entities.services import create_contact_point, create_person
from leadstream.intelligence.consignado import (
    calculate_margem_consignavel,
    evaluate_filtro_perda,
    evaluate_nao_me_perturbe,
    get_inss_species_info,
    rank_mailing_telefones,
)
from leadstream.intelligence.cpf_rfb import (
    clean_cpf_digits,
    validate_cpf_with_details,
)
from leadstream.providers.adapters.bigdatacorp_person import BigDataCorpPersonAdapter
from leadstream.tenancy.models import Tenant
from leadstream.validation.phone_check import get_phone_operator_hint
from leadstream.validation.whatsapp_probe import (
    format_display_phone_br,
    format_e164_whatsapp_br,
    is_whatsapp_probe_configured,
    verify_whatsapp_active,
)

logger = logging.getLogger(__name__)


class CanonicalPersonBuilder:
    """Construtor canônico unificado para Pessoa Física (PF / CPF).

    Executa higienização, enriquecimento e conformidade regulatória (INSS, SIAPE, WhatsApp, NMP).
    Produz um CanonicalPersonPayload (v2.4.0) estritamente validado.
    """

    def __init__(self, tenant: Tenant) -> None:
        self.tenant = tenant

    def build(
        self,
        query: str | dict[str, Any],
        bureau_data: dict[str, Any] | None = None,
        http_client: httpx.Client | None = None,
    ) -> dict[str, Any]:
        raw_cpf = query if isinstance(query, str) else query.get("cpf") or query.get("query") or ""
        val = validate_cpf_with_details(raw_cpf)
        digits = val["cpf_numerico"]
        formatted_cpf = val["cpf_formatado"]
        is_valid_dv = val["valido"]
        regiao_rfb = val.get("regiao_fiscal")

        # 1. Consulta ao Bureau (se não foi injetado previamente e o CPF for válido)
        bureau_result: dict[str, Any] = bureau_data or {}
        adapter = BigDataCorpPersonAdapter(client=http_client)
        if not bureau_result and is_valid_dv and adapter.is_configured():
            try:
                bureau_result = adapter.enrich_cpf(digits)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Falha na consulta ao bureau BigDataCorp para CPF %s [%s]: %s",
                    mask_cpf(digits),
                    correlation_tag(digits),
                    exc.__class__.__name__,
                )
                bureau_result = {}

        dados_cadastrais = bureau_result.get("dados_cadastrais") or {}
        telefones_raw = bureau_result.get("telefones") or []
        beneficios_inss_raw = bureau_result.get("beneficios_inss") or []
        vinculos_siape_raw = (
            bureau_result.get("vinculos_siape")
            or bureau_result.get("vinculos_empregaticios")
            or []
        )
        bloqueios_nmp_raw = (
            bureau_result.get("bloqueios_nao_perturbe", [])
            if bureau_result.get("nao_me_perturbe_consultado")
            or "bloqueios_nao_perturbe" in bureau_result
            else None
        )

        # 2. Dados Cadastrais & Filtro de Perda (Óbito)
        nome = dados_cadastrais.get("nome") or None
        data_nasc = dados_cadastrais.get("data_nascimento")
        idade = dados_cadastrais.get("idade")
        genero = dados_cadastrais.get("genero")
        nome_mae = dados_cadastrais.get("nome_mae")
        situacao_rfb = (
            dados_cadastrais.get("situacao_cpf")
            or dados_cadastrais.get("situacao_cadastral")
            or "DESCONHECIDA"
        )
        is_deceased = dados_cadastrais.get("is_deceased")
        death_date = dados_cadastrais.get("death_date")

        filtro_perda = evaluate_filtro_perda(
            is_deceased=is_deceased,
            death_date=death_date,
            tax_status=situacao_rfb,
        )

        # 3. Inteligência Previdenciária & Margens (Lei 14.431/2022)
        beneficios_formatados: list[dict[str, Any]] = []
        salario_base_inss = 0.0
        nb_principal: str | None = None

        for b in beneficios_inss_raw:
            cod_esp = str(b.get("especie_codigo") or "")
            sp_info = get_inss_species_info(cod_esp)
            val_ben = float(b.get("valor_beneficio") or 0.0)
            nb = str(b.get("numero_beneficio") or "")
            status_b = str(b.get("status") or "DESCONHECIDO")
            bloq_loans = b.get("bloqueado_para_emprestimo")

            beneficios_formatados.append(
                {
                    "numero_beneficio": nb,
                    "especie_codigo": cod_esp,
                    "especie_descricao": b.get("especie_descricao") or sp_info["descricao"],
                    "categoria_aptidao": sp_info["categoria"],
                    "status_beneficio": status_b,
                    "data_concessao": b.get("data_concessao"),
                    "data_cessacao": b.get("data_cessacao"),
                    "valor_beneficio_bruto": val_ben,
                    "valor_beneficio_liquido": b.get("valor_beneficio_liquido"),
                    "descontos_obrigatorios": b.get("descontos_obrigatorios"),
                    "bloqueado_para_emprestimo": bloq_loans,
                    "alerta_elegibilidade": sp_info["alerta"],
                    "banco_pagador": b.get("banco_pagador") or {},
                }
            )
            if (
                sp_info["elegivel"]
                and bloq_loans is False
                and status_b.upper() == "ATIVO"
                and val_ben > salario_base_inss
            ):
                salario_base_inss = val_ben
                nb_principal = nb

        consignado_inss = {
            "possui_beneficio_inss": bool(beneficios_formatados),
            "quantidade_beneficios": len(beneficios_formatados),
            "beneficios": beneficios_formatados,
        }

        # SIAPE
        vinculos_siape: list[dict[str, Any]] = []
        salario_base_siape = 0.0
        for v in vinculos_siape_raw:
            sal = float(v.get("salario") or 0.0)
            if sal > salario_base_siape:
                salario_base_siape = sal
            vinculos_siape.append(
                {
                    "matricula": str(v.get("matricula") or ""),
                    "orgao": str(v.get("orgao_siape") or v.get("orgao") or ""),
                    "uorg": v.get("uorg"),
                    "cargo": v.get("cargo"),
                    "regime_juridico": v.get("regime_juridico"),
                    "situacao_funcional": (
                        "ATIVO"
                        if v.get("ativo") is True
                        else ("INATIVO" if v.get("ativo") is False else "DESCONHECIDA")
                    ),
                    "uf_lotacao": v.get("uf"),
                    "rendimento_bruto_declarado": sal,
                }
            )

        consignado_siape = {
            "possui_vinculo_publico": bool(vinculos_siape),
            "quantidade_vinculos": len(vinculos_siape),
            "vinculos": vinculos_siape,
        }

        # Cálculo da Margem Consignável (INSS prioritário, ou SIAPE)
        salario_base_calculo = salario_base_inss or salario_base_siape
        vinculo_base = "INSS" if salario_base_inss else ("SIAPE" if salario_base_siape else None)
        margem_calculada = calculate_margem_consignavel(salario_base_calculo)

        margem_payload = {
            "base_legal": "LEI_FEDERAL_14431_2022",
            "elegivel": margem_calculada["elegivel"],
            "vinculo_base": vinculo_base,
            "numero_beneficio_base": nb_principal,
            "salario_base_calculo": salario_base_calculo,
            "margem_emprestimo_35": {
                "percentual": 35.0,
                "valor_mensal_permitido": margem_calculada["margem_emprestimo_35"],
            },
            "margem_rmc_cartao_5": {
                "percentual": 5.0,
                "valor_mensal_permitido": margem_calculada["margem_rmc_cartao_5"],
            },
            "margem_rcc_beneficio_5": {
                "percentual": 5.0,
                "valor_mensal_permitido": margem_calculada["margem_rcc_beneficio_5"],
            },
            "margem_total_45": {
                "percentual": 45.0,
                "valor_mensal_permitido": margem_calculada["margem_total_45"],
            },
        }

        # 4. Telefonia Higienizada & WhatsApp Probe & Não Me Perturbe
        telefones_higienizados: list[dict[str, Any]] = []
        candidatos_para_ranking: list[dict[str, Any]] = []
        telefones_consultados_nmp: list[dict[str, Any]] = []
        probe_ativo_resultado: dict[str, Any] | None = None
        gateway_probe_configurado = is_whatsapp_probe_configured()

        for t in telefones_raw:
            ddd = clean_cpf_digits(str(t.get("ddd") or t.get("AreaCode") or ""))
            numero = clean_cpf_digits(str(t.get("numero") or t.get("Number") or ""))
            if not numero:
                continue

            num_formatado = format_display_phone_br(f"{ddd}{numero}")
            num_e164 = format_e164_whatsapp_br(numero, ddd=ddd)
            is_cel = bool(t.get("is_celular") or (len(numero) == 9 and numero.startswith("9")))
            operadora = str(t.get("operadora") or get_phone_operator_hint(ddd, numero))
            score_rec = float(t.get("score") or 0.0)

            telefones_higienizados.append(
                {
                    "ddd": ddd,
                    "numero": numero,
                    "numero_formatado": num_formatado,
                    "numero_e164": num_e164,
                    "tipo_linha": "MOVEL_CELULAR" if is_cel else "FIXO_RESIDENCIAL",
                    "operadora": operadora,
                    "score_recencia": score_rec,
                    "indicador_atividade": str(t.get("recencia") or "DESCONHECIDA"),
                }
            )

            # Probe do WhatsApp (se configurado)
            tem_wa: bool | None = None
            tipo_conta = "DESCONHECIDA"
            foto_p = None
            jid_val = None

            if gateway_probe_configurado:
                probe_res = verify_whatsapp_active(f"{ddd}{numero}", client=http_client)
                if probe_res.get("sucesso") and probe_res.get("tem_whatsapp"):
                    tem_wa = True
                    tipo_conta = str(probe_res.get("tipo_conta") or "WHATSAPP_PESSOAL")
                    foto_p = probe_res.get("foto_perfil")
                    jid_val = probe_res.get("jid")

                    if not probe_ativo_resultado:
                        probe_ativo_resultado = {
                            "garantido": True,
                            "status": "VALIDADO_ATIVO",
                            "numero_formatado": num_formatado,
                            "numero_e164": num_e164,
                            "tipo_conta": tipo_conta,
                            "jid": jid_val,
                            "foto_perfil": foto_p,
                            "link_direto": f"https://wa.me/{num_e164.lstrip('+')}",
                            "verificado_em": timezone.now().isoformat(),
                        }

            # Avaliação de Não Me Perturbe
            nmp_eval = evaluate_nao_me_perturbe(f"{ddd}{numero}", block_records=bloqueios_nmp_raw)
            telefones_consultados_nmp.append(
                {
                    "numero": f"{ddd}{numero}",
                    "numero_formatado": num_formatado,
                    "inscrito_bloqueio": nmp_eval["inscrito_nao_me_perturbe"],
                    "entidade": nmp_eval.get("entidade", "NENHUMA"),
                    "data_bloqueio": nmp_eval.get("data_bloqueio"),
                    "motivo": nmp_eval.get("motivo"),
                    "status_consulta": nmp_eval["status_consulta"],
                    "seguro_discagem_fria": nmp_eval["seguro_para_discagem_fria"],
                    "risco_multa": nmp_eval["risco_multa"],
                    "badge_texto": nmp_eval["badge_texto"],
                }
            )

            candidatos_para_ranking.append(
                {
                    "ddd": ddd,
                    "numero": numero,
                    "is_celular": is_cel,
                    "operadora": operadora,
                    "score": score_rec,
                    "whatsappDisponivel": tem_wa,
                    "tipoConta": tipo_conta,
                }
            )

        # Ranking Top 3
        top3_ranqueado = rank_mailing_telefones(
            candidatos_para_ranking, block_records=bloqueios_nmp_raw
        )
        mailing_top3: list[dict[str, Any]] = []
        for idx, item_rank in enumerate(top3_ranqueado, 1):
            nmp_info = item_rank.get("naoMePerturbe") or {}
            mailing_top3.append(
                {
                    "ordem_prioridade": idx,
                    "numero_formatado": item_rank["numeroFormatado"],
                    "numero_raw": item_rank["numeroRaw"],
                    "numero_e164": item_rank["numeroE164"],
                    "ddd": item_rank["ddd"],
                    "operadora": item_rank["operadora"],
                    "whatsapp_disponivel": item_rank["whatsappDisponivel"],
                    "whatsapp_tipo_conta": item_rank.get("tipoConta", "NENHUMA"),
                    "link_whatsapp": item_rank.get("linkWhatsApp"),
                    "nao_me_perturbe_inscrito": nmp_info.get("inscrito_nao_me_perturbe"),
                    "seguro_para_discagem_fria": nmp_info.get(
                        "seguro_para_discagem_fria", False
                    ),
                    "risco_multa": nmp_info.get("risco_multa", "DESCONHECIDO"),
                    "score_assertividade": item_rank.get("scoreAssertividade", 0),
                    "recomendacao_canal": item_rank.get(
                        "recomendacao", "AGUARDAR_VALIDACAO_COMPLIANCE"
                    ),
                    "rotulo_canal": item_rank.get("rotuloCanal", ""),
                }
            )

        # WhatsApp Probe final payload
        whatsapp_probe_payload = {
            "gateway_configurado": gateway_probe_configurado,
            "provedor": getattr(settings, "WHATSAPP_PROBE_PROVIDER", "evolution")
            if gateway_probe_configurado
            else None,
            "resultado": probe_ativo_resultado
            or {
                "garantido": False,
                "status": "INDISPONIVEL" if not gateway_probe_configurado else "SEM_CONTA_WHATSAPP",
                "numero_formatado": None,
                "numero_e164": None,
                "tipo_conta": "NENHUMA",
                "jid": None,
                "foto_perfil": None,
                "link_direto": None,
                "verificado_em": timezone.now().isoformat(),
            },
        }

        # 5. Endereço e Indicadores Financeiros
        endereco_raw = dados_cadastrais.get("endereco") or {}
        address_payload: dict[str, Any] | None = None
        if (
            endereco_raw.get("logradouro")
            or endereco_raw.get("bairro")
            or endereco_raw.get("municipio")
        ):
            address_payload = {
                "logradouro": endereco_raw.get("logradouro"),
                "numero": endereco_raw.get("numero"),
                "complemento": endereco_raw.get("complemento"),
                "bairro": endereco_raw.get("bairro"),
                "municipio": endereco_raw.get("municipio"),
                "uf": endereco_raw.get("uf"),
                "cep": endereco_raw.get("cep"),
                "codigo_ibge": str(endereco_raw.get("codigo_ibge") or ""),
            }

        fontes_renda: list[str] = []
        if beneficios_formatados:
            fontes_renda.append("BENEFICIO_PREVIDENCIARIO_INSS")
        if vinculos_siape:
            fontes_renda.append("VINCULO_PUBLICO_SIAPE")

        renda_raw = bureau_result.get("renda") or {}
        renda_estimada = float(renda_raw.get("renda_estimada") or 0.0)
        if renda_estimada:
            fontes_renda.append("ESTIMATIVA_DO_PROVEDOR")

        # Política estrita de custo de créditos: 0 se CPF inválido ou se óbito; 1 se dados úteis
        if (
            not is_valid_dv
            or filtro_perda["status"] == "EXPURGADO_OBITO"
            or not (dados_cadastrais or telefones_raw)
        ):
            cost_credits = 0
        else:
            cost_credits = 1

        person_id = str(uuid.uuid4())
        raw_payload = {
            "_meta": {
                "schema_version": "2.4.0",
                "canon_id": f"canon_pf_{person_id}",
                "entity_type": "PERSON",
                "generated_at": timezone.now().isoformat(),
                "tenant_id": str(self.tenant.slug),
                "pipeline_run_id": f"run_person_{uuid.uuid4().hex}",
                "confidence_score_global": 0.7 if dados_cadastrais else 0.2,
                "provenance_method": "PROVEDOR_CADASTRAL_E_PROBE"
                if dados_cadastrais
                else "VALIDACAO_ESTRUTURAL_LOCAL",
            },
            "identification": {
                "person_id": person_id,
                "entity_type": "PERSON",
                "status": (
                    "OBSERVED"
                    if dados_cadastrais
                    else ("UNASSESSED" if is_valid_dv else "REJECTED")
                ),
                "lead_score": 0,
                "confidence_score": 0.7 if dados_cadastrais else 0.2,
                "cost_credits": cost_credits,
                "tags": [
                    "CPF_FORMATO_VALIDO" if is_valid_dv else "CPF_FORMATO_INVALIDO",
                    "INSS_OBSERVADO" if beneficios_formatados else "INSS_NAO_OBSERVADO",
                    "MARGEM_NAO_CONFIRMADA",
                    "WHATSAPP_CONFIRMADO"
                    if probe_ativo_resultado and probe_ativo_resultado.get("garantido")
                    else "WHATSAPP_PENDENTE",
                ],
            },
            "document_validation": {
                "cpf_formatado": formatted_cpf,
                "cpf_numerico": digits,
                "digitos_verificadores": val.get("digitos_verificadores_calculados", ""),
                "modulo_11_valido": is_valid_dv,
                "origem_validacao": "CALCULO_ESTRUTURAL_LOCAL_MODULO_11",
                "regiao_fiscal": regiao_rfb,
            },
            "cadastral_data": {
                "nome": nome,
                "cpf": formatted_cpf,
                "cpf_numerico": digits,
                "data_nascimento": data_nasc,
                "idade": idade,
                "genero": genero,
                "nome_mae": nome_mae,
                "nome_pai": dados_cadastrais.get("nome_pai"),
                "estado_civil": dados_cadastrais.get("estado_civil"),
                "instrucao": dados_cadastrais.get("instrucao"),
                "situacao_cadastral_rfb": situacao_rfb,
                "origem_cpf": dados_cadastrais.get("origem_cpf"),
                "data_situacao_cadastral": dados_cadastrais.get("data_situacao_cadastral"),
                "codigo_controle_rfb": dados_cadastrais.get("codigo_controle_rfb"),
            },
            "loss_prevention_filter": filtro_perda,
            "consignado_inss": consignado_inss,
            "consignado_siape_publico": consignado_siape,
            "margem_consignavel_calculada": margem_payload,
            "telefonia_higienizada": {
                "total_linhas_encontradas": len(telefones_higienizados),
                "telefones": telefones_higienizados,
            },
            "whatsapp_probe_tecnico": whatsapp_probe_payload,
            "nao_me_perturbe_anatel_febraban": {
                "fonte_reguladora": "ANATEL_FEBRABAN" if bloqueios_nmp_raw is not None else None,
                "consulta_executada": bloqueios_nmp_raw is not None,
                "telefones_consultados": telefones_consultados_nmp,
            },
            "mailing_qualificado_top3": mailing_top3,
            "address_cadastral": address_payload,
            "electoral_data": bureau_result.get("dados_eleitorais"),
            "social_benefits": bureau_result.get("beneficios_sociais", []),
            "financial_restrictions": bureau_result.get(
                "restricoes_financeiras", {}
            ),
            "bank_relationships": bureau_result.get(
                "relacionamentos_bancarios", []
            ),
            "education_history": bureau_result.get("escolaridade", {}).get(
                "historico", []
            ),
            "financial_indicators": {
                "renda_estimada_declarada": renda_estimada,
                "faixa_renda": "DE_5_A_10_SALARIOS_MINIMOS"
                if renda_estimada > 7000
                else (
                    "DE_2_A_5_SALARIOS_MINIMOS"
                    if renda_estimada > 3000
                    else "ATE_2_SALARIOS_MINIMOS"
                ),
                "fontes_renda_identificadas": fontes_renda,
            },
            "governance_and_lgpd": {
                "enquadramento_legal": "LEI_FEDERAL_13709_LGPD",
                "base_legal": "NAO_DOCUMENTADA",
                "finalidade": "NAO_DOCUMENTADA",
                "trilha_auditoria_hash": None,
                "data_consulta": timezone.now().isoformat(),
            },
        }

        # Validação estrita via Pydantic
        payload_model = CanonicalPersonPayload.model_validate(raw_payload)
        return payload_model.model_dump(mode="json")

    def build_and_save(
        self,
        query: str | dict[str, Any],
        bureau_data: dict[str, Any] | None = None,
        http_client: httpx.Client | None = None,
    ) -> dict[str, Any]:
        compiled = self.build(query, bureau_data=bureau_data, http_client=http_client)
        digits = compiled["document_validation"]["cpf_numerico"]
        name = compiled["cadastral_data"]["nome"]

        # Persistência da entidade Person e ContactPoints no tenant
        if compiled["document_validation"]["modulo_11_valido"] and name:
            try:
                with transaction.atomic():
                    person = create_person(
                        tenant=self.tenant,
                        cpf=digits,
                        full_name=name,
                        hash_key=settings.DATA_HASH_KEY,
                    )
                    # Salva WhatsApp se verificado
                    wa_res = compiled.get("whatsapp_probe_tecnico", {}).get("resultado") or {}
                    if wa_res.get("garantido") and wa_res.get("numero_e164"):
                        create_contact_point(
                            tenant=self.tenant,
                            owner=person.entity,
                            kind=ContactPoint.Kind.WHATSAPP,
                            value=wa_res["numero_e164"],
                            status=ContactPoint.Status.CONFIRMED,
                            capabilities={
                                "whatsapp": True,
                                "jid": wa_res.get("jid"),
                                "foto_perfil": wa_res.get("foto_perfil"),
                                "verified_at": wa_res.get("verificado_em"),
                            },
                        )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Falha ao salvar Person para CPF %s [%s]: %s",
                    mask_cpf(digits),
                    correlation_tag(digits),
                    exc.__class__.__name__,
                )

        return compiled
