from __future__ import annotations

import pytest

from leadstream.batches.models import Batch, BatchItem
from leadstream.canonical.builder import CanonicalLeadBuilder
from leadstream.canonical.contracts import CanonicalLeadPayload
from leadstream.tenancy.services import get_internal_tenant

pytestmark = pytest.mark.django_db


def test_canonical_lead_builder_builds_and_saves() -> None:
    tenant = get_internal_tenant()
    batch = Batch.objects.create(
        tenant=tenant,
        name="Lote Builder Test",
        idempotency_key="batch-builder-001",
    )
    item = BatchItem.objects.create(
        tenant=tenant,
        batch=batch,
        row_number=1,
        hygiene_state=BatchItem.HygieneState.CORRECTED,
        normalized_data={
            "cnpj": "48.944.179/0001-61",
            "razao_social": "ALEX LEOPOLDO DE OLIVEIRA 17351600762",
            "nome_fantasia": "ALEX LEOPOLDO",
            "situacao_cadastral": "ATIVA",
            "data_situacao_cadastral": "2022-12-19",
            "data_inicio_atividade": "2022-12-19",
            "codigo_natureza_juridica": "2135",
            "cnae_fiscal": "8599603",
            "cnaes_secundarios": "9511800,4789099",
            "porte": "01",
            "opcao_pelo_simples": True,
            "opcao_pelo_mei": True,
            "capital_social": 10.0,
            "logradouro": "RUA VISCONDE DE INHAUMA",
            "numero": "580",
            "complemento": "SALA 101",
            "bairro": "CENTRO",
            "municipio": "RIO DE JANEIRO",
            "uf": "RJ",
            "cep": "20091-007",
            "codigo_municipio_ibge": "3304557",
            "correio_eletronico": "lx.leopoldo@outlook.com",
            "ddd_telefone_1": "21996260135",
            "qsa": [
                {
                    "nome_socio": "ALEX LEOPOLDO DE OLIVEIRA",
                    "qualificacao_socio": "Empresário",
                    "faixa_etaria": "31-40 anos",
                }
            ],
        },
    )

    builder = CanonicalLeadBuilder(tenant=tenant)
    payload_dict = builder.build_and_save(item)

    # 1. Check returned structure validates against CanonicalLeadPayload
    validated = CanonicalLeadPayload.model_validate(payload_dict)
    assert validated.meta_.schema_version == "2.4.0"

    # 2. Check company & economics
    assert validated.company.cnpj == "48.944.179/0001-61"
    assert validated.company.razao_social == "ALEX LEOPOLDO DE OLIVEIRA 17351600762"
    assert validated.company.porte_sebrae == "MEI"
    assert validated.company.regime_tributario == "SIMEI"
    assert validated.company.capital_social_formatado == "R$ 10,00"
    assert validated.company.natureza_juridica["codigo"] == "213-5"

    # 3. Check CNAE
    assert validated.cnae.principal.codigo == "85.99-6-03"
    assert len(validated.cnae.secundarios) == 2

    # 4. Check Contacts & Validation
    assert len(validated.contacts.emails) >= 1
    assert validated.contacts.emails[0].endereco == "lx.leopoldo@outlook.com"
    assert validated.contacts.emails[0].mx_found is True
    assert len(validated.contacts.telefones) >= 1
    assert validated.contacts.telefones[0].ddd == "21"
    assert validated.contacts.telefones[0].numero == "996260135"
    assert "-" not in validated.contacts.telefones[0].numero
    assert "+" not in validated.contacts.telefones[0].numero
    assert " " not in validated.contacts.telefones[0].numero

    # 5. Check QSA
    assert len(validated.decision_makers_qsa) == 1
    assert validated.decision_makers_qsa[0].nome == "ALEX LEOPOLDO DE OLIVEIRA"

    # 6. Check Persistence in DB
    item.refresh_from_db()
    assert item.canonical_payload["_meta"]["schema_version"] == "2.4.0"
    assert item.canonical_payload["company"]["cnpj"] == "48.944.179/0001-61"
