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


@pytest.mark.django_db
def test_provider_parses_official_envelope_and_complete_person_profile() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/ondemand"):
            return httpx.Response(
                200,
                json={
                    "Result": [
                        {
                            "OnlineQueries": [
                                {
                                    "QueryResultData": {
                                        "RegistrationNumber": "123456789012",
                                        "Status": "REGULAR",
                                        "PollingPlace.LocationName": "ESCOLA MUNICIPAL",
                                        "PollingPlace.Zone": "10",
                                        "PollingPlace.Section": "123",
                                    }
                                }
                            ]
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "QueryId": "query-123",
                "Result": [
                    {
                        "BasicData": {
                            "Name": "PESSOA COMPLETA",
                            "BirthDate": "1980-01-02T00:00:00",
                            "MotherName": "MAE COMPLETA",
                            "FatherName": "PAI COMPLETO",
                            "Gender": "F",
                            "MaritalStatusData": {"Status": "CASADO"},
                            "TaxIdStatus": "REGULAR",
                            "TaxIdOrigin": "RECEITA FEDERAL",
                        },
                        "ExtendedPhones": {
                            "Phones": [
                                {
                                    "AreaCode": "11",
                                    "Number": "999999999",
                                    "Type": "MOBILE",
                                    "IsMainForEntity": True,
                                    "CurrentCarrier": "VIVO",
                                }
                            ]
                        },
                        "ExtendedAddresses": {
                            "Addresses": [
                                {
                                    "AddressMain": "RUA UM",
                                    "Number": "10",
                                    "City": "SAO PAULO",
                                    "State": "SP",
                                    "ZipCode": "01001000",
                                    "IsMainForEntity": True,
                                }
                            ]
                        },
                        "FinantialData": {
                            "TaxReturns": [
                                {
                                    "Year": 2025,
                                    "Bank": "BANCO EXEMPLO",
                                    "Branch": "0001",
                                }
                            ]
                        },
                        "FinancialRisk": {
                            "IsCurrentlyOnCollection": True,
                            "Protests": 2,
                            "BadChecks": 1,
                        },
                        "ExtendedSocialAssistancePrograms": {
                            "SocialAssistances": [
                                {"ProgramName": "BOLSA FAMILIA", "Status": "ATIVO"}
                            ]
                        },
                        "UniversityStudentData": {
                            "EducationHistory": [{"Level": "GRADUATE"}]
                        },
                    }
                ],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with override_settings(
        BIGDATACORP_ACCESS_TOKEN="token",
        BIGDATACORP_TOKEN_ID="token-id",
        BIGDATACORP_PERSON_ONDEMAND_DATASETS="ondemand_tse_polling_place_person",
    ):
        result = BigDataCorpPersonAdapter(client=client).enrich_cpf("52998224725")

    cadastral = result["dados_cadastrais"]
    assert cadastral["nome"] == "PESSOA COMPLETA"
    assert cadastral["nome_pai"] == "PAI COMPLETO"
    assert cadastral["estado_civil"] == "CASADO"
    assert cadastral["instrucao"] == "GRADUATE"
    assert cadastral["origem_cpf"] == "RECEITA FEDERAL"
    assert result["telefones"][0]["operadora"] == "VIVO"
    assert result["enderecos"][0]["municipio"] == "SAO PAULO"
    assert result["restricoes_financeiras"]["protestos"] == 2
    assert result["restricoes_financeiras"]["cheques_sem_fundo"] == 1
    assert result["relacionamentos_bancarios"][0]["instituicao"] == "BANCO EXEMPLO"
    assert result["beneficios_sociais"][0]["programa"] == "BOLSA FAMILIA"
    assert result["dados_eleitorais"]["titulo_eleitor"] == "123456789012"
    assert result["metadados_provedor"]["query_id"] == "query-123"
