from __future__ import annotations

from typing import Any


def clean_phone_digits(value: str) -> str:
    return "".join(c for c in value if c.isdigit())


def get_phone_operator_hint(ddd: str, prefix: str) -> str:
    """Não deduz operadora pelo prefixo: portabilidade torna essa inferência insegura."""
    _ = (ddd, prefix)
    return "DESCONHECIDA"


def format_e164_br(phone: str, ddd: str = "") -> str:
    digits = clean_phone_digits(phone)
    if not digits:
        return ""

    clean_ddd = clean_phone_digits(ddd)

    # Strip country code 55 if already present
    if digits.startswith("55") and len(digits) in (12, 13):
        digits = digits[2:]

    # If DDD was not provided or phone already contains it
    if len(digits) in (10, 11):
        detected_ddd = digits[:2]
        number_part = digits[2:]
    elif len(digits) in (8, 9):
        detected_ddd = clean_ddd
        number_part = digits
    else:
        detected_ddd = clean_ddd if clean_ddd else ""
        number_part = digits

    if len(number_part) == 9:
        # 9xxxx-xxxx
        formatted_num = f"{number_part[:5]}-{number_part[5:]}"
    elif len(number_part) == 8:
        # xxxx-xxxx
        formatted_num = f"{number_part[:4]}-{number_part[4:]}"
    else:
        formatted_num = number_part

    if detected_ddd:
        return f"+55 {detected_ddd} {formatted_num}"
    return formatted_num


def validate_phone_technical(
    phone: str,
    ddd: str = "",
    is_primary: bool = False,
    run_probe: bool = False,
) -> dict[str, Any]:
    digits = clean_phone_digits(phone)
    clean_ddd = clean_phone_digits(ddd)

    if digits.startswith("55") and len(digits) in (12, 13):
        digits = digits[2:]

    if clean_ddd.startswith("0") and len(clean_ddd) == 3:
        clean_ddd = clean_ddd[1:]

    if digits.startswith("0") and len(digits) in (11, 12):
        digits = digits[1:]

    if len(digits) in (10, 11):
        detected_ddd = digits[:2]
        number_part = digits[2:]
    elif len(digits) in (8, 9):
        detected_ddd = clean_ddd
        number_part = digits
    else:
        detected_ddd = clean_ddd or ""
        number_part = digits

    is_mobile = len(number_part) == 9 and number_part.startswith("9")
    is_fixed = len(number_part) == 8 and number_part[0] in ("2", "3", "4", "5")

    operadora = get_phone_operator_hint(detected_ddd, number_part)

    if is_mobile:
        tipo = "MOVEL"
        tem_whatsapp: bool | None = None
        tipo_conta = "DESCONHECIDA"
        confianca = 0.7 if detected_ddd else 0.4
    elif is_fixed:
        tipo = "FIXO_RECEITA"
        tem_whatsapp = None
        tipo_conta = "DESCONHECIDA"
        confianca = 0.7 if detected_ddd else 0.4
    else:
        tipo = "DESCONHECIDO"
        tem_whatsapp = None
        tipo_conta = "DESCONHECIDA"
        confianca = 0.2

    wa_status: dict[str, Any] = {
        "tem_whatsapp": tem_whatsapp,
        "tipo_conta": tipo_conta,
        "foto_perfil": None,
        "recado": None,
        "verificado_em": None,
        "probe_executado": False,
    }

    if run_probe:
        from leadstream.validation.whatsapp_probe import verify_whatsapp_active

        probe_res = verify_whatsapp_active(phone, ddd=detected_ddd)
        if probe_res.get("disponivel"):
            wa_status["tem_whatsapp"] = bool(probe_res.get("tem_whatsapp"))
            wa_status["tipo_conta"] = str(probe_res.get("tipo_conta") or "NENHUMA")
            wa_status["foto_perfil"] = probe_res.get("foto_perfil")
            wa_status["recado"] = probe_res.get("recado")
            wa_status["verificado_em"] = probe_res.get("verificado_em")
            wa_status["probe_executado"] = True
            wa_status["validado"] = bool(probe_res.get("sucesso"))
            wa_status["jid"] = probe_res.get("jid")
            if probe_res.get("tem_whatsapp"):
                confianca = 1.0
            else:
                confianca = 0.5

    return {
        "tipo": tipo,
        "ddd": detected_ddd or None,
        "numero": number_part,
        "ramal": None,
        "operadora": operadora,
        "status_linha": "DESCONHECIDA",
        "principal": is_primary,
        "formato_valido": bool(detected_ddd and (is_mobile or is_fixed)),
        "validado": bool(wa_status.get("validado", False)),
        "whatsapp_status": wa_status,
        "confianca": confianca,
    }
