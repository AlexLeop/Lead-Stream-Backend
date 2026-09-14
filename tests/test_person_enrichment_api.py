from __future__ import annotations

import httpx
import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from leadstream.canonical.contracts import CanonicalPersonPayload
from leadstream.entities.models import ContactPoint, Person
from leadstream.providers.live_enrichment_person import (
    enrich_person_live,
    validate_cpf_format_and_dv,
)
from leadstream.tenancy.models import Tenant


@pytest.mark.django_db
def test_validate_cpf_format_and_dv() -> None:
    # CPF válido
    is_valid, exp, rec, _ = validate_cpf_format_and_dv("52998224725")
    assert is_valid is True
    assert exp == "25"
    assert rec == "25"

    # CPF com DV incorreto
    is_valid, exp, rec, suggested = validate_cpf_format_and_dv("52998224700")
    assert is_valid is False
    assert exp == "25"
    assert rec == "00"
    assert suggested == "52998224725"

    # CPF com dígitos repetidos
    is_valid, _, _, _ = validate_cpf_format_and_dv("11111111111")
    assert is_valid is False

    # CPF com tamanho menor
    is_valid, _, _, _ = validate_cpf_format_and_dv("12345")
    assert is_valid is False


@pytest.mark.django_db
def test_enrich_person_live_invalid_dv() -> None:
    tenant = Tenant.objects.create(name="Tenant Teste", slug="tenant-teste-cpf-dv")
    res = enrich_person_live(query="529.982.247-00", tenant=tenant)
    assert res["entityType"] == "PERSON"
    assert res["person"] is None
    assert res["coverage"]["available"] == 0
    assert len(res["sections"]) == 1
    sec = res["sections"][0]
    assert sec["id"] == "validation_error"
    assert "dígitos verificadores incorretos" in sec["errorMessage"]
    assert res["costCredits"] == 0


@pytest.mark.django_db
def test_enrich_person_live_with_mock_bureau_and_probe() -> None:
    """Valida enriquecimento: Bureau (BigDataCorp PF) + WhatsApp Probe + Persistência."""
    tenant = Tenant.objects.create(name="Tenant Teste 2", slug="tenant-teste-cpf-full")

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        # Mock BigDataCorp Pessoas
        if "pessoas" in url_str:
            return httpx.Response(
                200,
                json=[
                    {
                        "BasicData": {
                            "Name": "CARLOS EDUARDO SILVA",
                            "BirthDate": "1985-04-12T00:00:00Z",
                            "Age": 41,
                            "MotherName": "MARIA DAS GRACAS SILVA",
                            "Gender": "M",
                            "TaxIdStatus": "REGULAR",
                        },
                        "PhonesExtended": [
                            {
                                "AreaCode": "11",
                                "Number": "996260135",
                                "IsMobile": True,
                                "Score": 95.0,
                                "ActivityIndicator": "ALTA",
                            }
                        ],
                    }
                ],
            )
        # Mock Evolution API
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
                200, json={"profilePictureUrl": "https://pps.whatsapp.net/v/carlos.jpg"}
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    mock_client = httpx.Client(transport=transport)

    with override_settings(
        BIGDATACORP_ACCESS_TOKEN="mock-token",
        BIGDATACORP_TOKEN_ID="mock-id",
        WHATSAPP_PROBE_URL="https://evolution.teste.local",
        WHATSAPP_PROBE_API_KEY="secret-token-123",
        WHATSAPP_PROBE_INSTANCE="leadstream",
        WHATSAPP_PROBE_PROVIDER="evolution",
    ):
        res = enrich_person_live(query="52998224725", tenant=tenant, http_client=mock_client)

        # 1. Verifica exibição clara e completa do CPF (conforme solicitado pelo usuário!)
        assert res["entityType"] == "PERSON"
        assert res["person"]["cpf"] == "529.982.247-25"
        assert res["person"]["cpfDigits"] == "52998224725"
        assert res["person"]["name"] == "CARLOS EDUARDO SILVA"
        assert res["person"]["birthDate"] == "1985-04-12"
        assert res["person"]["age"] == 41

        # 2. Verifica WhatsApp Garantido
        wa = res["whatsappGarantido"]
        assert wa is not None
        assert wa["garantido"] is True
        assert wa["numero"] == "(11) 99626-0135"
        assert wa["tipoConta"] == "WHATSAPP_BUSINESS"
        assert wa["jid"] == "5511996260135@s.whatsapp.net"
        assert wa["fotoPerfil"] == "https://pps.whatsapp.net/v/carlos.jpg"
        assert wa["linkDireto"] == "https://wa.me/5511996260135"

        # 3. Verifica persistência canônica no banco
        person = Person.objects.filter(entity__tenant=tenant).first()
        assert person is not None
        assert person.full_name == "CARLOS EDUARDO SILVA"
        # O modelo Person armazena cpf_masked para compatibilidade interna
        assert "*" in person.cpf_masked

        contact = ContactPoint.objects.filter(
            owner=person.entity, kind=ContactPoint.Kind.WHATSAPP
        ).first()
        assert contact is not None
        assert contact.status == ContactPoint.Status.CONFIRMED
        assert contact.capabilities.get("whatsapp") is True
        assert contact.capabilities.get("business") is True
        assert contact.capabilities.get("foto_perfil") == "https://pps.whatsapp.net/v/carlos.jpg"

        # 4. Créditos
        assert res["costCredits"] == 1


