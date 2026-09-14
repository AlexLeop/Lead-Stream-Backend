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


def _national_phone(value: str) -> str:
    clean = only_digits(value)
    if clean.startswith("55") and len(clean) in (12, 13):
        return clean[2:]
    return clean


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
        "elegivel": False,
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
        "elegivel": None,
        "margem_emprestimo_35": margem_35,
        "margem_rmc_cartao_5": margem_5_rmc,
        "margem_rcc_beneficio_5": margem_5_rcc,
        "margem_total_45": margem_total,
        "percentual_emprestimo": 35.0,
        "percentual_rmc": 5.0,
        "percentual_rcc": 5.0,
        "percentual_total": 45.0,
        "mensagem": (
            "Cenário matemático parametrizado; não confirma margem disponível, elegibilidade "
            "ou averbação. Consulte a fonte oficial aplicável antes de ofertar crédito."
        ),
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
    clean_tax_status = (tax_status or "DESCONHECIDA").upper().strip()

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
            "fontes_consultadas": ["PROVEDOR_CADASTRAL"],
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
            "fontes_consultadas": ["PROVEDOR_CADASTRAL"],
        }

    # Ausência de sinal ou situação diferente de REGULAR não comprova elegibilidade.
    if clean_tax_status != "REGULAR" or is_deceased is None:
        return {
            "status": "INCONCLUSIVO",
            "is_deceased": None,
            "death_date": None,
            "tax_status": clean_tax_status or "DESCONHECIDA",
            "elegivel_consignado": False,
            "motivo_expurgo": "Dados insuficientes para confirmar situação cadastral e óbito.",
            "deve_cobrar_credito": None,
            "badge_texto": "Situação não confirmada",
            "badge_variante": "secondary",
            "fontes_consultadas": [],
        }

    # 3. Regularidade explicitamente informada pelo provedor
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
        "fontes_consultadas": ["PROVEDOR_CADASTRAL"],
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
            "status_consulta": "INCONCLUSIVO",
            "inscrito_nao_me_perturbe": None,
            "entidade": None,
            "data_bloqueio": None,
            "motivo": "Número inválido ou ausente.",
            "seguro_para_discagem_fria": False,
            "risco_multa": "DESCONHECIDO",
            "badge_texto": "Número Inválido",
            "badge_variante": "secondary",
        }

    if block_records is not None:
        for rec in block_records:
            if not isinstance(rec, dict):
                continue
            rec_phone = only_digits(
                str(rec.get("phone") or rec.get("number") or rec.get("telefone") or "")
            )
            raw_blocked = next(
                (
                    rec.get(key)
                    for key in (
                        "blocked",
                        "is_blocked",
                        "bloqueado",
                        "do_not_call",
                        "DoNotCall",
                    )
                    if rec.get(key) is not None
                ),
                None,
            )
            is_blocked = raw_blocked is True or str(raw_blocked).strip().casefold() in {
                "true",
                "1",
                "sim",
                "yes",
            }

            if is_blocked and _national_phone(rec_phone) == _national_phone(phone_digits):
                data_bloq = rec.get("block_date") or rec.get("data_bloqueio") or rec.get("Date")
                return {
                    "status_consulta": "BLOQUEADO",
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
            "status_consulta": "NAO_LOCALIZADO_NA_FONTE",
            "inscrito_nao_me_perturbe": False,
            "entidade": "FONTE_CONSULTADA",
            "data_bloqueio": None,
            "motivo": "Nenhum bloqueio localizado na fonte consultada neste instante.",
            "seguro_para_discagem_fria": True,
            "risco_multa": "NAO_IDENTIFICADO",
            "badge_texto": "Bloqueio não localizado",
            "badge_variante": "success",
        }

    return {
        "status_consulta": "NAO_CONSULTADO",
        "inscrito_nao_me_perturbe": None,
        "entidade": None,
        "data_bloqueio": None,
        "motivo": "Fonte de bloqueio não consultada; não autorizar discagem automática.",
        "seguro_para_discagem_fria": False,
        "risco_multa": "DESCONHECIDO",
        "badge_texto": "Conformidade não verificada",
        "badge_variante": "secondary",
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
            detected_ddd = clean_ddd
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

        raw_has_wa = next(
            (
                item.get(key)
                for key in ("whatsappDisponivel", "has_whatsapp", "tem_whatsapp")
                if item.get(key) is not None
            ),
            None,
        )
        has_wa = raw_has_wa is True
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
        if nmp_status["status_consulta"] == "NAO_LOCALIZADO_NA_FONTE":
            score += 30
        elif nmp_status["status_consulta"] == "BLOQUEADO":
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
        if nmp_status["status_consulta"] == "BLOQUEADO":
            recomendacao = "DESACONSELHADO"
            rotulo_canal = "Bloqueado para oferta por telefone"
        elif not nmp_status["seguro_para_discagem_fria"]:
            recomendacao = "AGUARDAR_VALIDACAO_COMPLIANCE"
            rotulo_canal = "Conformidade ainda não verificada"
        elif has_wa:
            recomendacao = "DISCAGEM_E_WHATSAPP"
            rotulo_canal = "Voz liberada; WhatsApp tecnicamente confirmado"
        elif is_celular:
            recomendacao = "DISCAGEM_VOZ_APENAS"
            rotulo_canal = "Discagem liberada; WhatsApp não confirmado"
        else:
            recomendacao = "DISCAGEM_VOZ_FIXO"
            rotulo_canal = "Telefone fixo com bloqueio não localizado"

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

        e164 = f"+55{full_digits}" if detected_ddd else ""

        scored_item = {
            "numeroFormatado": num_fmt,
            "numeroRaw": full_digits,
            "numeroE164": e164,
            "ddd": detected_ddd,
            "tipo": "Celular" if is_celular else "Fixo",
            "operadora": operadora,
            "whatsappDisponivel": has_wa,
            "tipoConta": tipo_conta_wa,
            "linkWhatsApp": (
                f"https://wa.me/{e164.lstrip('+')}" if has_wa and e164 else None
            ),
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
