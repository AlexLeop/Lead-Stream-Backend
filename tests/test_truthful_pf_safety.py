from __future__ import annotations

import httpx
import pytest
from django.test import override_settings

from leadstream.intelligence.consignado import (
    evaluate_filtro_perda,
    evaluate_nao_me_perturbe,
    get_inss_species_info,
)
from leadstream.providers.adapters.bigdatacorp_person import BigDataCorpPersonAdapter
from leadstream.validation.phone_check import format_e164_br, validate_phone_technical
from leadstream.validation.whatsapp_probe import format_e164_whatsapp_br


def test_unknown_signals_never_become_eligible_or_safe() -> None:
    loss_filter = evaluate_filtro_perda(None, None, None)
    assert loss_filter["status"] == "INCONCLUSIVO"
    assert loss_filter["elegivel_consignado"] is False

    nmp = evaluate_nao_me_perturbe("11999999999", None)
    assert nmp["status_consulta"] == "NAO_CONSULTADO"
    assert nmp["inscrito_nao_me_perturbe"] is None
    assert nmp["seguro_para_discagem_fria"] is False

    assert get_inss_species_info("9999")["elegivel"] is False


def test_local_phone_without_ddd_is_not_rewritten_as_sao_paulo() -> None:
    assert format_e164_br("99999-0000") == "99999-0000"
    assert format_e164_whatsapp_br("99999-0000") == "999990000"
    result = validate_phone_technical("99999-0000")
    assert result["ddd"] is None
    assert result["formato_valido"] is False
    assert result["validado"] is False


@pytest.mark.django_db
def test_provider_preserves_explicit_false_and_drops_raw_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "BasicData": {"Name": "Pessoa Teste", "IsDeceased": False},
                    "EmploymentRelationships": [
                        {"EmployerName": "Empresa", "IsActive": False}
                    ],
                    "DoNotCall": [{"Phone": "11999999999", "Blocked": False}],
                }
            ],
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with override_settings(
        BIGDATACORP_ACCESS_TOKEN="token",
        BIGDATACORP_TOKEN_ID="token-id",
    ):
        result = BigDataCorpPersonAdapter(client=client).enrich_cpf("52998224725")

    assert result["dados_cadastrais"]["is_deceased"] is False
    assert result["vinculos_empregaticios"][0]["ativo"] is False
    assert result["bloqueios_nao_perturbe"][0]["blocked"] is False
    assert result["nao_me_perturbe_consultado"] is True
    assert "raw_response" not in result
