from __future__ import annotations

import re
from typing import Any

from leadstream.validation.dns_mx import check_domain_mx

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

DISPOSABLE_DOMAINS = {
    "tempmail.com",
    "temp-mail.org",
    "mailinator.com",
    "guerrillamail.com",
    "10minutemail.com",
    "yopmail.com",
    "trashmail.com",
    "throwawaymail.com",
    "getnada.com",
}

FREE_EMAIL_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "yahoo.com",
    "yahoo.com.br",
    "uol.com.br",
    "bol.com.br",
    "terra.com.br",
    "ig.com.br",
    "globo.com",
    "icloud.com",
}

GENERIC_LOCALPARTS = {
    "contato",
    "sac",
    "atendimento",
    "comercial",
    "vendas",
    "suporte",
    "info",
    "recepcao",
    "faleconosco",
}

DEPARTMENTAL_LOCALPARTS = {
    "financeiro",
    "cobranca",
    "rh",
    "recursoshumanos",
    "administrativo",
    "juridico",
    "faturamento",
    "fiscal",
    "compras",
    "contabilidade",
}


def validate_email_syntax(email: str) -> bool:
    if not email or not isinstance(email, str):
        return False
    clean = email.strip()
    return bool(EMAIL_REGEX.match(clean))


def is_disposable_domain(domain: str) -> bool:
    if not domain:
        return False
    return domain.strip().lower() in DISPOSABLE_DOMAINS


def classify_email_type(email: str) -> str:
    if not validate_email_syntax(email):
        return "INVALIDO"
    clean = email.strip().lower()
    local_part, domain = clean.split("@", 1)

    if domain in FREE_EMAIL_DOMAINS:
        return "GRATUITO"
    if local_part in GENERIC_LOCALPARTS:
        return "GENERICO_RECEITA"
    if local_part in DEPARTMENTAL_LOCALPARTS:
        return "DEPARTAMENTAL"
    return "DIRETO_DECISOR"


def validate_email_technical(email: str, deep_smtp: bool = False) -> dict[str, Any]:
    clean = (email or "").strip().lower()
    if not validate_email_syntax(clean):
        return {
            "endereco": clean,
            "tipo": "INVALIDO",
            "status": "INVALIDO",
            "mx_found": False,
            "smtp_check": False,
            "disposable": False,
            "catch_all": False,
            "score_confiabilidade": 0.0,
        }

    _, domain = clean.split("@", 1)
    disposable = is_disposable_domain(domain)
    if disposable:
        return {
            "endereco": clean,
            "tipo": "DESCARTAVEL",
            "status": "INDELIVERAVEL",
            "mx_found": False,
            "smtp_check": False,
            "disposable": True,
            "catch_all": False,
            "score_confiabilidade": 0.0,
        }

    tipo = classify_email_type(clean)

    if deep_smtp:
        from leadstream.validation.smtp_probe import DeliverabilityStatus, verify_email_smtp_deep

        smtp_res = verify_email_smtp_deep(clean)
        is_deliv = bool(smtp_res["is_deliverable"])
        if is_deliv:
            status = "ENTREGAVEL_VALIDADO" if tipo == "DIRETO_DECISOR" else "ENTREGAVEL"
        elif smtp_res["status"] == DeliverabilityStatus.UNDELIVERABLE_MAILBOX_NOT_FOUND:
            status = "INDELIVERAVEL"
        else:
            status = "RISCO_CATCH_ALL"
        return {
            "endereco": clean,
            "tipo": tipo,
            "status": status,
            "mx_found": smtp_res["mx_server"] is not None,
            "smtp_check": is_deliv,
            "disposable": False,
            "catch_all": smtp_res["is_catch_all"],
            "score_confiabilidade": smtp_res["score_confiabilidade"],
            "smtp_details": smtp_res,
        }

    mx_info = check_domain_mx(domain)
    mx_found = mx_info["mx_found"]

    status = "ENTREGAVEL" if mx_found else "INDELIVERAVEL"
    if tipo == "DIRETO_DECISOR" and mx_found:
        status = "ENTREGAVEL_VALIDADO"

    score = 0.98 if (mx_found and tipo != "GRATUITO") else (0.85 if mx_found else 0.1)

    return {
        "endereco": clean,
        "tipo": tipo,
        "status": status,
        "mx_found": mx_found,
        "smtp_check": mx_found,
        "disposable": False,
        "catch_all": False,
        "score_confiabilidade": score,
    }
