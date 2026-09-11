from __future__ import annotations

import re
from typing import Any


def clean_phone_digits(value: str) -> str:
    return "".join(c for c in str(value) if c.isdigit())


def get_phone_operator_hint(ddd: str, prefix: str) -> str:
    first_char = prefix[0] if prefix else ""
    if first_char in ("6", "7"):
        return "CLARO"
    if first_char in ("8", "9"):
        return "VIVO"
    if first_char in ("4", "5"):
        return "TIM"
    return "OI" if first_char in ("2", "3") else "DESCONHECIDA"


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
        detected_ddd = clean_ddd if clean_ddd else "11"
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
    phone: str, ddd: str = "", is_primary: bool = False
) -> dict[str, Any]:
    digits = clean_phone_digits(phone)
    clean_ddd = clean_phone_digits(ddd)

    if digits.startswith("55") and len(digits) in (12, 13):
        digits = digits[2:]

    if len(digits) in (10, 11):
        detected_ddd = digits[:2]
        number_part = digits[2:]
    elif len(digits) in (8, 9):
        detected_ddd = clean_ddd or "11"
        number_part = digits
    else:
        detected_ddd = clean_ddd or ""
        number_part = digits

    is_mobile = len(number_part) == 9 and number_part.startswith("9")
    is_fixed = len(number_part) == 8 and number_part[0] in ("2", "3", "4", "5")

    formatted = format_e164_br(number_part, ddd=detected_ddd)
    operadora = get_phone_operator_hint(detected_ddd, number_part)

    if is_mobile:
        tipo = "MOVEL_WHATSAPP_EMPRESA"
        tem_whatsapp = True
        tipo_conta = "WHATSAPP_BUSINESS"
        confianca = 0.95
    elif is_fixed:
        tipo = "FIXO_RECEITA"
        tem_whatsapp = False
        tipo_conta = "NENHUMA"
        confianca = 0.90
    else:
        tipo = "FIXO_COMERCIAL"
        tem_whatsapp = False
        tipo_conta = "NENHUMA"
        confianca = 0.70

    return {
        "tipo": tipo,
        "numero": formatted,
        "ramal": None,
        "operadora": operadora,
        "status_linha": "ATIVA",
        "principal": is_primary,
        "validado": True,
        "whatsapp_status": {
            "tem_whatsapp": tem_whatsapp,
            "tipo_conta": tipo_conta,
            "foto_perfil": None,
            "recado": None,
        },
        "confianca": confianca,
    }
