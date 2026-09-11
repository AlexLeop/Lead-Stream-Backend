from __future__ import annotations

import pytest

from leadstream.entities.normalization import (
    DataValidationError,
    cnpj_root,
    fingerprint_value,
    normalize_cnpj,
    normalize_domain,
    normalize_email,
    normalize_linkedin_url,
    normalize_phone_br,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("04.252.011/0001-10", "04252011000110"),
        ("11.222.333/0001-81", "11222333000181"),
    ],
)
def test_normaliza_cnpj_e_valida_digitos(raw: str, expected: str) -> None:
    assert normalize_cnpj(raw) == expected
    assert normalize_cnpj(expected) == expected
    assert cnpj_root(raw) == expected[:8]


@pytest.mark.parametrize("raw", ["", "00.000.000/0000-00", "04.252.011/0001-11", "123"])
def test_rejeita_cnpj_invalido(raw: str) -> None:
    with pytest.raises(DataValidationError, match="CNPJ inválido"):
        normalize_cnpj(raw)


def test_normaliza_email_e_dominio_internacional() -> None:
    assert normalize_email("  DECISOR@Exemplo.COM.BR ") == "decisor@exemplo.com.br"
    assert normalize_domain("https://www.Ação.com.br/contato") == "xn--ao-siap.com.br"


@pytest.mark.parametrize("raw", ["sem-arroba", "a@localhost", "https://localhost"])
def test_rejeita_email_ou_dominio_invalido(raw: str) -> None:
    function = normalize_email if "https" not in raw else normalize_domain
    with pytest.raises(DataValidationError):
        function(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("(11) 99876-5432", "+5511998765432"),
        ("+55 11 3456-7890", "+551134567890"),
    ],
)
def test_normaliza_telefone_sem_inferir_whatsapp(raw: str, expected: str) -> None:
    assert normalize_phone_br(raw) == expected


def test_fingerprint_json_independe_da_ordem_das_chaves() -> None:
    assert fingerprint_value({"b": 2, "a": 1}) == fingerprint_value({"a": 1, "b": 2})


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://br.linkedin.com/in/alexleop/en", "https://linkedin.com/in/alexleop"),
        ("https://br.linkedin.com/in/alexleop/en/", "https://linkedin.com/in/alexleop"),
        ("https://www.linkedin.com/in/alexleop/pt-br", "https://linkedin.com/in/alexleop"),
        ("https://linkedin.com/in/alexleop/es?trk=profile", "https://linkedin.com/in/alexleop"),
        ("https://br.linkedin.com/in/alexleop", "https://linkedin.com/in/alexleop"),
        ("http://LinkedIn.com/in/joao/", "https://linkedin.com/in/joao"),
        ("https://linkedin.com/in/carlos", "https://linkedin.com/in/carlos"),
        (
            "https://br.linkedin.com/company/leadstream/about",
            "https://linkedin.com/company/leadstream",
        ),
    ],
)
def test_normaliza_linkedin_url_remove_siglas_pais_e_lingua(raw: str, expected: str) -> None:
    assert normalize_linkedin_url(raw) == expected

