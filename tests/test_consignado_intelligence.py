from __future__ import annotations

from leadstream.intelligence.consignado import (
    CATEGORY_APTO,
    CATEGORY_BLOQUEADO_TEMPORARIO,
    CATEGORY_INAPTO,
    CATEGORY_RESTRITO_BPC,
    calculate_margem_consignavel,
    evaluate_filtro_perda,
    evaluate_nao_me_perturbe,
    get_inss_species_info,
    rank_mailing_telefones,
)


def test_get_inss_species_info() -> None:
    # Apto
    sp41 = get_inss_species_info("41")
    assert sp41["categoria"] == CATEGORY_APTO
    assert sp41["elegivel"] is True
    assert "Idade" in sp41["descricao"]

    sp21 = get_inss_species_info(21)
    assert sp21["categoria"] == CATEGORY_APTO
    assert sp21["elegivel"] is True
    assert "Pensão" in sp21["descricao"]

    # BPC / LOAS
    sp87 = get_inss_species_info("87")
    assert sp87["categoria"] == CATEGORY_RESTRITO_BPC
    assert sp87["elegivel"] is True
    assert "Deficiência" in sp87["descricao"]
    assert sp87["alerta"] is not None

    # Inapto / Temporário
    sp31 = get_inss_species_info("31")
    assert sp31["categoria"] == CATEGORY_BLOQUEADO_TEMPORARIO
    assert sp31["elegivel"] is False

    sp25 = get_inss_species_info("25")
    assert sp25["categoria"] == CATEGORY_INAPTO
    assert sp25["elegivel"] is False

    # Desconhecido ou nulo
    sp_none = get_inss_species_info(None)
    assert sp_none["elegivel"] is False

    sp_unk = get_inss_species_info("9999")
    assert sp_unk["categoria"] == "DESCONHECIDO"


def test_calculate_margem_consignavel() -> None:
    # Salário base de R$ 2.000,00
    res = calculate_margem_consignavel(2000.0)
    assert res["elegivel"] is True
    assert res["salario_base"] == 2000.0
    assert res["margem_emprestimo_35"] == 700.0  # 35% de 2000
    assert res["margem_rmc_cartao_5"] == 100.0  # 5% de 2000
    assert res["margem_rcc_beneficio_5"] == 100.0  # 5% de 2000
    assert res["margem_total_45"] == 900.0  # 45% de 2000

    # Salário mínimo hipotético R$ 1.518,00
    res_sm = calculate_margem_consignavel(1518.0)
    assert res_sm["margem_emprestimo_35"] == 531.3
    assert res_sm["margem_rmc_cartao_5"] == 75.9
    assert res_sm["margem_rcc_beneficio_5"] == 75.9
    assert res_sm["margem_total_45"] == 683.1

    # Nulo ou zero
    res_zero = calculate_margem_consignavel(0)
    assert res_zero["elegivel"] is False
    assert res_zero["margem_total_45"] == 0.0

    res_none = calculate_margem_consignavel(None)
    assert res_none["elegivel"] is False


def test_evaluate_filtro_perda() -> None:
    # Óbito via flag
    res_obito1 = evaluate_filtro_perda(is_deceased=True, death_date=None, tax_status="REGULAR")
    assert res_obito1["status"] == "EXPURGADO_OBITO"
    assert res_obito1["elegivel_consignado"] is False
    assert res_obito1["deve_cobrar_credito"] is False

    # Óbito via data
    res_obito2 = evaluate_filtro_perda(
        is_deceased=False, death_date="2023-08-10", tax_status="REGULAR"
    )
    assert res_obito2["status"] == "EXPURGADO_OBITO"
    assert res_obito2["deve_cobrar_credito"] is False

    # Receita Federal Cancelada
    res_cancelada = evaluate_filtro_perda(
        is_deceased=False, death_date=None, tax_status="CANCELADA"
    )
    assert res_cancelada["status"] == "EXPURGADO_RECEITA_IRREGULAR"
    assert res_cancelada["deve_cobrar_credito"] is False

    # Regular
    res_reg = evaluate_filtro_perda(is_deceased=False, death_date=None, tax_status="REGULAR")
    assert res_reg["status"] == "REGULAR"
    assert res_reg["elegivel_consignado"] is True
    assert res_reg["deve_cobrar_credito"] is True


def test_evaluate_nao_me_perturbe() -> None:
    blocks = [
        {
            "phone": "11987654321",
            "blocked": True,
            "entity": "ANATEL_FEBRABAN",
            "block_date": "2023-01-15",
        }
    ]

    # Número na lista de bloqueio
    res_blocked = evaluate_nao_me_perturbe("11987654321", block_records=blocks)
    assert res_blocked["inscrito_nao_me_perturbe"] is True
    assert res_blocked["seguro_para_discagem_fria"] is False
    assert res_blocked["risco_multa"] == "ALTO"
    assert "Não Me Perturbe" in res_blocked["badge_texto"]

    # Número livre
    res_free = evaluate_nao_me_perturbe("11999998888", block_records=blocks)
    assert res_free["inscrito_nao_me_perturbe"] is False
    assert res_free["seguro_para_discagem_fria"] is True
    assert res_free["risco_multa"] == "BAIXO"


def test_rank_mailing_telefones() -> None:
    blocks = [{"phone": "11977771111", "blocked": True, "entity": "ANATEL_FEBRABAN"}]

    candidates = [
        {
            "ddd": "11",
            "numero": "988882222",
            "is_celular": True,
            "whatsappDisponivel": True,
            "score": 0.9,
        },
        {
            "ddd": "11",
            "numero": "977771111",  # Inscrito no NMP
            "is_celular": True,
            "whatsappDisponivel": True,
            "score": 0.8,
        },
        {
            "ddd": "11",
            "numero": "966663333",
            "is_celular": True,
            "whatsappDisponivel": False,
            "score": 0.5,
        },
        {
            "ddd": "11",
            "numero": "33334444",  # Fixo
            "is_celular": False,
            "whatsappDisponivel": False,
            "score": 0.3,
        },
    ]

    mailing = rank_mailing_telefones(candidates, block_records=blocks, max_count=3)
    assert len(mailing) == 3

    # O primeiro deve ser o que tem WhatsApp ativo e livre de Não Me Perturbe
    top1 = mailing[0]
    assert top1["numeroRaw"] == "11988882222"
    assert top1["whatsappDisponivel"] is True
    assert top1["naoMePerturbe"]["inscrito_nao_me_perturbe"] is False
    assert top1["ordemRecomendada"] == 1
    assert top1["operadora"] in ("VIVO", "CLARO", "TIM")

    # Verificar que o número bloqueado foi penalizado ou rotulado
    blocked_item = next((item for item in mailing if item["numeroRaw"] == "11977771111"), None)
    if blocked_item:
        assert blocked_item["naoMePerturbe"]["inscrito_nao_me_perturbe"] is True
        assert blocked_item["recomendacao"] == "APENAS_WHATSAPP_COMPLIANCE"
