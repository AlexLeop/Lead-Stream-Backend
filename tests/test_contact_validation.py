from __future__ import annotations

from leadstream.validation.email_check import (
    classify_email_type,
    is_disposable_domain,
    validate_email_syntax,
    validate_email_technical,
)
from leadstream.validation.phone_check import (
    format_e164_br,
    validate_phone_technical,
)


def test_validate_email_syntax():
    assert validate_email_syntax("contato@empresa.com.br") is True
    assert validate_email_syntax("invalido@") is False
    assert validate_email_syntax("sem_arroba.com") is False


def test_is_disposable_domain():
    assert is_disposable_domain("tempmail.com") is True
    assert is_disposable_domain("mailinator.com") is True
    assert is_disposable_domain("gmail.com") is False
    assert is_disposable_domain("outlook.com") is False


def test_classify_email_type():
    assert classify_email_type("contato@empresa.com.br") == "GENERICO_RECEITA"
    assert classify_email_type("financeiro@empresa.com.br") == "DEPARTAMENTAL"
    assert classify_email_type("alexandre.leopoldo@empresa.com.br") == "DIRETO_DECISOR"
    assert classify_email_type("usuario@gmail.com") == "GRATUITO"


def test_email_technical_validation():
    res = validate_email_technical("lx.leopoldo@outlook.com")
    assert res["endereco"] == "lx.leopoldo@outlook.com"
    assert res["status"] in ("ENTREGAVEL", "ENTREGAVEL_VALIDADO")
    assert res["mx_found"] is True
    assert res["disposable"] is False


def test_format_e164_br():
    assert (
        format_e164_br("2196260135") == "+55 21 99626-0135"
        or format_e164_br("21996260135") == "+55 21 99626-0135"
    )
    assert format_e164_br("1132908800") == "+55 11 3290-8800"


def test_phone_validation_mobile():
    res = validate_phone_technical("996260135", ddd="21")
    assert res["tipo"] in ("MOVEL_WHATSAPP_EMPRESA", "MOVEL")
    assert res["ddd"] == "21"
    assert res["numero"] == "996260135"
    assert "-" not in res["numero"]
    assert "+" not in res["numero"]
    assert " " not in res["numero"]
    assert res["whatsapp_status"]["tem_whatsapp"] is True
    assert res["status_linha"] == "ATIVA"


def test_phone_validation_fixed():
    res = validate_phone_technical("32908800", ddd="11")
    assert res["tipo"] == "FIXO_RECEITA"
    assert res["ddd"] == "11"
    assert res["numero"] == "32908800"
    assert "-" not in res["numero"]
    assert "+" not in res["numero"]
    assert " " not in res["numero"]
    assert res["whatsapp_status"]["tem_whatsapp"] is False


def test_phone_validation_no_special_chars():
    # Test with formatted/dirty strings (+55, parentheses, hyphens, spaces)
    res = validate_phone_technical("+55 (21) 9626-0135")
    assert res["ddd"] == "21"
    assert res["numero"] == "96260135"
    assert "-" not in res["numero"]
    assert "+" not in res["numero"]
    assert " " not in res["numero"]
    assert "-" not in res["ddd"]
    assert "+" not in res["ddd"]
    assert " " not in res["ddd"]
