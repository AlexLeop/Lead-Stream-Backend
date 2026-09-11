from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from leadstream.batches.hygiene import normalize_row
from leadstream.batches.models import Batch, BatchItem
from leadstream.canonical.contracts import CanonicalLeadPayload
from leadstream.entities.services import create_company
from leadstream.providers.adapters.bigquery import BigQueryOpenCNPJAdapter, QueryResponse
from leadstream.providers.orchestrator import run_enrichment_cascade
from leadstream.tenancy.services import get_internal_tenant

pytestmark = pytest.mark.django_db


@override_settings(
    BIGQUERY_PROJECT_ID="leadstream-507303",
    OPEN_CNPJ_BIGQUERY_SQL="SELECT 1",
)
def test_cnpj_alex_canonical_end_to_end(api_client: APIClient) -> None:
    tenant = get_internal_tenant()
    batch = Batch.objects.create(
        tenant=tenant,
        name="Lote Homologação Alex Leopoldo",
        idempotency_key="batch-alex-real-001",
    )

    # 1. Raw input with only the CNPJ (as provided by client or CSV)
    raw_input = {"cnpj": "48.944.179/0001-61"}

    # 2. Hygiene & Normalization via backend
    hyg = normalize_row(raw_input)
    assert hyg.state in (BatchItem.HygieneState.UNCHANGED, BatchItem.HygieneState.CORRECTED)

    # 3. Canonical Company Entity creation
    ident = create_company(
        tenant=tenant,
        cnpj=hyg.normalized["cnpj"],
        legal_name=f"Empresa {hyg.normalized['cnpj']}",
    )

    # 4. Item persistence
    item = BatchItem.objects.create(
        tenant=tenant,
        batch=batch,
        row_number=1,
        original_data=raw_input,
        normalized_data=hyg.normalized,
        hygiene_state=hyg.state,
        applied_rules=hyg.rules,
        issues=hyg.issues,
        fingerprint=hyg.fingerprint,
        entity=ident.company.entity,
        status=BatchItem.Status.SUCCEEDED,
    )

    # 5. Real RFB data runner simulating BigQuery query response
    def alex_runner(sql: str, parameters: dict[str, Any]) -> QueryResponse:
        return QueryResponse(
            rows=(
                {
                    "cnpj": "48944179000161",
                    "razao_social": "48.944.179 ALEX LEOPOLDO DA SILVA",
                    "nome_fantasia": None,
                    "situacao_cadastral": "2",
                    "data_situacao_cadastral": "2022-12-20",
                    "data_inicio_atividade": "2022-12-20",
                    "motivo_situacao_cadastral": "0",
                    "cnae_fiscal": "8599603",
                    "cnaes_secundarios": (
                        "9511800,4789099,4773300,4772500,4781400,4751201,4755503,"
                        "4763602,4763601,4754703,4789008,4789007,4782201,4783102,4783101"
                    ),
                    "uf": "RJ",
                    "municipio": "Rio de Janeiro",
                    "codigo_municipio_ibge": "3304557",
                    "tipo_logradouro": "ESTRADA",
                    "logradouro": "DA AGUA GRANDE - DE 756 AO FIM - LADO PAR",
                    "numero": "1.202",
                    "complemento": "COND AMOVILA",
                    "bairro": "VISTA ALEGRE",
                    "cep": "21230355",
                    "ddd_1": "21",
                    "telefone_1": "96260135",
                    "email": "lx.leopoldo@outlook.com",
                    "capital_social": 10.0,
                    "porte": "1",
                    "natureza_juridica": "2135",
                    "socios": [
                        {
                            "nome_socio": "ALEX LEOPOLDO DA SILVA",
                            "qualificacao_socio": "PROPRIETARIO",
                            "faixa_etaria": None,
                        }
                    ],
                },
            ),
            billed_bytes=1024,
        )

    adapters = {
        "open-cnpj-bigquery": BigQueryOpenCNPJAdapter(runner=alex_runner),
    }

    # 6. Execute real backend enrichment cascade with the adapter
    run_enrichment_cascade(
        tenant=tenant,
        batch=batch,
        item=item,
        adapters=adapters,
    )

    # 7. Query the REST API for canonical lead
    client = api_client
    response = client.get(
        f"/api/v1/leads/{item.id}/canonical/",
        HTTP_X_TENANT_ID=tenant.slug,
    )

    assert response.status_code == 200
    data = response.data

    # 8. Validate compliance with CanonicalLeadPayload schema
    canonical = CanonicalLeadPayload.model_validate(data)
    assert canonical.meta_.schema_version == "2.4.0"

    # 9. Verify 14 core sections exist
    reference_file = Path("payload.json")
    if reference_file.exists():
        reference_data = json.loads(reference_file.read_text(encoding="utf-8"))
        for key in reference_data.keys():
            assert key in data, f"Key '{key}' missing from generated canonical payload"

    # 10. Real Company Data directly enriched by Backend (BigQuery / RFB)
    comp = data["company"]
    assert comp["cnpj"] == "48.944.179/0001-61"
    assert comp["cnpj_raw"] == "48944179000161"
    assert comp["razao_social"] == "48.944.179 ALEX LEOPOLDO DA SILVA"
    assert comp["nome_fantasia"] is None
    assert comp["situacao_cadastral"] == "ATIVA"
    assert comp["data_abertura"] == "2022-12-20"
    assert comp["natureza_juridica"]["codigo"] == "213-5"
    assert "Empresário" in comp["natureza_juridica"]["descricao"]

    # 11. CNAE Intelligence (Principal + 15 Secundários from RFB)
    cnae = data["cnae"]
    assert cnae["principal"]["codigo"] == "85.99-6-03"
    assert "Treinamento" in cnae["principal"]["descricao"]
    assert len(cnae["secundarios"]) == 15

    # 12. Technical Contact Validation (Email & Phone from RFB)
    contacts = data["contacts"]
    assert len(contacts["emails"]) >= 1
    email_entry = contacts["emails"][0]
    assert email_entry["endereco"] == "lx.leopoldo@outlook.com"
    assert email_entry["mx_found"] is True

    assert len(contacts["telefones"]) >= 1
    phone_entry = contacts["telefones"][0]
    assert phone_entry["ddd"] == "21"
    assert phone_entry["numero"] == "96260135"
    assert "-" not in phone_entry["numero"]
    assert "+" not in phone_entry["numero"]
    assert " " not in phone_entry["numero"]
    assert "-" not in phone_entry["ddd"]
    assert "+" not in phone_entry["ddd"]
    assert " " not in phone_entry["ddd"]

    # 13. Real Address Verification from RFB
    addr = data["address"]
    assert addr["tipo_logradouro"] == "ESTRADA"
    assert "AGUA GRANDE" in addr["logradouro"]
    assert addr["numero"] == "1.202"
    assert addr["bairro"] == "VISTA ALEGRE"
    assert addr["uf"] == "RJ"
    assert addr["cep"] == "21230-355"

    # 14. Decision Maker / QSA (Owner from RFB)
    qsa = data["decision_makers_qsa"]
    assert len(qsa) == 1
    assert qsa[0]["nome"] == "ALEX LEOPOLDO DA SILVA"
    direct = qsa[0]["contatos_diretos"]
    assert direct["ddd_celular"] == "21"
    assert direct["celular_whatsapp"] == "96260135"
    assert "-" not in direct["celular_whatsapp"]
    assert "+" not in direct["celular_whatsapp"]
    assert " " not in direct["celular_whatsapp"]
    assert qsa[0]["qualificacao_socio"] == "PROPRIETARIO"
    # LinkedIn is not fabricated when absent
    assert qsa[0]["contatos_diretos"]["linkedin_url"] is None

    # 15. Financial & Banking Truthfulness (Not fabricated when absent)
    fin = data["financial_and_banking"]
    assert fin["instituicoes_bancarias_principais"] == []
    assert fin["bancos_relacionamento_detectados"] == []

    # 16. Digital Presence Truthfulness (Not fabricated when absent)
    redes = data["digital_presence_and_tech_stack"]["redes_sociais"]
    assert redes["linkedin_decisor"] is None
    assert redes["linkedin_company"] is None
