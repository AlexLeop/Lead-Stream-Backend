from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from leadstream.entities.normalization import only_digits
from leadstream.validation.phone_check import get_phone_operator_hint

logger = logging.getLogger(__name__)

# Categorias de Elegibilidade para Crédito Consignado
CATEGORY_APTO = "APTO_CONSIGNAVEL"
CATEGORY_RESTRITO_BPC = "RESTRITO_BPC"
CATEGORY_BLOQUEADO_TEMPORARIO = "BLOQUEADO_TEMPORARIO"
CATEGORY_INAPTO = "INAPTO"

# Tabela Oficial de Espécies de Benefício do INSS
INSS_ESPECIES: dict[str, dict[str, Any]] = {
    # Aposentadorias - Alto Potencial de Consignado (Apto)
    "41": {
        "codigo": "41",
        "descricao": "Aposentadoria por Idade",
        "categoria": CATEGORY_APTO,
        "elegivel": True,
        "alerta": None,
        "observacao": "Público-alvo preferencial para crédito consignado.",
    },
    "42": {
        "codigo": "42",
        "descricao": "Aposentadoria por Tempo de Contribuição",
        "categoria": CATEGORY_APTO,
        "elegivel": True,
        "alerta": None,
        "observacao": "Excelente histórico de estabilidade e ticket médio.",
    },
    "32": {
        "codigo": "32",
        "descricao": "Aposentadoria por Invalidez Previdenciária",
        "categoria": CATEGORY_APTO,
        "elegivel": True,
        "alerta": "Verificar se benefício possui isenção ou revisão médica pendente.",
        "observacao": "Apto para consignação.",
    },
    "57": {
        "codigo": "57",
        "descricao": "Aposentadoria Especial",
        "categoria": CATEGORY_APTO,
        "elegivel": True,
        "alerta": None,
        "observacao": "Apto para consignação com margem integral.",
    },
    "04": {
        "codigo": "04",
        "descricao": "Aposentadoria por Invalidez de Trabalhador Rural",
        "categoria": CATEGORY_APTO,
        "elegivel": True,
        "alerta": None,
        "observacao": "Apto para consignação.",
    },
    "07": {
        "codigo": "07",
        "descricao": "Aposentadoria por Idade do Trabalhador Rural",
        "categoria": CATEGORY_APTO,
        "elegivel": True,
        "alerta": None,
        "observacao": "Apto para consignação.",
    },
    "08": {
        "codigo": "08",
        "descricao": "Aposentadoria por Idade do Empregador Rural",
        "categoria": CATEGORY_APTO,
        "elegivel": True,
        "alerta": None,
        "observacao": "Apto para consignação.",
    },
    "19": {
        "codigo": "19",
        "descricao": "Aposentadoria de Ex-combatente",
        "categoria": CATEGORY_APTO,
        "elegivel": True,
        "alerta": None,
        "observacao": "Apto para consignação.",
    },
    "46": {
        "codigo": "46",
        "descricao": "Aposentadoria Especial de Professor",
        "categoria": CATEGORY_APTO,
        "elegivel": True,
        "alerta": None,
        "observacao": "Apto para consignação com margem integral.",
    },
    "52": {
        "codigo": "52",
        "descricao": "Aposentadoria por Idade da Pessoa com Deficiência",
        "categoria": CATEGORY_APTO,
        "elegivel": True,
        "alerta": None,
        "observacao": "Apto para consignação.",
    },
    # Pensões - Apto
    "21": {
        "codigo": "21",
        "descricao": "Pensão por Morte Previdenciária",
        "categoria": CATEGORY_APTO,
        "elegivel": True,
        "alerta": "Verificar se há múltiplos pensionistas dividindo a cota-parte.",
        "observacao": "Apto para consignação.",
    },
    "22": {
        "codigo": "22",
        "descricao": "Pensão por Morte de Ex-combatente",
        "categoria": CATEGORY_APTO,
        "elegivel": True,
        "alerta": None,
        "observacao": "Apto para consignação.",
    },
    "92": {
        "codigo": "92",
        "descricao": "Pensão por Morte por Acidente do Trabalho",
        "categoria": CATEGORY_APTO,
        "elegivel": True,
        "alerta": None,
        "observacao": "Apto para consignação.",
    },
    # Assistenciais / BPC (Restrito - Exige atenção jurídica e regras de banco)
    "87": {
        "codigo": "87",
        "descricao": "Amparo Assistencial à Pessoa com Deficiência (BPC/LOAS)",
        "categoria": CATEGORY_RESTRITO_BPC,
        "elegivel": True,
        "alerta": "BPC/LOAS possui regras restritivas e margem via portarias MDS/INSS.",
        "observacao": "Elegibilidade condicionada às diretrizes do banco emissor.",
    },
    "88": {
        "codigo": "88",
        "descricao": "Amparo Assistencial ao Idoso (BPC/LOAS)",
        "categoria": CATEGORY_RESTRITO_BPC,
        "elegivel": True,
        "alerta": "BPC/LOAS possui regras restritivas e margem via portarias MDS/INSS.",
        "observacao": "Elegibilidade condicionada às diretrizes do banco emissor.",
    },
    # Benefícios Temporários - Bloqueado / Inapto para longo prazo
    "31": {
        "codigo": "31",
        "descricao": "Auxílio por Incapacidade Temporária (Auxílio-Doença)",
        "categoria": CATEGORY_BLOQUEADO_TEMPORARIO,
        "elegivel": False,
        "alerta": "Benefício de caráter temporário com cessação prevista. Inapto para consignação.",
        "observacao": "Não permite averbação de consignado pela Previdência Social.",
    },
    "91": {
        "codigo": "91",
        "descricao": "Auxílio por Incapacidade Temporária Acidentária",
        "categoria": CATEGORY_BLOQUEADO_TEMPORARIO,
        "elegivel": False,
        "alerta": "Benefício acidentário temporário. Inapto para consignação.",
        "observacao": "Não permite averbação de consignado.",
    },
    "13": {
        "codigo": "13",
        "descricao": "Auxílio-Acidente",
        "categoria": CATEGORY_BLOQUEADO_TEMPORARIO,
        "elegivel": False,
        "alerta": "Benefício indenizatório complementar. Consultar regras bancárias.",
        "observacao": "Geralmente inapto para consignação direta.",
    },
    "80": {
        "codigo": "80",
        "descricao": "Salário-Maternidade",
        "categoria": CATEGORY_BLOQUEADO_TEMPORARIO,
        "elegivel": False,
        "alerta": "Benefício com duração transitória (120 dias).",
        "observacao": "Inapto para empréstimo consignado.",
    },
    # Inaptos
    "25": {
        "codigo": "25",
        "descricao": "Auxílio-Reclusão",
        "categoria": CATEGORY_INAPTO,
        "elegivel": False,
        "alerta": "Benefício inapto para operações de crédito consignado.",
        "observacao": "Vedado pela legislação previdenciária.",
    },
    "48": {
        "codigo": "48",
        "descricao": "Salário-Família",
        "categoria": CATEGORY_INAPTO,
        "elegivel": False,
        "alerta": "Complemento de renda familiar sem natureza consignável.",
        "observacao": "Inapto.",
    },
}


