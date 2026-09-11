from __future__ import annotations

from typing import Any


def format_currency_brl(value: float | None) -> str:
    if value is None:
        value = 0.0
    val_abs = abs(value)
    # Format with dot for thousands and comma for cents
    formatted_num = f"{val_abs:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    prefix = "-" if value < 0 else ""
    return f"{prefix}R$ {formatted_num}"


def infer_revenue_range(faturamento: float) -> str:
    if faturamento <= 81000.0:
        return "Até R$ 81.000"
    if faturamento <= 360000.0:
        return "R$ 81.000 a R$ 360.000"
    if faturamento <= 4800000.0:
        return "R$ 360.000 a R$ 4.800.000"
    if faturamento <= 20000000.0:
        return "R$ 4.800.000 a R$ 20.000.000"
    if faturamento <= 50000000.0:
        return "R$ 20.000.000 a R$ 50.000.000"
    if faturamento <= 300000000.0:
        return "R$ 50.000.000 a R$ 300.000.000"
    return "Acima de R$ 300.000.000"


def infer_employee_count(porte_sebrae: str, capital_social: float) -> tuple[int, str]:
    if porte_sebrae == "MEI":
        return 1, "Até 1 colaborador"
    if porte_sebrae == "MICRO_EMPRESA":
        count = 3 if capital_social > 20000 else 1
        return count, "2 a 9 colaboradores" if count > 1 else "Até 1 colaborador"
    if porte_sebrae == "PEQUENA_EMPRESA":
        count = min(49, max(10, int(capital_social / 20000))) if capital_social else 15
        return count, "10 a 49 colaboradores"
    if porte_sebrae == "MEDIA_EMPRESA":
        count = min(249, max(50, int(capital_social / 30000))) if capital_social else 84
        return count, "51 a 100 colaboradores" if count <= 100 else "101 a 250 colaboradores"
    # GRANDE_EMPRESA
    count = max(250, int(capital_social / 50000)) if capital_social else 350
    return count, "Mais de 250 colaboradores"


def infer_economics(
    capital_social: float | None = 0.0,
    porte_rfb: str | None = None,
    optante_mei: bool | None = False,
    optante_simples: bool | None = False,
    cnae_code: str | None = None,
) -> dict[str, Any]:
    cap = capital_social if capital_social is not None else 0.0
    is_mei = bool(optante_mei)
    is_simples = bool(optante_simples)

    # 1. Regime Tributário
    if is_mei:
        regime = "SIMEI"
        porte_sebrae = "MEI"
        # MEI limit is R$ 81.000 / year. Est faturamento between 30k and 81k.
        faturamento_est = min(81000.0, max(24000.0, cap * 4.0 if cap > 0 else 60000.0))
    elif is_simples:
        regime = "SIMPLES_NACIONAL"
        if porte_rfb in ("1", "ME", "01") or cap <= 100000.0:
            porte_sebrae = "MICRO_EMPRESA"
            faturamento_est = max(120000.0, min(360000.0, cap * 5.0 if cap > 0 else 240000.0))
        else:
            porte_sebrae = "PEQUENA_EMPRESA"
            faturamento_est = max(400000.0, min(4800000.0, cap * 4.0 if cap > 0 else 1200000.0))
    else:
        # Non-simples (Lucro Presumido ou Lucro Real)
        if cap >= 2000000.0 or porte_rfb in ("5", "DEMAIS"):
            if cap >= 50000000.0:
                porte_sebrae = "GRANDE_EMPRESA"
                regime = "LUCRO_REAL"
                faturamento_est = max(300000000.0, cap * 3.5)
            elif cap >= 500000.0:
                porte_sebrae = "MEDIA_EMPRESA"
                regime = "LUCRO_REAL" if cap >= 2000000.0 else "LUCRO_PRESUMIDO"
                faturamento_est = max(5000000.0, cap * 5.0)
            else:
                porte_sebrae = "PEQUENA_EMPRESA"
                regime = "LUCRO_PRESUMIDO"
                faturamento_est = max(500000.0, cap * 6.0 if cap > 0 else 1500000.0)
        else:
            porte_sebrae = "MICRO_EMPRESA" if cap <= 50000.0 else "PEQUENA_EMPRESA"
            regime = "LUCRO_PRESUMIDO"
            faturamento_est = max(250000.0, cap * 5.0 if cap > 0 else 600000.0)

    faixa_fat = infer_revenue_range(faturamento_est)
    qtd_func, faixa_func = infer_employee_count(porte_sebrae, cap)

    return {
        "porte_sebrae": porte_sebrae,
        "regime_tributario": regime,
        "capital_social": cap,
        "capital_social_formatado": format_currency_brl(cap),
        "faturamento_estimado_anual": round(faturamento_est, 2),
        "faixa_faturamento": faixa_fat,
        "quantidade_funcionarios_estimada": qtd_func,
        "faixa_funcionarios": faixa_func,
    }
