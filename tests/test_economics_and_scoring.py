from __future__ import annotations

from leadstream.intelligence.economics import (
    format_currency_brl,
    infer_economics,
)
from leadstream.intelligence.scoring import calculate_lead_score


def test_format_currency_brl():
    assert format_currency_brl(10.0) == "R$ 10,00"
    assert format_currency_brl(2500000.00) == "R$ 2.500.000,00"
    assert format_currency_brl(0.0) == "R$ 0,00"


def test_economics_inference_for_mei():
    eco = infer_economics(
        capital_social=10.0,
        porte_rfb="1",
        optante_mei=True,
        optante_simples=True,
        cnae_code="8599603",
    )
    assert eco["porte_sebrae"] == "MEI"
    assert eco["regime_tributario"] == "SIMEI"
    assert eco["faturamento_estimado_anual"] <= 81000.00
    assert "Até R$ 81.000" in eco["faixa_faturamento"]
    assert eco["quantidade_funcionarios_estimada"] in (1, 0)
    assert "1" in eco["faixa_funcionarios"] or "Até" in eco["faixa_funcionarios"]


def test_economics_inference_for_large_enterprise():
    eco = infer_economics(
        capital_social=2500000.00,
        porte_rfb="5",  # DEMAIS
        optante_mei=False,
        optante_simples=False,
        cnae_code="6202300",
    )
    assert eco["porte_sebrae"] in ("MEDIA_EMPRESA", "GRANDE_EMPRESA")
    assert eco["regime_tributario"] == "LUCRO_REAL"
    assert eco["faturamento_estimado_anual"] >= 5000000.00
    assert eco["quantidade_funcionarios_estimada"] > 20


def test_lead_score_calculation_hot():
    score_data = calculate_lead_score(
        is_active=True,
        has_decision_maker=True,
        has_verified_email=True,
        has_verified_phone=True,
        porte_sebrae="MEDIA_EMPRESA",
        regime_tributario="LUCRO_REAL",
    )
    assert score_data["lead_score"] == 100
    assert score_data["lead_temperature"] == "HOT"
    assert score_data["ideal_customer_profile_fit"] >= 90.0
    assert "WhatsApp Ativo" in score_data["tags"]
    assert "Decisor Mapeado" in score_data["tags"]


def test_lead_score_calculation_cold():
    score_data = calculate_lead_score(
        is_active=False,
        has_decision_maker=False,
        has_verified_email=False,
        has_verified_phone=False,
        porte_sebrae="MEI",
        regime_tributario="SIMEI",
    )
    assert score_data["lead_score"] == 0
    assert score_data["lead_temperature"] == "COLD"
    assert score_data["ideal_customer_profile_fit"] < 50.0
    assert "Inapta/Baixada" in score_data["tags"]
