from __future__ import annotations

import json
from pathlib import Path

import pytest
from rest_framework.test import APIClient

from leadstream.batches.models import Batch, BatchItem
from leadstream.canonical.contracts import CanonicalLeadPayload
from leadstream.tenancy.services import get_internal_tenant

pytestmark = pytest.mark.django_db


def test_cnpj_alex_canonical_end_to_end() -> None:
    tenant = get_internal_tenant()
    batch = Batch.objects.create(
        tenant=tenant,
        name="Lote Homologação Alex Leopoldo",
        idempotency_key="batch-alex-001",
    )

    # Real data from Alex Leopoldo's CNPJ 48.944.179/0001-61
    raw_alex_data = {
        "cnpj": "48.944.179/0001-61",
        "razao_social": "ALEX LEOPOLDO DE OLIVEIRA 17351600762",
        "nome_fantasia": "ALEX LEOPOLDO",
        "situacao_cadastral": "ATIVA",
        "data_situacao_cadastral": "2022-12-20",
        "data_inicio_atividade": "2022-12-20",
        "codigo_natureza_juridica": "2135",
        "cnae_fiscal": "8599603",
        "cnaes_secundarios": (
            "9511800,4789099,4773300,4772500,4781400,4751201,4755503,"
            "4763602,4763601,4754703,4789008,4789007,4782201,4783102,4783101"
        ),
        "porte": "01",
        "opcao_pelo_simples": True,
        "opcao_pelo_mei": True,
        "capital_social": 10.0,
        "tipo_logradouro": "ESTRADA",
        "logradouro": "DA AGUA GRANDE - DE 756 AO FIM - LADO PAR",
        "numero": "1202",
        "complemento": "COND AMOVILA",
        "bairro": "VISTA ALEGRE",
        "municipio": "RIO DE JANEIRO",
        "uf": "RJ",
        "cep": "21230-355",
        "codigo_municipio_ibge": "3304557",
        "correio_eletronico": "lx.leopoldo@outlook.com",
        "ddd_telefone_1": "21996260135",
        "instituicoes_bancarias_principais": [
            {
                "codigo_compensacao": "260",
                "nome_banco": "Nu Pagamentos S.A. (Nubank)",
                "tipo_relacionamento": "CONTA_CORRENTE_PJ_PRINCIPAL",
                "chave_pix_ativa": True,
                "tipo_chave_pix": "CNPJ",
                "chave_pix": "48944179000161",
                "operacoes_cambio_ativas": False,
                "tempo_relacionamento_anos": 2.0,
            },
            {
                "codigo_compensacao": "077",
                "nome_banco": "Banco Inter S.A.",
                "tipo_relacionamento": "CONTA_SECUNDARIA",
                "chave_pix_ativa": True,
                "tipo_chave_pix": "EMAIL",
                "chave_pix": "lx.leopoldo@outlook.com",
                "operacoes_cambio_ativas": False,
                "tempo_relacionamento_anos": 1.5,
            },
        ],
        "qsa": [
            {
                "nome_socio": "ALEX LEOPOLDO DE OLIVEIRA",
                "qualificacao_socio": "Empresário",
                "faixa_etaria": "31-40 anos",
                "linkedin_url": "https://www.linkedin.com/in/alex-leopoldo",
            }
        ],
        "linkedin_company": "https://www.linkedin.com/company/alex-leopoldo",
    }

    item = BatchItem.objects.create(
        tenant=tenant,
        batch=batch,
        row_number=1,
        hygiene_state=BatchItem.HygieneState.CORRECTED,
        normalized_data=raw_alex_data,
    )

    # Query the REST API
    client = APIClient()
    response = client.get(
        f"/api/v1/leads/{item.id}/canonical/",
        HTTP_X_TENANT_ID=tenant.slug,
    )

    assert response.status_code == 200
    data = response.data

    # 1. Validate compliance with CanonicalLeadPayload schema
    canonical = CanonicalLeadPayload.model_validate(data)
    assert canonical.meta_.schema_version == "2.4.0"

    # 2. Match reference payload.json keys
    reference_file = Path("payload.json")
    reference_data = json.loads(reference_file.read_text(encoding="utf-8"))
    for key in reference_data.keys():
        assert key in data, f"Key '{key}' missing from generated canonical payload"

    # 3. Company & Economic Intelligence Verification
    comp = data["company"]
    assert comp["cnpj"] == "48.944.179/0001-61"
    assert comp["cnpj_raw"] == "48944179000161"
    assert comp["cnpj_raiz"] == "48944179"
    assert comp["cnpj_ordem"] == "0001"
    assert comp["cnpj_dv"] == "61"
    assert comp["porte_sebrae"] == "MEI"
    assert comp["regime_tributario"] == "SIMEI"
    assert comp["capital_social_formatado"] == "R$ 10,00"
    assert comp["natureza_juridica"]["codigo"] == "213-5"
    assert "Empresário" in comp["natureza_juridica"]["descricao"]

    # 4. CNAE Intelligence (Principal + 15 Secundários)
    cnae = data["cnae"]
    assert cnae["principal"]["codigo"] == "85.99-6-03"
    assert "Treinamento" in cnae["principal"]["descricao"]
    assert cnae["principal"]["setor"] in ("Educação / Treinamento", "Serviços")
    assert cnae["principal"]["grau_risco_trabalho"] == 1
    assert len(cnae["secundarios"]) == 15

    # 5. Technical Contact Validation (Email & Phone)
    contacts = data["contacts"]
    assert len(contacts["emails"]) >= 1
    email_entry = contacts["emails"][0]
    assert email_entry["endereco"] == "lx.leopoldo@outlook.com"
    assert email_entry["mx_found"] is True
    assert email_entry["status"] in ("ENTREGAVEL", "ENTREGAVEL_VALIDADO")

    assert len(contacts["telefones"]) >= 1
    phone_entry = contacts["telefones"][0]
    assert "99626-0135" in phone_entry["numero"]
    assert phone_entry["whatsapp_status"]["tem_whatsapp"] is True

    # 6. Commercial Identification & Scoring
    ident = data["identification"]
    assert ident["status"] == "QUALIFIED"
    assert ident["lead_score"] == 100
    assert ident["lead_temperature"] == "HOT"
    assert "WhatsApp Ativo" in ident["tags"]
    assert "Target SDR" in ident["tags"]

    # 7. Real Address Verification
    addr = data["address"]
    assert addr["tipo_logradouro"] == "ESTRADA"
    assert "AGUA GRANDE" in addr["logradouro"]
    assert addr["numero"] == "1202"
    assert addr["bairro"] == "VISTA ALEGRE"
    assert addr["municipio"] == "RIO DE JANEIRO"
    assert addr["uf"] == "RJ"
    assert addr["cep"] == "21230-355"

    # 8. Financial & Banking Institutions Verification
    fin = data["financial_and_banking"]
    assert len(fin["instituicoes_bancarias_principais"]) >= 1
    assert (
        fin["instituicoes_bancarias_principais"][0]["nome_banco"]
        == "Nu Pagamentos S.A. (Nubank)"
    )
    assert fin["instituicoes_bancarias_principais"][0]["codigo_compensacao"] == "260"
    assert fin["instituicoes_bancarias_principais"][0]["chave_pix_ativa"] is True

    # 9. QSA & Decision Maker LinkedIn
    qsa = data["decision_makers_qsa"]
    assert len(qsa) == 1
    assert qsa[0]["nome"] == "ALEX LEOPOLDO DE OLIVEIRA"
    assert qsa[0]["contatos_diretos"]["email_corporativo"] == "lx.leopoldo@outlook.com"
    assert "99626-0135" in qsa[0]["contatos_diretos"]["celular_whatsapp"]
    assert (
        qsa[0]["contatos_diretos"]["linkedin_url"]
        == "https://www.linkedin.com/in/alex-leopoldo"
    )

    # 10. Digital Presence Social Networks
    redes = data["digital_presence_and_tech_stack"]["redes_sociais"]
    assert redes["linkedin_decisor"] == "https://www.linkedin.com/in/alex-leopoldo"
    assert redes["linkedin_company"] == "https://www.linkedin.com/company/alex-leopoldo"
