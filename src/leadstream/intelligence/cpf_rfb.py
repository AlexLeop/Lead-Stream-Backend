from __future__ import annotations

from typing import Any

# =============================================================================
# REGIÕES HISTORICAMENTE ASSOCIADAS AO 9º DÍGITO DO CPF
# =============================================================================
# Esse metadado não representa endereço, residência ou domicílio fiscal atual.
# =============================================================================

REGIOES_FISCAIS_RFB: dict[str, dict[str, Any]] = {
    "1": {
        "codigo": "1",
        "regiao": "1ª Região Fiscal",
        "ufs": ["DF", "GO", "MT", "MS", "TO"],
        "sede": "Brasília / DF",
        "jurisdicao": "Distrito Federal, Goiás, Mato Grosso, Mato Grosso do Sul e Tocantins",
    },
    "2": {
        "codigo": "2",
        "regiao": "2ª Região Fiscal",
        "ufs": ["AC", "AP", "AM", "PA", "RO", "RR"],
        "sede": "Belém / PA",
        "jurisdicao": "Acre, Amapá, Amazonas, Pará, Rondônia e Roraima",
    },
    "3": {
        "codigo": "3",
        "regiao": "3ª Região Fiscal",
        "ufs": ["CE", "MA", "PI"],
        "sede": "Fortaleza / CE",
        "jurisdicao": "Ceará, Maranhão e Piauí",
    },
    "4": {
        "codigo": "4",
        "regiao": "4ª Região Fiscal",
        "ufs": ["AL", "PB", "PE", "RN"],
        "sede": "Recife / PE",
        "jurisdicao": "Alagoas, Paraíba, Pernambuco e Rio Grande do Norte",
    },
    "5": {
        "codigo": "5",
        "regiao": "5ª Região Fiscal",
        "ufs": ["BA", "SE"],
        "sede": "Salvador / BA",
        "jurisdicao": "Bahia e Sergipe",
    },
    "6": {
        "codigo": "6",
        "regiao": "6ª Região Fiscal",
        "ufs": ["MG"],
        "sede": "Belo Horizonte / MG",
        "jurisdicao": "Minas Gerais",
    },
    "7": {
        "codigo": "7",
        "regiao": "7ª Região Fiscal",
        "ufs": ["ES", "RJ"],
        "sede": "Rio de Janeiro / RJ",
        "jurisdicao": "Espírito Santo e Rio de Janeiro",
    },
    "8": {
        "codigo": "8",
        "regiao": "8ª Região Fiscal",
        "ufs": ["SP"],
        "sede": "São Paulo / SP",
        "jurisdicao": "São Paulo",
    },
    "9": {
        "codigo": "9",
        "regiao": "9ª Região Fiscal",
        "ufs": ["PR", "SC"],
        "sede": "Curitiba / PR",
        "jurisdicao": "Paraná e Santa Catarina",
    },
    "0": {
        "codigo": "0",
        "regiao": "10ª Região Fiscal",
        "ufs": ["RS"],
        "sede": "Porto Alegre / RS",
        "jurisdicao": "Rio Grande do Sul",
    },
}


def clean_cpf_digits(raw: str | None) -> str:
    if not raw:
        return ""
    return "".join(c for c in str(raw) if c.isdigit())


def format_cpf_display(digits: str) -> str:
    cleaned = clean_cpf_digits(digits)
    if len(cleaned) == 11:
        return f"{cleaned[:3]}.{cleaned[3:6]}.{cleaned[6:9]}-{cleaned[9:]}"
    return digits


def calculate_cpf_check_digits(base_9: str) -> tuple[str, str]:
    """Calcula os dois dígitos verificadores compatíveis com o CPF (Módulo 11)."""
    dv1, dv2, _ = calculate_cpf_check_digits_with_steps(base_9)
    return dv1, dv2


