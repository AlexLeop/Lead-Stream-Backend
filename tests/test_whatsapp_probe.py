from __future__ import annotations

import httpx
from django.test import override_settings

from leadstream.validation.whatsapp_probe import (
    format_display_phone_br,
    format_e164_whatsapp_br,
    is_whatsapp_probe_configured,
    verify_whatsapp_active,
)


def test_format_e164_whatsapp_br() -> None:
    # 11 dígitos com DDD
    assert format_e164_whatsapp_br("11996260135") == "5511996260135"
    # Com formatação e DDI já presente
    assert format_e164_whatsapp_br("+55 (21) 99626-0135") == "5521996260135"
    # 9 dígitos com DDD separado
    assert format_e164_whatsapp_br("99626-0135", ddd="21") == "5521996260135"
    # Vazio
    assert format_e164_whatsapp_br("") == ""


def test_format_display_phone_br() -> None:
    assert format_display_phone_br("5511996260135") == "(11) 99626-0135"
    assert format_display_phone_br("552132908800") == "(21) 3290-8800"


def test_whatsapp_probe_not_configured_returns_unavailable() -> None:
    """Sem credenciais, NÃO DEVE simular dados: deve reportar status explícito de INDISPONIVEL."""
    with override_settings(WHATSAPP_PROBE_URL=None, WHATSAPP_PROBE_API_KEY=None):
        assert is_whatsapp_probe_configured() is False
        res = verify_whatsapp_active("11996260135")
        assert res["configurado"] is False
        assert res["disponivel"] is False
        assert res["status"] == "INDISPONIVEL"
        assert res["tem_whatsapp"] is False
        assert "não está configurado" in res["detalhes"]


def test_whatsapp_probe_invalid_number() -> None:
    res = verify_whatsapp_active("123")
    assert res["sucesso"] is False
    assert res["status"] == "NUMERO_INVALIDO"
    assert res["tem_whatsapp"] is False


def test_whatsapp_probe_evolution_active_success() -> None:
    """Simula resposta real da Evolution API / EvolutionGo com conta ativa."""

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "whatsappNumbers" in url_str:
            return httpx.Response(
                200,
                json=[
                    {
                        "exists": True,
                        "jid": "5511996260135@s.whatsapp.net",
                        "number": "5511996260135",
                        "isBusiness": True,
                    }
                ],
            )
        if "fetchProfilePictureUrl" in url_str:
            return httpx.Response(
                200, json={"profilePictureUrl": "https://pps.whatsapp.net/v/photo.jpg"}
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    mock_client = httpx.Client(transport=transport)

    with override_settings(
        WHATSAPP_PROBE_URL="https://evolution.teste.local",
        WHATSAPP_PROBE_API_KEY="secret-token-123",
        WHATSAPP_PROBE_INSTANCE="leadstream",
        WHATSAPP_PROBE_PROVIDER="evolution",
    ):
        res = verify_whatsapp_active("11996260135", client=mock_client)
        assert res["configurado"] is True
        assert res["disponivel"] is True
        assert res["sucesso"] is True
        assert res["tem_whatsapp"] is True
        assert res["status"] == "VALIDADO_ATIVO"
        assert res["tipo_conta"] == "WHATSAPP_BUSINESS"
        assert res["jid"] == "5511996260135@s.whatsapp.net"
        assert res["numero_formatado"] == "(11) 99626-0135"
        assert res["foto_perfil"] == "https://pps.whatsapp.net/v/photo.jpg"


def test_whatsapp_probe_evolution_number_not_exists() -> None:
    """Simula resposta real quando o número não tem conta no WhatsApp."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[{"exists": False, "number": "5511999999999"}],
        )

    transport = httpx.MockTransport(handler)
    mock_client = httpx.Client(transport=transport)

    with override_settings(
        WHATSAPP_PROBE_URL="https://evolution.teste.local",
        WHATSAPP_PROBE_API_KEY="secret-token-123",
        WHATSAPP_PROBE_INSTANCE="leadstream",
        WHATSAPP_PROBE_PROVIDER="evolution",
    ):
        res = verify_whatsapp_active("11999999999", client=mock_client)
        assert res["disponivel"] is True
        assert res["sucesso"] is True
        assert res["tem_whatsapp"] is False
        assert res["status"] == "SEM_CONTA_WHATSAPP"
        assert res["tipo_conta"] == "NENHUMA"
        assert res["jid"] is None