def get_inss_species_info(code: str | int | None) -> dict[str, Any]:
    """Recupera metadados oficiais e elegibilidade de consignado para benefício do INSS."""
    if code is None:
        return {
            "codigo": None,
            "descricao": "Espécie não informada",
            "categoria": CATEGORY_INAPTO,
            "elegivel": False,
            "alerta": "Código da espécie de benefício não disponível.",
            "observacao": "Sem dados de espécie para averiguação.",
        }

    clean_code = str(code).strip()
    if clean_code in INSS_ESPECIES:
        item = INSS_ESPECIES[clean_code]
        return {
            "codigo": clean_code,
            "descricao": item["descricao"],
            "categoria": item["categoria"],
            "elegivel": item["elegivel"],
            "alerta": item["alerta"],
            "observacao": item["observacao"],
        }

    # Código não mapeado explicitamente
    return {
        "codigo": clean_code,
        "descricao": f"Benefício INSS Espécie {clean_code}",
        "categoria": "DESCONHECIDO",
        "elegivel": True,  # Permite análise manual
        "alerta": f"Espécie {clean_code} não listada. Validar averbação no Dataprev/Meu INSS.",
        "observacao": "Consultar tabela de averbação da instituição financeira.",
    }


def calculate_margem_consignavel(base_salary: float | Decimal | int | None) -> dict[str, Any]:
    """Calcula a margem consignável estimada (Lei 14.431/2022 e INSS/PRES 138/2022).

    Divisão legal:
    - 35%: Empréstimo Pessoal Consignado tradicional.
    - 5%: Reserva de Margem Consignável (RMC) - Cartão de Crédito Consignado.
    - 5%: Reserva de Cartão Consignado de Benefício (RCC).
    - 45%: Margem Consignável Total Estimada.
    """
    if base_salary is None:
        salary_val = 0.0
    else:
        try:
            salary_val = float(base_salary)
        except (ValueError, TypeError):
            salary_val = 0.0

    if salary_val <= 0:
        return {
            "salario_base": 0.0,
            "elegivel": False,
            "margem_emprestimo_35": 0.0,
            "margem_rmc_cartao_5": 0.0,
            "margem_rcc_beneficio_5": 0.0,
            "margem_total_45": 0.0,
            "percentual_emprestimo": 35.0,
            "percentual_rmc": 5.0,
            "percentual_rcc": 5.0,
            "percentual_total": 45.0,
            "mensagem": "Salário ou benefício base não informado ou zerado.",
        }

    margem_35 = round(salary_val * 0.35, 2)
    margem_5_rmc = round(salary_val * 0.05, 2)
    margem_5_rcc = round(salary_val * 0.05, 2)
    margem_total = round(margem_35 + margem_5_rmc + margem_5_rcc, 2)

    return {
        "salario_base": round(salary_val, 2),
        "elegivel": True,
        "margem_emprestimo_35": margem_35,
        "margem_rmc_cartao_5": margem_5_rmc,
        "margem_rcc_beneficio_5": margem_5_rcc,
        "margem_total_45": margem_total,
        "percentual_emprestimo": 35.0,
        "percentual_rmc": 5.0,
        "percentual_rcc": 5.0,
        "percentual_total": 45.0,
        "mensagem": "Margem calculada pela Lei 14.431/2022 (35% + 5% RMC + 5% RCC).",
    }