def calculate_cpf_check_digits_with_steps(
    base_9: str,
) -> tuple[str, str, dict[str, Any]]:
    """Calcula os dígitos verificadores com passos auditáveis de Módulo 11."""
    if len(base_9) != 9 or not base_9.isdigit():
        return "", "", {}

    # 1º Dígito Verificador (pesos de 10 a 2)
    pesos_1 = list(range(10, 1, -1))
    soma_1 = sum(int(digit) * weight for digit, weight in zip(base_9, pesos_1, strict=True))
    resto_1 = soma_1 % 11
    dv_1 = 0 if resto_1 < 2 else 11 - resto_1

    # 2º Dígito Verificador (pesos de 11 a 2)
    base_10 = base_9 + str(dv_1)
    pesos_2 = list(range(11, 1, -1))
    soma_2 = sum(int(digit) * weight for digit, weight in zip(base_10, pesos_2, strict=True))
    resto_2 = soma_2 % 11
    dv_2 = 0 if resto_2 < 2 else 11 - resto_2

    steps = {
        "dv1": {
            "pesos": pesos_1,
            "soma": soma_1,
            "resto": resto_1,
            "digito_calculado": str(dv_1),
            "regra": "Resto < 2 -> 0; caso contrário 11 - Resto",
        },
        "dv2": {
            "pesos": pesos_2,
            "soma": soma_2,
            "resto": resto_2,
            "digito_calculado": str(dv_2),
            "regra": "Resto < 2 -> 0; caso contrário 11 - Resto",
        },
    }
    return str(dv_1), str(dv_2), steps


def validate_cpf_with_details(cpf_input: str) -> dict[str, Any]:
    """Valida apenas formato e checksum; não consulta existência ou situação na RFB."""
    digits = clean_cpf_digits(cpf_input)
    if len(digits) != 11:
        return {
            "valido": False,
            "motivo": f"Quantidade de dígitos incorreta ({len(digits)} de 11 esperados).",
            "cpf_formatado": cpf_input,
            "cpf_numerico": digits,
            "regiao_fiscal": None,
            "auditoria_modulo_11": None,
        }

    # Verifica repetição uniforme (11111111111, 22222222222, etc.)
    if digits == digits[0] * 11:
        return {
            "valido": False,
            "motivo": "CPF composto por sequência de dígitos repetidos.",
            "cpf_formatado": format_cpf_display(digits),
            "cpf_numerico": digits,
            "regiao_fiscal": None,
            "auditoria_modulo_11": None,
        }

    base_9 = digits[:9]
    dv_informado = digits[9:11]
    dv1_exp, dv2_exp, steps = calculate_cpf_check_digits_with_steps(base_9)
    dv_esperado = f"{dv1_exp}{dv2_exp}"

    is_valid = dv_informado == dv_esperado
    non_digit_9 = digits[8]
    regiao_info = REGIOES_FISCAIS_RFB.get(non_digit_9)
    suggested_cpf = f"{base_9}{dv_esperado}"

    return {
        "valido": is_valid,
        "motivo": (
            "CPF estruturalmente compatível com o cálculo Módulo 11."
            if is_valid
            else (
                f"Dígitos verificadores incorretos "
                f"(esperado '{dv_esperado}', recebido '{dv_informado}')."
            )
        ),
        "cpf_formatado": format_cpf_display(digits),
        "cpf_numerico": digits,
        "base_cadastral_9": base_9,
        "digitos_verificadores_informados": dv_informado,
        "digitos_verificadores_calculados": dv_esperado,
        "sugestao_cpf_corrigido": format_cpf_display(suggested_cpf) if not is_valid else None,
        "regiao_fiscal_codigo": non_digit_9,
        "regiao_fiscal": regiao_info,
        "auditoria_modulo_11": steps,
    }


def lookup_cpf_fiscal_region(cpf_input: str) -> dict[str, Any] | None:
    """Retorna a região historicamente indicada pelo 9º dígito do CPF."""
    details = validate_cpf_with_details(cpf_input)
    return details.get("regiao_fiscal")
