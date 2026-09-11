from __future__ import annotations

from typing import Any


def calculate_lead_score(
    is_active: bool = True,
    has_decision_maker: bool = False,
    has_verified_email: bool = False,
    has_verified_phone: bool = False,
    porte_sebrae: str = "MICRO_EMPRESA",
    regime_tributario: str = "SIMPLES_NACIONAL",
) -> dict[str, Any]:
    score = 0
    tags: list[str] = []

    # 1. Situação Cadastral
    if is_active:
        score += 30
        tags.append("Empresa Ativa")
    else:
        tags.append("Inapta/Baixada")

    # 2. Decisor Mapeado
    if has_decision_maker:
        score += 25
        tags.append("Decisor Mapeado")

    # 3. Email direto verificado
    if has_verified_email:
        score += 25
        tags.append("Email Verificado")

    # 4. Telefone / WhatsApp
    if has_verified_phone:
        score += 20
        tags.append("WhatsApp Ativo")

    # Temperature
    if score >= 80:
        temperature = "HOT"
        tags.append("Target SDR")
    elif score >= 50:
        temperature = "WARM"
    else:
        temperature = "COLD"

    # ICP Fit calculation
    icp_fit = float(score)
    if porte_sebrae in ("MEDIA_EMPRESA", "GRANDE_EMPRESA"):
        icp_fit = min(100.0, icp_fit * 1.1)
        if is_active and (has_decision_maker or has_verified_phone):
            tags.append("Tier 1")
    elif porte_sebrae == "MEI":
        icp_fit = max(10.0, icp_fit * 0.85)

    if regime_tributario:
        tags.append(regime_tributario.replace("_", " ").title())

    return {
        "lead_score": score,
        "lead_temperature": temperature,
        "ideal_customer_profile_fit": round(icp_fit, 1),
        "tags": sorted(list(set(tags))),
    }
