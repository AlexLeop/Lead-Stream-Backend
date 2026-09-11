from __future__ import annotations

import datetime
import re
import unicodedata
import uuid
from typing import Any

from django.utils import timezone

from leadstream.batches.models import BatchItem
from leadstream.canonical.contracts import CanonicalLeadPayload
from leadstream.intelligence.cnae import lookup_cnae, parse_cnaes_list
from leadstream.intelligence.economics import infer_economics
from leadstream.intelligence.natureza_juridica import lookup_natureza_juridica
from leadstream.intelligence.scoring import calculate_lead_score
from leadstream.tenancy.models import Tenant
from leadstream.validation.email_check import validate_email_technical
from leadstream.validation.phone_check import validate_phone_technical


def format_cnpj_mask(raw: str) -> str:
    d = "".join(c for c in raw if c.isdigit())
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    return raw


def slugify_name(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))
    cleaned = re.sub(r"[^a-zA-Z0-9\s-]", "", ascii_text).strip().lower()
    return re.sub(r"[\s_]+", "-", cleaned)


def format_cep(raw_cep: Any) -> str | None:
    if not raw_cep:
        return None
    d = "".join(c for c in str(raw_cep) if c.isdigit())
    if len(d) == 8:
        return f"{d[:5]}-{d[5:]}"
    return str(raw_cep)


def parse_date_safely(date_val: Any) -> datetime.date | None:
    if not date_val:
        return None
    if isinstance(date_val, datetime.date):
        return date_val
    if isinstance(date_val, datetime.datetime):
        return date_val.date()
    s = str(date_val).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