@pytest.mark.django_db
def test_api_enrichment_person_endpoint(api_client: APIClient) -> None:
    """Testa a view POST /api/v1/enrichment/person."""
    # 1. CPF Inválido
    res = api_client.post(
        "/api/v1/enrichment/person",
        data={"query": "123"},
        content_type="application/json",
    )
    assert res.status_code == 200
    data = res.json()
    assert data["entityType"] == "PERSON"
    assert data["person"] is None
    assert data["sections"][0]["id"] == "validation_error"

    # 2. CPF Válido (mesmo sem bureau configurado, retorna seções estruturadas sem simulação)
    with override_settings(
        BIGDATACORP_ACCESS_TOKEN=None,
        BIGDATACORP_TOKEN_ID=None,
        WHATSAPP_PROBE_URL=None,
        WHATSAPP_PROBE_API_KEY=None,
    ):
        res2 = api_client.post(
            "/api/v1/enrichment/person",
            data={"query": "52998224725"},
            content_type="application/json",
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["entityType"] == "PERSON"
        assert data2["person"]["cpf"] == "529.982.247-25"
        assert data2["whatsappGarantido"] is None
        # Confirma que há seções indicando que o bureau e o probe não estão configurados
        sec_ids = [s["id"] for s in data2["sections"]]
        assert "document_validation" in sec_ids
        assert "cadastral_data" in sec_ids
        assert "whatsapp_verified" in sec_ids


@pytest.mark.django_db
def test_api_enrichment_lookup_cpf(api_client: APIClient) -> None:
    """Testa detecção automática de CPF (11 dígitos) no GET /api/v1/enrichment/lookup."""
    res = api_client.get("/api/v1/enrichment/lookup?q=52998224725")
    assert res.status_code == 200
    data = res.json()
    assert data.get("cpf") == "529.982.247-25"
    assert "lookup-person" in data.get("id", "") or "Titular" in data.get("name", "")


@pytest.mark.django_db
def test_enrich_person_consignado_complete_flow() -> None:
    """Valida as 4 camadas: Filtro de Perda, Core Consignado, Não Me Perturbe e Mailing Top 3."""
    tenant = Tenant.objects.create(name="Tenant Consignado", slug="tenant-consignado-flow")

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "pessoas" in url_str:
            return httpx.Response(
                200,
                json=[
                    {
                        "BasicData": {
                            "Name": "SEBASTIAO FERREIRA COSTA",
                            "BirthDate": "1954-03-20T00:00:00Z",
                            "Age": 72,
                            "TaxIdStatus": "REGULAR",
                            "IsDeceased": False,
                        },
                        "PhonesExtended": [
                            {
                                "AreaCode": "11",
                                "Number": "981234567",
                                "IsMobile": True,
                                "Score": 98.0,
                            },
                            {
                                "AreaCode": "11",
                                "Number": "976543210",
                                "IsMobile": True,
                                "Score": 85.0,
                            },
                        ],
                        "SocialBenefits": [
                            {
                                "BenefitNumber": "123.456.789-0",
                                "BenefitType": "41",
                                "BenefitDescription": "Aposentadoria por Idade",
                                "BenefitValue": 3000.00,
                                "Status": "ATIVO",
                            }
                        ],
                        "DoNotCall": [
                            {
                                "Phone": "11976543210",
                                "Blocked": True,
                                "Entity": "ANATEL_FEBRABAN",
                                "Date": "2023-05-10",
                            }
                        ],
                    }
                ],
            )
        if "whatsappNumbers" in url_str:
            return httpx.Response(
                200,
                json=[
                    {
                        "exists": True,
                        "jid": "5511981234567@s.whatsapp.net",
                        "number": "5511981234567",
                        "isBusiness": False,
                    }
                ],
            )
        if "fetchProfilePictureUrl" in url_str:
            return httpx.Response(
                200, json={"profilePictureUrl": "https://pps.whatsapp.net/v/sebastiao.jpg"}
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    mock_client = httpx.Client(transport=transport)

    with override_settings(
        BIGDATACORP_ACCESS_TOKEN="mock-token",
        BIGDATACORP_TOKEN_ID="mock-id",
        WHATSAPP_PROBE_URL="https://evolution.teste.local",
        WHATSAPP_PROBE_API_KEY="secret-token-123",
        WHATSAPP_PROBE_INSTANCE="leadstream",
        WHATSAPP_PROBE_PROVIDER="evolution",
    ):
        res = enrich_person_live(query="52998224725", tenant=tenant, http_client=mock_client)

        # 1. Filtro de Perda
        fp = res["filtroPerda"]
        assert fp is not None
        assert fp["status"] == "REGULAR"
        assert fp["is_deceased"] is False
        assert fp["elegivel_consignado"] is True

        # 2. Core Consignado (Margem 35% + 5% RMC + 5% RCC = 45%)
        cons = res["consignado"]
        assert cons is not None
        assert cons["elegivel"] is True
        assert cons["salarioBase"] == 3000.00
        assert cons["margemEmprestimo35"] == 1050.00
        assert cons["margemRmcCartao5"] == 150.00
        assert cons["margemRccBeneficio5"] == 150.00
        assert cons["margemTotal45"] == 1350.00
        assert cons["especieCodigo"] == "41"
        assert cons["numeroBeneficio"] == "123.456.789-0"

        # 3. Mailing Higienizado Top 3 & Não Me Perturbe
        mailing = res["mailingTop3"]
        assert len(mailing) == 2
        # O 1º telefone deve ser o 11981234567 (com WhatsApp ativo e livre de NMP)
        top1 = mailing[0]
        assert top1["numeroRaw"] == "11981234567"
        assert top1["whatsappDisponivel"] is True
        assert top1["naoMePerturbe"]["inscrito_nao_me_perturbe"] is False
        assert top1["recomendacao"] == "DISCAGEM_E_WHATSAPP"

        # O 2º telefone deve ser o 11976543210 (inscrito no Não Me Perturbe)
        top2 = mailing[1]
        assert top2["numeroRaw"] == "11976543210"
        assert top2["naoMePerturbe"]["inscrito_nao_me_perturbe"] is True
        assert top2["naoMePerturbe"]["risco_multa"] == "ALTO"

        # 4. Cobrança de crédito
        assert res["costCredits"] == 1


@pytest.mark.django_db
def test_enrich_person_deceased_zero_credits() -> None:
    """Valida que lead com indicador de óbito é expurgado e NÃO consome créditos da carteira."""
    tenant = Tenant.objects.create(name="Tenant Obito", slug="tenant-obito-zero-cred")

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "pessoas" in url_str:
            return httpx.Response(
                200,
                json=[
                    {
                        "BasicData": {
                            "Name": "FALECIDO DA SILVA",
                            "TaxIdStatus": "REGULAR",
                            "IsDeceased": True,
                            "DeathDate": "2021-10-05T00:00:00Z",
                        },
                        "PhonesExtended": [],
                    }
                ],
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    mock_client = httpx.Client(transport=transport)

    with override_settings(
        BIGDATACORP_ACCESS_TOKEN="mock-token",
        BIGDATACORP_TOKEN_ID="mock-id",
        WHATSAPP_PROBE_URL=None,
        WHATSAPP_PROBE_API_KEY=None,
    ):
        res = enrich_person_live(query="52998224725", tenant=tenant, http_client=mock_client)
        assert res["filtroPerda"]["status"] == "EXPURGADO_OBITO"
        assert res["filtroPerda"]["is_deceased"] is True
        assert res["filtroPerda"]["elegivel_consignado"] is False
        assert res["filtroPerda"]["deve_cobrar_credito"] is False
        # GARANTIA: Zero cobrança de créditos para lead morto!
        assert res["costCredits"] == 0


@pytest.mark.django_db
def test_enrichment_catalog_has_consignado_preset(api_client: APIClient) -> None:
    """Valida presença do preset de consignado no catálogo."""
    res = api_client.get("/api/v1/enrichment/catalog")
    assert res.status_code == 200
    data = res.json()
    presets = {p["id"]: p for p in data.get("presets", [])}
    assert "consignado_premium" in presets
    assert "consignado_core" in presets["consignado_premium"]["capabilityIds"]
    assert "nao_me_perturbe" in presets["consignado_premium"]["capabilityIds"]
    assert "filtro_perda_obito" in presets["consignado_premium"]["capabilityIds"]


@pytest.mark.django_db
def test_enrich_person_cpf_14715435799_rfb_fiscal_region() -> None:
    """Valida enriquecimento e higienização matemática para o CPF 14715435799.

    7ª Região Fiscal da RFB (ES, RJ - Sede Rio de Janeiro).
    DVs Módulo 11 = '99'.
    Sem bureau configurado: zero alucinação, zero cobrança de créditos (costCredits = 0).
    """
    tenant = Tenant.objects.create(name="Tenant RJ", slug="tenant-rj-14715435799")
    with override_settings(
        BIGDATACORP_ACCESS_TOKEN=None,
        BIGDATACORP_TOKEN_ID=None,
        WHATSAPP_PROBE_URL=None,
        WHATSAPP_PROBE_API_KEY=None,
    ):
        res = enrich_person_live(query="14715435799", tenant=tenant)

        # 1. Identificação e documento
        assert res["entityType"] == "PERSON"
        assert res["person"]["cpf"] == "147.154.357-99"
        assert res["person"]["cpfDigits"] == "14715435799"
        assert res["costCredits"] == 0

        # 2. Inteligência Regional da RFB (7ª Região - RJ/ES)
        reg = res.get("regiaoFiscal")
        assert reg is not None
        assert reg["codigo"] == "7"
        assert reg["regiao"] == "7ª Região Fiscal"
        assert "RJ" in reg["ufs"] and "ES" in reg["ufs"]
        assert "Rio de Janeiro" in reg["sede"]

        # 3. Seção Document Validation
        sec_map = {s["id"]: s for s in res["sections"]}
        doc_sec = sec_map["document_validation"]
        assert doc_sec["status"] == "available"
        fields_map = {f["label"]: f["value"] for f in doc_sec["fields"]}
        assert fields_map["CPF Formatado"] == "147.154.357-99"
        assert "99" in fields_map["Módulo 11"]
        assert "7ª Região Fiscal" in fields_map["Região Fiscal RFB"]
        assert "Rio de Janeiro" in fields_map["Sede Regional"]
        assert "1º DV: Soma" in fields_map["Demonstrativo Módulo 11"]

        # 4. Canonical payload
        canonical = res.get("canonical")
        assert canonical is not None
        payload_obj = CanonicalPersonPayload.model_validate(canonical)
        assert payload_obj.document_validation.modulo_11_valido is True
        assert payload_obj.document_validation.digitos_verificadores == "99"
        assert payload_obj.document_validation.regiao_fiscal is not None
        assert payload_obj.document_validation.regiao_fiscal["codigo"] == "7"


@pytest.mark.django_db
def test_enrich_person_cpf_14715435799_with_bureau_and_probe() -> None:
    """Valida fluxo completo de enriquecimento real para o CPF 14715435799 com bureau e probe."""
    tenant = Tenant.objects.create(name="Tenant RJ Full", slug="tenant-rj-full-14715435799")

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "pessoas" in url_str:
            return httpx.Response(
                200,
                json=[
                    {
                        "BasicData": {
                            "Name": "ALEXANDRE LEOPOLDO DA SILVA",
                            "BirthDate": "1990-08-25T00:00:00Z",
                            "Age": 36,
                            "MotherName": "LUCIA LEOPOLDO",
                            "Gender": "M",
                            "TaxIdStatus": "REGULAR",
                            "IsDeceased": False,
                        },
                        "PhonesExtended": [
                            {
                                "AreaCode": "21",
                                "Number": "987654321",
                                "IsMobile": True,
                                "Score": 96.0,
                                "Carrier": "VIVO",
                            }
                        ],
                        "SocialBenefits": [
                            {
                                "BenefitNumber": "987.654.321-0",
                                "BenefitType": "42",
                                "BenefitDescription": "Aposentadoria por Tempo de Contribuicao",
                                "BenefitValue": 4500.00,
                                "Status": "ATIVO",
                            }
                        ],
                    }
                ],
            )
        if "whatsappNumbers" in url_str:
            return httpx.Response(
                200,
                json=[
                    {
                        "exists": True,
                        "jid": "5521987654321@s.whatsapp.net",
                        "number": "5521987654321",
                        "isBusiness": False,
                    }
                ],
            )
        if "fetchProfilePictureUrl" in url_str:
            return httpx.Response(
                200,
                json={"profilePictureUrl": "https://pps.whatsapp.net/v/alexandre.jpg"},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    mock_client = httpx.Client(transport=transport)

    with override_settings(
        BIGDATACORP_ACCESS_TOKEN="mock-token",
        BIGDATACORP_TOKEN_ID="mock-id",
        WHATSAPP_PROBE_URL="https://evolution.teste.local",
        WHATSAPP_PROBE_API_KEY="secret-token-123",
        WHATSAPP_PROBE_INSTANCE="leadstream",
        WHATSAPP_PROBE_PROVIDER="evolution",
    ):
        res = enrich_person_live(query="14715435799", tenant=tenant, http_client=mock_client)

        # 1. Identificação
        assert res["entityType"] == "PERSON"
        assert res["person"]["name"] == "ALEXANDRE LEOPOLDO DA SILVA"
        assert res["person"]["cpf"] == "147.154.357-99"
        assert res["costCredits"] == 1

        # 2. Região Fiscal RJ/ES
        assert res["regiaoFiscal"]["codigo"] == "7"
        assert "ES" in res["regiaoFiscal"]["ufs"]
        assert "RJ" in res["regiaoFiscal"]["ufs"]

        # 3. Consignado (Espécie 42 com R$ 4.500,00)
        cons = res["consignado"]
        assert cons["salarioBase"] == 4500.00
        assert cons["margemEmprestimo35"] == 1575.00  # 4500 * 0.35
        assert cons["margemRmcCartao5"] == 225.00  # 4500 * 0.05
        assert cons["margemRccBeneficio5"] == 225.00  # 4500 * 0.05
        assert cons["margemTotal45"] == 2025.00  # 4500 * 0.45

        # 4. WhatsApp Probe Garantido
        wa = res["whatsappGarantido"]
        assert wa is not None
        assert wa["garantido"] is True
        assert wa["numero"] == "(21) 98765-4321"

        # 5. Validação Canônica
        canonical = res.get("canonical")
        assert canonical is not None
        payload_obj = CanonicalPersonPayload.model_validate(canonical)
        assert payload_obj.identification.status == "QUALIFIED"
        assert payload_obj.identification.lead_score == 90
        assert payload_obj.loss_prevention_filter.is_deceased is False
        assert payload_obj.loss_prevention_filter.elegivel_consignado is True