def evaluate_filtro_perda(
    is_deceased: bool | None,
    death_date: str | None,
    tax_status: str | None,
) -> dict[str, Any]:
    """Avalia o Filtro de Perda (Camada 1 do Consignado).

    Detecta se o lead é inapto por óbito comprovado ou por irregularidade
    cadastral na Receita Federal (Cancelada, Nula ou Suspensa).
    Leads expurgados por óbito NÃO geram cobrança de créditos.
    """
    clean_tax_status = (tax_status or "REGULAR").upper().strip()

    # 1. Falecimento confirmado
    if is_deceased or bool(death_date):
        return {
            "status": "EXPURGADO_OBITO",
            "is_deceased": True,
            "death_date": death_date[:10] if death_date else None,
            "tax_status": clean_tax_status,
            "elegivel_consignado": False,
            "motivo_expurgo": (
                "Indicador de óbito confirmado pelo cadastro central de pessoas físicas."
            ),
            "deve_cobrar_credito": False,
            "badge_texto": "💀 Óbito Detectado (Expurgado)",
            "badge_variante": "danger",
            "fontes_consultadas": [
                "BASE_CADASTRO_CENTRAL_RFB",
                "SISTEMA_NACIONAL_OBITOS_RCPN",
            ],
        }

    # 2. Receita Federal Irregular
    if clean_tax_status in ("CANCELADA", "NULA", "SUSPENSA", "INAPTA"):
        return {
            "status": "EXPURGADO_RECEITA_IRREGULAR",
            "is_deceased": False,
            "death_date": None,
            "tax_status": clean_tax_status,
            "elegivel_consignado": False,
            "motivo_expurgo": f"CPF com situação cadastral na Receita Federal: {clean_tax_status}.",
            "deve_cobrar_credito": False,
            "badge_texto": f"⚠️ CPF {clean_tax_status}",
            "badge_variante": "warning",
            "fontes_consultadas": [
                "BASE_CADASTRO_CENTRAL_RFB",
                "SISTEMA_NACIONAL_OBITOS_RCPN",
            ],
        }

    # 3. Regular
    return {
        "status": "REGULAR",
        "is_deceased": False,
        "death_date": None,
        "tax_status": clean_tax_status,
        "elegivel_consignado": True,
        "motivo_expurgo": None,
        "deve_cobrar_credito": True,
        "badge_texto": "✅ Lead Apto & Regular",
        "badge_variante": "success",
        "fontes_consultadas": [
            "BASE_CADASTRO_CENTRAL_RFB",
            "SISTEMA_NACIONAL_OBITOS_RCPN",
        ],
    }