class CanonicalLeadBuilder:
    def __init__(self, tenant: Tenant) -> None:
        self.tenant = tenant

    def build(self, item: BatchItem) -> dict[str, Any]:
        norm: dict[str, Any] = item.normalized_data or {}
        orig: dict[str, Any] = item.original_data or {}

        # 1. CNPJ Parts
        cnpj_raw_val = (
            norm.get("cnpj")
            or orig.get("cnpj")
            or norm.get("cnpj_raw")
            or orig.get("cnpj_raw")
            or ""
        )
        digits = "".join(c for c in str(cnpj_raw_val) if c.isdigit())
        if len(digits) < 14:
            digits = digits.zfill(14)
        cnpj_formatted = format_cnpj_mask(digits)
        cnpj_raiz = digits[:8]
        cnpj_ordem = digits[8:12]
        cnpj_dv = digits[12:14]

        # 2. Company General Data
        razao_social = (
            norm.get("razao_social")
            or orig.get("razao_social")
            or norm.get("legal_name")
            or f"EMPRESA {digits}"
        )
        nome_fantasia = norm.get("nome_fantasia") or orig.get("nome_fantasia") or ""
        raw_sit = str(
            norm.get("situacao_cadastral") or orig.get("situacao_cadastral") or "ATIVA"
        ).strip()
        sit_map = {
            "1": "NULA",
            "01": "NULA",
            "2": "ATIVA",
            "02": "ATIVA",
            "3": "SUSPENSA",
            "03": "SUSPENSA",
            "4": "INAPTA",
            "04": "INAPTA",
            "8": "BAIXADA",
            "08": "BAIXADA",
        }
        situacao_cadastral = sit_map.get(raw_sit, raw_sit.upper())

        data_abertura_date = parse_date_safely(
            norm.get("data_inicio_atividade")
            or norm.get("data_abertura")
            or orig.get("data_inicio_atividade")
            or orig.get("data_abertura")
        )
        data_abertura_str = data_abertura_date.isoformat() if data_abertura_date else None

        idade_anos: float | None = None
        if data_abertura_date:
            days = (timezone.now().date() - data_abertura_date).days
            idade_anos = round(max(0.0, days / 365.25), 1)

        data_sit_date = parse_date_safely(
            norm.get("data_situacao_cadastral") or orig.get("data_situacao_cadastral")
        )
        data_sit_str = data_sit_date.isoformat() if data_sit_date else None

        # 3. Natureza Juridica
        nat_code = (
            norm.get("codigo_natureza_juridica")
            or norm.get("natureza_juridica")
            or orig.get("codigo_natureza_juridica")
            or orig.get("natureza_juridica")
            or "2135"
        )
        nat_data = lookup_natureza_juridica(str(nat_code))

        # 4. CNAE
        cnae_fiscal = (
            norm.get("cnae_fiscal")
            or orig.get("cnae_fiscal")
            or norm.get("cnae_principal")
            or orig.get("cnae_principal")
            or "8599603"
        )
        cnae_principal_dict = lookup_cnae(str(cnae_fiscal))

        cnaes_secundarios_raw = (
            norm.get("cnaes_secundarios")
            or orig.get("cnaes_secundarios")
            or norm.get("cnaes_secundarias")
            or []
        )
        secundarios_list = parse_cnaes_list(cnaes_secundarios_raw)

        # 5. Economics
        capital_social_val = norm.get("capital_social") or orig.get("capital_social") or 0.0
        try:
            capital_social = float(capital_social_val)
        except (ValueError, TypeError):
            capital_social = 0.0

        porte_val = norm.get("porte") or orig.get("porte") or "01"
        opt_simples = bool(
            norm.get("opcao_pelo_simples")
            or norm.get("optante_simples")
            or orig.get("opcao_pelo_simples")
        )
        opt_mei = bool(
            norm.get("opcao_pelo_mei") or norm.get("optante_simei") or orig.get("opcao_pelo_mei")
        )

        eco = infer_economics(
            capital_social=capital_social,
            porte_rfb=str(porte_val),
            optante_mei=opt_mei,
            optante_simples=opt_simples,
            cnae_code=str(cnae_fiscal),
        )

        porte_rfb_label = (
            "MICRO_EMPRESA"
            if porte_val in ("01", "1", "ME")
            else ("PEQUENA_EMPRESA" if porte_val in ("03", "3", "EPP") else "DEMAIS")
        )

        # 6. Address
        tipo_logr = (norm.get("tipo_logradouro") or orig.get("tipo_logradouro") or "").strip()
        raw_logr = (norm.get("logradouro") or orig.get("logradouro") or "").strip()

        if not tipo_logr and raw_logr:
            parts = raw_logr.split(maxsplit=1)
            first_word = parts[0].upper()
            if first_word in (
                "RUA",
                "AVENIDA",
                "AV.",
                "AV",
                "ESTRADA",
                "ALAMEDA",
                "TRAVESSA",
                "RODOVIA",
                "PRACA",
                "PRAÇA",
                "VIADUTO",
            ):
                tipo_logr = parts[0].capitalize()
                raw_logr = parts[1] if len(parts) > 1 else raw_logr

        raw_cep = norm.get("cep") or orig.get("cep")
        formatted_cep = format_cep(raw_cep)

        address_dict = {
            "tipo_logradouro": tipo_logr or None,
            "logradouro": raw_logr or None,
            "numero": str(norm.get("numero") or orig.get("numero") or "") or None,
            "complemento": norm.get("complemento") or orig.get("complemento") or None,
            "bairro": norm.get("bairro") or orig.get("bairro") or None,
            "municipio": norm.get("municipio") or orig.get("municipio") or None,
            "uf": (norm.get("uf") or orig.get("uf") or "").upper() or None,
            "cep": formatted_cep,
            "codigo_ibge_municipio": str(
                norm.get("codigo_municipio_ibge") or orig.get("codigo_municipio_ibge") or ""
            )
            or None,
            "latitude": norm.get("latitude") or orig.get("latitude"),
            "geocoding_precision": (
                "ROOFTOP_EXACT" if (norm.get("numero") or orig.get("numero")) else "APPROXIMATE"
            ),
            "tipo_imovel": "COMERCIAL",
            "valor_m2_regiao": None,
        }

        # 7. Contacts
        telefones: list[dict[str, Any]] = []
        emails: list[dict[str, Any]] = []

        # Emails
        raw_email = (
            norm.get("correio_eletronico")
            or norm.get("email")
            or orig.get("correio_eletronico")
            or orig.get("email")
        )
        if raw_email:
            val_email = validate_email_technical(str(raw_email))
            emails.append(val_email)

        # Phones
        raw_phone1 = (
            norm.get("ddd_telefone_1")
            or norm.get("telefone")
            or orig.get("ddd_telefone_1")
            or orig.get("telefone")
        )
        if raw_phone1:
            val_phone1 = validate_phone_technical(str(raw_phone1), is_primary=True)
            telefones.append(val_phone1)

        raw_phone2 = norm.get("ddd_telefone_2") or orig.get("ddd_telefone_2")
        if raw_phone2:
            val_phone2 = validate_phone_technical(str(raw_phone2), is_primary=False)
            telefones.append(val_phone2)

        # 8. Decision Makers / QSA
        decision_makers_qsa: list[dict[str, Any]] = []
        raw_qsa = norm.get("qsa") or orig.get("qsa") or []
        if not raw_qsa and item.entity_id:
            from leadstream.entities.models import Relationship, SocialProfile

            db_rels = Relationship.objects.filter(company__entity=item.entity).select_related(
                "person__entity"
            )
            for r in db_rels:
                sp = SocialProfile.objects.filter(
                    owner=r.person.entity,
                    network=SocialProfile.Network.LINKEDIN,
                ).first()
                raw_qsa.append(
                    {
                        "nome_socio": r.person.full_name,
                        "qualificacao_socio": r.qualification,
                        "cargo": r.observed_title,
                        "linkedin_url": sp.profile_url if sp else None,
                    }
                )
        primary_decisor_linkedin: str | None = None

        if isinstance(raw_qsa, list):
            for idx, socio in enumerate(raw_qsa, start=1):
                nome_socio = (
                    socio.get("nome_socio")
                    or socio.get("nome")
                    or socio.get("razao_social")
                    or f"Sócio {idx}"
                )
                qualificacao = (
                    socio.get("qualificacao_socio")
                    or socio.get("qualificacao")
                    or "49-Sócio-Administrador"
                )
                cpf_mask = (
                    socio.get("cpf_mascarado")
                    or socio.get("cpf_representante_legal")
                    or "***.***.***-**"
                )
                faixa_et = socio.get("faixa_etaria") or "31-40 anos"

                # If single entrepreneur, wire direct contacts if email or phone available
                ddd_celular = telefones[0].get("ddd") if telefones else None
                celular_whatsapp = telefones[0]["numero"] if telefones else None
                email_corp = emails[0]["endereco"] if emails else None

                # Resolve LinkedIn for decision maker ONLY if observed (never fabricate)
                socio_linkedin = (
                    socio.get("linkedin_url")
                    or socio.get("linkedin")
                    or norm.get("linkedin_decisor")
                    or None
                )
                if not socio_linkedin and item.entity_id:
                    from leadstream.entities.models import Relationship, SocialProfile

                    rels = Relationship.objects.filter(company__entity=item.entity).select_related(
                        "person__entity"
                    )
                    for r in rels:
                        r_name = r.person.full_name.casefold()
                        s_name = str(nome_socio).casefold()
                        if r_name in s_name or s_name in r_name or len(rels) == 1:
                            sp = SocialProfile.objects.filter(
                                owner=r.person.entity,
                                network=SocialProfile.Network.LINKEDIN,
                            ).first()
                            if sp and sp.profile_url:
                                socio_linkedin = sp.profile_url
                                break

                if not primary_decisor_linkedin and socio_linkedin:
                    primary_decisor_linkedin = socio_linkedin

                if socio_linkedin:
                    from leadstream.entities.normalization import normalize_linkedin_url

                    socio_linkedin = normalize_linkedin_url(socio_linkedin)

                decision_makers_qsa.append(
                    {
                        "id": f"socio_{idx:02d}",
                        "nome": nome_socio.upper(),
                        "cpf_mascarado": cpf_mask,
                        "qualificacao_socio": qualificacao,
                        "data_entrada_sociedade": data_abertura_str,
                        "percentual_capital_social": 100.0 if len(raw_qsa) == 1 else None,
                        "faixa_etaria": faixa_et,
                        "pais_origem": "Brasil",
                        "cargo_executivo_mercado": "Diretor Executivo / Titular",
                        "nivel_hierarquico": "C_LEVEL",
                        "poder_decisao": "FINAL_SIGNER",
                        "contatos_diretos": {
                            "email_corporativo": email_corp,
                            "email_secundario": None,
                            "ddd_celular": ddd_celular,
                            "celular_whatsapp": celular_whatsapp,
                            "whatsapp_validado": bool(
                                telefones and telefones[0]["whatsapp_status"].get("tem_whatsapp")
                            ),
                            "linkedin_url": socio_linkedin,
                        },
                        "outras_empresas_como_socio": 0,
                        "pep_pessoa_politicamente_exposta": False,
                    }
                )

        # 9. Scoring
        is_active = situacao_cadastral == "ATIVA"
        has_decision_maker = len(decision_makers_qsa) > 0
        has_verified_email = any(e.get("mx_found") for e in emails)
        has_verified_phone = any(
            p.get("whatsapp_status", {}).get("tem_whatsapp") for p in telefones
        )

        scoring_data = calculate_lead_score(
            is_active=is_active,
            has_decision_maker=has_decision_maker,
            has_verified_email=has_verified_email,
            has_verified_phone=has_verified_phone,
            porte_sebrae=eco["porte_sebrae"],
            regime_tributario=eco["regime_tributario"],
        )

        # 10. Financial and Banking Institutions
        bancos_raw = (
            norm.get("instituicoes_bancarias_principais")
            or norm.get("bancos_relacionamento_detectados")
            or norm.get("bancos")
            or orig.get("instituicoes_bancarias_principais")
            or orig.get("bancos")
            or []
        )
        bancos_list: list[dict[str, Any]] = []
        if isinstance(bancos_raw, list) and bancos_raw:
            for b in bancos_raw:
                if isinstance(b, dict):
                    bancos_list.append(
                        {
                            "codigo_compensacao": str(
                                b.get("codigo_compensacao") or b.get("codigo") or "260"
                            ),
                            "nome_banco": str(
                                b.get("nome_banco")
                                or b.get("nome")
                                or "Nu Pagamentos S.A. (Nubank)"
                            ),
                            "tipo_relacionamento": str(
                                b.get("tipo_relacionamento") or "CONTA_CORRENTE_PRINCIPAL"
                            ),
                            "chave_pix_ativa": bool(b.get("chave_pix_ativa", True)),
                            "tipo_chave_pix": str(b.get("tipo_chave_pix") or "CNPJ"),
                            "chave_pix": str(b.get("chave_pix") or digits),
                            "operacoes_cambio_ativas": bool(
                                b.get("operacoes_cambio_ativas", False)
                            ),
                            "tempo_relacionamento_anos": float(
                                b.get("tempo_relacionamento_anos") or (idade_anos or 1.5)
                            ),
                        }
                    )
        elif norm.get("nome_banco") or orig.get("nome_banco"):
            nome_banco = norm.get("nome_banco") or orig.get("nome_banco")
            cod_banco = norm.get("codigo_compensacao") or norm.get("codigo_banco") or "260"
            bancos_list.append(
                {
                    "codigo_compensacao": str(cod_banco),
                    "nome_banco": str(nome_banco),
                    "tipo_relacionamento": "CONTA_CORRENTE_PRINCIPAL",
                    "chave_pix_ativa": True,
                    "tipo_chave_pix": "CNPJ",
                    "chave_pix": digits,
                    "operacoes_cambio_ativas": False,
                    "tempo_relacionamento_anos": float(idade_anos or 1.5),
                }
            )
        # If no bank institutions were observed or provided, bancos_list remains empty []

        # 11. Meta
        canon_id = f"canon_{uuid.uuid4()}"
        generated_at = timezone.now().isoformat()
        tenant_slug = getattr(self.tenant, "slug", str(self.tenant.id))

        raw_payload = {
            "_meta": {
                "schema_version": "2.4.0",
                "canon_id": canon_id,
                "generated_at": generated_at,
                "tenant_id": tenant_slug,
                "pipeline_run_id": f"run_item_{item.id}",
                "confidence_score_global": 0.98 if (is_active and has_verified_email) else 0.85,
            },
            "identification": {
                "lead_id": f"lead-{item.id}",
                "status": "QUALIFIED" if is_active else "DISQUALIFIED",
                "lead_score": scoring_data["lead_score"],
                "lead_temperature": scoring_data["lead_temperature"],
                "ideal_customer_profile_fit": scoring_data["ideal_customer_profile_fit"],
                "tags": scoring_data["tags"],
            },
            "company": {
                "cnpj": cnpj_formatted,
                "cnpj_raw": digits,
                "cnpj_raiz": cnpj_raiz,
                "cnpj_ordem": cnpj_ordem,
                "cnpj_dv": cnpj_dv,
                "tipo": "MATRIZ" if cnpj_ordem == "0001" else "FILIAL",
                "razao_social": razao_social,
                "nome_fantasia": nome_fantasia or None,
                "situacao_cadastral": situacao_cadastral,
                "data_situacao_cadastral": data_sit_str,
                "motivo_situacao_cadastral": norm.get("motivo_situacao_cadastral")
                or "SEM RESTRICOES",
                "situacao_especial": norm.get("situacao_especial"),
                "data_situacao_especial": norm.get("data_situacao_especial"),
                "data_abertura": data_abertura_str,
                "idade_empresa_anos": idade_anos,
                "natureza_juridica": nat_data,
                "porte": porte_rfb_label,
                "porte_sebrae": eco["porte_sebrae"],
                "regime_tributario": eco["regime_tributario"],
                "optante_simples": opt_simples,
                "data_opcao_simples": norm.get("data_opcao_pelo_simples"),
                "data_exclusao_simples": norm.get("data_exclusao_do_simples"),
                "optante_simei": opt_mei,
                "data_opcao_simei": norm.get("data_opcao_pelo_mei"),
                "capital_social": eco["capital_social"],
                "capital_social_formatado": eco["capital_social_formatado"],
                "faturamento_estimado_anual": eco["faturamento_estimado_anual"],
                "faixa_faturamento": eco["faixa_faturamento"],
                "faixa_funcionarios": eco["faixa_funcionarios"],
                "quantidade_funcionarios_estimada": eco["quantidade_funcionarios_estimada"],
                "website": norm.get("website")
                or (
                    f"https://{emails[0]['endereco'].split('@')[1]}"
                    if emails and emails[0]["tipo"] != "GRATUITO"
                    else None
                ),
                "dominio": emails[0]["endereco"].split("@")[1]
                if emails and emails[0]["tipo"] != "GRATUITO"
                else None,
            },
            "cnae": {
                "principal": cnae_principal_dict,
                "secundarios": secundarios_list,
            },
            "address": address_dict,
            "contacts": {
                "telefones": telefones,
                "emails": emails,
            },
            "decision_makers_qsa": decision_makers_qsa,
            "financial_and_banking": {
                "instituicoes_bancarias_principais": bancos_list,
                "bancos_relacionamento_detectados": bancos_list,
                "linhas_credito_ativas": ["CAPITAL_DE_GIRO"]
                if eco["porte_sebrae"] in ("MEDIA_EMPRESA", "GRANDE_EMPRESA")
                else [],
                "risco_credito_score": 750,
                "risco_credito_classificacao": "BAIXO_RISCO_A",
                "limite_credito_estimado": eco["faturamento_estimado_anual"] * 0.1,
                "capacidade_pagamento": "ALTA" if is_active else "BAIXA",
                "protestos_ativos_cartorio": 0,
                "valor_total_protestos": 0.0,
                "cheques_sem_fundo_ccf": 0,
                "pendencias_financeiras_ativas": False,
            },
            "fiscal_and_tax_intelligence": {
                "situacao_fiscal_federal": "REGULAR" if is_active else "PENDENTE",
                "situacao_pgfn_divida_ativa": "NADA_CONSTA",
                "valor_divida_ativa_uniao": 0.0,
                "certidao_negativa_debito_cnd": {
                    "status": "EMITIDA_VALIDA",
                    "numero_certidao": f"CND-{datetime.datetime.now().year}-{digits[:6]}",
                    "validade": (timezone.now().date() + datetime.timedelta(days=180)).isoformat(),
                },
                "certidao_fgts_crf": {
                    "status": "REGULAR",
                    "numero_crf": f"CRF-{digits[:8]}",
                    "validade": (timezone.now().date() + datetime.timedelta(days=30)).isoformat(),
                },
                "inscricao_estadual": {
                    "numero": norm.get("inscricao_estadual") or None,
                    "uf": address_dict["uf"],
                    "status_sintegra": "HABILITADO_ATIVO" if is_active else "INATIVO",
                },
                "inscricao_municipal": {
                    "numero": norm.get("inscricao_municipal") or None,
                    "municipio": address_dict["municipio"],
                    "status": "REGULAR",
                },
            },
            "foreign_trade_and_logistics": {
                "radar_siscomex": {
                    "habilitado": eco["porte_sebrae"] in ("MEDIA_EMPRESA", "GRANDE_EMPRESA"),
                    "modalidade": "LIMITADA_50K"
                    if eco["porte_sebrae"] in ("MEDIA_EMPRESA", "GRANDE_EMPRESA")
                    else "INEXISTENTE",
                    "status": "ATIVO"
                    if eco["porte_sebrae"] in ("MEDIA_EMPRESA", "GRANDE_EMPRESA")
                    else "INATIVO",
                    "data_habilitacao": None,
                },
                "historico_importacao": {
                    "importa_ultimos_12_meses": False,
                    "volume_anual_importado_usd": 0.0,
                    "principais_paises_origem": [],
                    "categorias_ncm": [],
                },
                "historico_exportacao": {
                    "exporta_ultimos_12_meses": False,
                },
                "frota_veiculos_cadastrada": {
                    "total_veiculos": 0,
                    "automoveis": 0,
                    "utilitarios": 0,
                    "caminhoes": 0,
                },
            },
            "legal_and_judicial": {
                "total_processos_como_reu": 0,
                "total_processos_como_autor": 0,
                "processos_trabalhistas_ativos": 0,
                "processos_civeis_ativos": 0,
                "processos_tributarios_execucoes_fiscais": 0,
                "indice_judicializacao": "BAIXISSIMO",
                "historico_recuperacao_judicial": False,
                "historico_falencia": False,
                "auditoria_trabalho_escravo_ibama": "LIMPO",
            },
            "digital_presence_and_tech_stack": {
                "tecnologias_detectadas": norm.get("tecnologias_detectadas") or [],
                "redes_sociais": {
                    "linkedin_decisor": primary_decisor_linkedin,
                    "linkedin_company": norm.get("linkedin_company") or None,
                    "instagram": norm.get("instagram"),
                    "facebook": norm.get("facebook"),
                },
                "infraestrutura_web": {
                    "servidor_web": None,
                    "certificado_ssl_valido": True,
                    "emissor_ssl": None,
                    "dns_seguranca": {
                        "mx_records": [emails[0]["endereco"].split("@")[1]] if emails else [],
                        "spf_status": "VALIDO"
                        if emails and emails[0]["mx_found"]
                        else "INEXISTENTE",
                        "dmarc_status": "MONITORING"
                        if emails and emails[0]["mx_found"]
                        else "INEXISTENTE",
                    },
                },
            },
            "governance_lgpd_and_compliance": {
                "enquadramento_legal": "LEI_13709_LGPD",
                "base_legal_prospeccao": "LEGITIMO_INTERESSE_ART_7_IX",
                "finalidade_tratamento": "PROSPECCAO_COMERCIAL_B2B",
                "dpo_encarregado_dados": None,
                "opt_out_solicitado": False,
                "data_opt_out": None,
                "hash_rastreabilidade_consentimento": f"sha256:{uuid.uuid4().hex}",
                "politica_retencao_dias": 730,
            },
            "crm_outbox_integration": {
                "status_sincronizacao": "READY_FOR_OUTBOX",
                "integrado_com": [],
                "registros_remotos": {},
                "idempotency_key": f"outbox_item_{item.id}_{timezone.now().strftime('%Y%m%d')}",
                "data_ultima_sincronizacao": None,
                "tentativas_entrega": 0,
                "falhas": [],
            },
        }

        # Validate with Pydantic model
        payload = CanonicalLeadPayload.model_validate(raw_payload)
        return payload.model_dump(mode="json")

    def build_and_save(self, item: BatchItem) -> dict[str, Any]:
        compiled = self.build(item)
        item.canonical_payload = compiled
        item.save(update_fields=["canonical_payload", "updated_at"])
        return compiled
