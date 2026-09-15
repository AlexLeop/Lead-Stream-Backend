from __future__ import annotations

import pytest
from django.utils import timezone

from leadstream.entities.models import Company, ContactPoint
from leadstream.entities.services import create_company
from leadstream.providers.live_enrichment import enrich_company_live
from leadstream.tenancy.services import get_internal_tenant

pytestmark = pytest.mark.django_db


def test_enriquecimento_projeta_dados_cadastrais_sem_inventar_ausencias(
    monkeypatch,
) -> None:
    tenant = get_internal_tenant()
    observed_at = timezone.now()
    monkeypatch.setattr(
        "leadstream.providers.live_enrichment.fetch_official_rfb_data",
        lambda _cnpj: {
            "_leadstream_source": "Fonte cadastral de teste",
            "_leadstream_observed_at": observed_at,
            "razao_social": "Empresa Exemplo S.A.",
            "nome_fantasia": "Exemplo",
            "descricao_situacao_cadastral": "ATIVA",
            "data_inicio_atividade": "2005-11-03",
            "natureza_juridica": "Sociedade Empresária Limitada",
            "porte": "ME",
            "capital_social": "125000.50",
            "cnae_fiscal": "6201501",
            "cnae_fiscal_descricao": "Desenvolvimento de programas de computador",
            "cnaes_secundarios": [
                {"codigo": "6202300", "descricao": "Desenvolvimento sob encomenda"}
            ],
            "descricao_identificador_matriz_filial": "MATRIZ",
            "logradouro": "Avenida Paulista",
            "numero": "1000",
            "bairro": "Bela Vista",
            "municipio": "São Paulo",
            "uf": "SP",
            "cep": "01310100",
            "email": "contato@empresa.example",
        },
    )

    result = enrich_company_live("04.252.011/0001-10", tenant)

    company = Company.objects.get(entity_id=result["companyId"])
    establishment = company.establishments.get(cnpj="04252011000110")
    assert company.primary_cnae == "6201501"
    assert company.share_capital is not None
    assert str(company.share_capital) == "125000.50"
    assert company.simple_national is None
    assert company.mei is None
    assert company.registry_source == "Fonte cadastral de teste"
    assert establishment.city == "São Paulo"
    assert establishment.state == "SP"
    assert result["company"]["annualRevenue"] == ""
    assert result["company"]["capitalSocial"] == "R$ 125.000,50"
    assert result["emailsValidados"] == []
    assert result["telefonesAtribuiveis"] == []
    assert result["contatosCadastraisEmpresa"] == [
        {
            "tipo": "EMAIL",
            "valor": "contato@empresa.example",
            "fonte": "Fonte cadastral de teste",
        }
    ]
    assert ContactPoint.objects.get().owner_id == company.entity_id


def test_projecao_em_cache_preserva_false_explicito(monkeypatch) -> None:
    tenant = get_internal_tenant()
    identity = create_company(
        tenant=tenant,
        cnpj="04.252.011/0001-10",
        legal_name="Empresa em cache",
    )
    company = identity.company
    company.simple_national = False
    company.mei = False
    company.registry_source = "OpenCNPJ"
    company.registry_observed_at = timezone.now()
    company.save(
        update_fields=("simple_national", "mei", "registry_source", "registry_observed_at")
    )
    monkeypatch.setattr(
        "leadstream.providers.live_enrichment.fetch_official_rfb_data",
        lambda _cnpj: None,
    )

    result = enrich_company_live("04.252.011/0001-10", tenant)
    tax_section = next(section for section in result["sections"] if section["id"] == "tax")

    assert tax_section["status"] == "available"
    assert "Não optante" in tax_section["summary"]
    assert "MEI: Não" in tax_section["summary"]
    assert result["registryEvidence"]["method"] == "CACHE"