def evaluate_nao_me_perturbe(
    phone: str,
    block_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Avalia se o telefone possui restrição no 'Não Me Perturbe' (Anatel/Febraban).

    Protege financeiras e correspondentes de multas de até R$ 50 mil por infração.
    """
    phone_digits = only_digits(phone)
    if not phone_digits:
        return {
            "inscrito_nao_me_perturbe": False,
            "entidade": "NENHUMA",
            "data_bloqueio": None,
            "motivo": "Número inválido ou ausente.",
            "seguro_para_discagem_fria": False,
            "risco_multa": "BAIXO",
            "badge_texto": "Número Inválido",
            "badge_variante": "secondary",
        }

    if block_records:
        for rec in block_records:
            if not isinstance(rec, dict):
                continue
            rec_phone = only_digits(
                str(rec.get("phone") or rec.get("number") or rec.get("telefone") or "")
            )
            is_blocked = bool(
                rec.get("blocked")
                or rec.get("is_blocked")
                or rec.get("bloqueado")
                or rec.get("do_not_call")
                or rec.get("DoNotCall")
            )

            # Match por terminação do número ou igualdade
            if is_blocked and (
                rec_phone == phone_digits
                or (len(phone_digits) >= 8 and rec_phone.endswith(phone_digits[-8:]))
            ):
                data_bloq = rec.get("block_date") or rec.get("data_bloqueio") or rec.get("Date")
                return {
                    "inscrito_nao_me_perturbe": True,
                    "entidade": str(rec.get("entity") or rec.get("entidade") or "ANATEL_FEBRABAN"),
                    "data_bloqueio": str(data_bloq)[:10] if data_bloq else None,
                    "motivo": (
                        "Inscrito no Não Me Perturbe (Bloqueio de Telemarketing Bancário)."
                    ),
                    "seguro_para_discagem_fria": False,
                    "risco_multa": "ALTO",
                    "badge_texto": "⛔ Inscrito no Não Me Perturbe",
                    "badge_variante": "danger",
                }

    return {
        "inscrito_nao_me_perturbe": False,
        "entidade": "NENHUMA",
        "data_bloqueio": None,
        "motivo": "Número liberado para prospecção e discagem telefônica.",
        "seguro_para_discagem_fria": True,
        "risco_multa": "BAIXO",
        "badge_texto": "✅ Liberado para Telemarketing",
        "badge_variante": "success",
    }


def rank_mailing_telefones(
    candidate_phones: list[dict[str, Any]],
    block_records: list[dict[str, Any]] | None = None,
    max_count: int = 3,
) -> list[dict[str, Any]]:
    """Gera o Mailing Higienizado (Top 3 Celulares) ordenados por assertividade legal.

    Critérios de pontuação:
    - WhatsApp Ativo / Verificado: +35 pts
    - Livre de Não Me Perturbe: +30 pts
    - Celular / Linha Móvel: +15 pts
    - Operadora Reconhecida (VIVO, CLARO, TIM): +10 pts
    - Recência / Score do Bureau: até +10 pts
    - Penalidade severa se inscrito no Não Me Perturbe: -40 pts (rebaixa discagem de voz)
    """
    scored_candidates: list[tuple[int, dict[str, Any]]] = []

    for item in candidate_phones:
        raw_num = str(item.get("numero") or item.get("phone") or "")
        ddd = str(item.get("ddd") or "")
        clean_digits = only_digits(raw_num)
        if not clean_digits:
            continue

        if clean_digits.startswith("55") and len(clean_digits) in (12, 13):
            clean_digits = clean_digits[2:]

        clean_ddd = only_digits(ddd)
        if len(clean_digits) in (10, 11):
            detected_ddd = clean_digits[:2]
            number_part = clean_digits[2:]
        elif len(clean_digits) in (8, 9):
            detected_ddd = clean_ddd if clean_ddd else "11"
            number_part = clean_digits
        else:
            detected_ddd = clean_ddd
            number_part = clean_digits

        is_celular = bool(
            item.get("is_celular")
            or item.get("isCelular")
            or (len(number_part) == 9 and number_part.startswith("9"))
        )
        operadora = (
            item.get("operadora")
            or item.get("carrier")
            or get_phone_operator_hint(detected_ddd, number_part)
        )

        has_wa = bool(
            item.get("whatsappDisponivel") or item.get("has_whatsapp") or item.get("tem_whatsapp")
        )
        tipo_conta_wa = str(item.get("tipoConta") or item.get("tipo_conta") or "NENHUMA")

        # Avaliar Não Me Perturbe
        full_digits = f"{detected_ddd}{number_part}" if detected_ddd else number_part
        nmp_status = evaluate_nao_me_perturbe(full_digits, block_records=block_records)

        # Cálculo do Score de Assertividade de Contato (0 a 100)
        score = 0

        # WhatsApp ativo
        if has_wa:
            score += 35
        # Livre do Não Me Perturbe
        if not nmp_status["inscrito_nao_me_perturbe"]:
            score += 30
        else:
            score -= 40  # Penalidade expressiva
        # Móvel
        if is_celular:
            score += 15
        # Operadora válida
        if operadora in ("VIVO", "CLARO", "TIM"):
            score += 10
        elif operadora != "DESCONHECIDA":
            score += 5
        # Score de bureau / recência
        bureau_score = float(item.get("score") or item.get("scoreBureau") or 0)
        score += min(10, int(bureau_score * 10))

        # Normalização do score entre 0 e 100
        score = max(0, min(100, score))

        # Recomendação de canal
        if nmp_status["inscrito_nao_me_perturbe"]:
            if has_wa:
                recomendacao = "APENAS_WHATSAPP_COMPLIANCE"
                rotulo_canal = "⚠️ Apenas WhatsApp (Bloqueado para Voz)"
            else:
                recomendacao = "DESACONSELHADO"
                rotulo_canal = "⛔ Desaconselhado (Bloqueado no Não Me Perturbe)"
        elif has_wa:
            recomendacao = "DISCAGEM_E_WHATSAPP"
            rotulo_canal = "🌟 Prioridade Máxima (Voz & WhatsApp Liberados)"
        elif is_celular:
            recomendacao = "DISCAGEM_VOZ_APENAS"
            rotulo_canal = "📞 Discagem Telefônica Liberada"
        else:
            recomendacao = "DISCAGEM_VOZ_FIXO"
            rotulo_canal = "☎️ Fixo (Discagem Liberada)"

        # Formatação amigável do número
        if len(number_part) == 9:
            num_fmt = (
                f"({detected_ddd}) {number_part[:5]}-{number_part[5:]}"
                if detected_ddd
                else f"{number_part[:5]}-{number_part[5:]}"
            )
        elif len(number_part) == 8:
            num_fmt = (
                f"({detected_ddd}) {number_part[:4]}-{number_part[4:]}"
                if detected_ddd
                else f"{number_part[:4]}-{number_part[4:]}"
            )
        else:
            num_fmt = f"({detected_ddd}) {number_part}" if detected_ddd else number_part

        e164 = f"+55{full_digits}"

        scored_item = {
            "numeroFormatado": num_fmt,
            "numeroRaw": full_digits,
            "numeroE164": e164,
            "ddd": detected_ddd,
            "tipo": "Celular" if is_celular else "Fixo",
            "operadora": operadora,
            "whatsappDisponivel": has_wa,
            "tipoConta": tipo_conta_wa,
            "linkWhatsApp": f"https://wa.me/{e164.lstrip('+')}" if has_wa else None,
            "naoMePerturbe": nmp_status,
            "scoreAssertividade": score,
            "recomendacao": recomendacao,
            "rotuloCanal": rotulo_canal,
        }
        scored_candidates.append((score, scored_item))

    # Ordenar por maior assertividade
    scored_candidates.sort(key=lambda x: x[0], reverse=True)

    result_mailing: list[dict[str, Any]] = []
    for rank, (_, item_dict) in enumerate(scored_candidates[:max_count], start=1):
        item_dict["ordemRecomendada"] = rank
        result_mailing.append(item_dict)

    return result_mailing
