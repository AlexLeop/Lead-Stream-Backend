from __future__ import annotations

import pytest
from django.utils import timezone

from leadstream.billing.models import DataBlock
from leadstream.entities.models import Company, ContactPoint, Relationship
from leadstream.entities.services import (
    create_company,
    create_contact_point,
    create_person,
    create_relationship,
    create_social_profile,
)
from leadstream.providers.live_enrichment import enrich_company_live
from leadstream.providers.orchestrator import CascadeResult
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


def test_mei_e_apresentado_como_simei_vinculado_ao_simples(monkeypatch) -> None:
    tenant = get_internal_tenant()
    monkeypatch.setattr(
        "leadstream.providers.live_enrichment.fetch_official_rfb_data",
        lambda _cnpj: {
            "_leadstream_source": "Fonte cadastral de teste",
            "_leadstream_observed_at": timezone.now(),
            "razao_social": "EMPRESA INDIVIDUAL TESTE",
            "opcao_pelo_simples": True,
            "opcao_pelo_mei": True,
            "data_opcao_pelo_simples": "2024-01-01",
            "data_opcao_pelo_mei": "2024-01-01",
        },
    )

    result = enrich_company_live("04.252.011/0001-10", tenant)
    tax_section = next(section for section in result["sections"] if section["id"] == "tax")
    fields = {field["label"]: field["value"] for field in tax_section["fields"]}

    assert tax_section["summary"] == "MEI (SIMEI), modalidade vinculada ao Simples Nacional."
    assert fields["Enquadramento"] == "Microempreendedor Individual (MEI / SIMEI)"
    assert fields["Regime associado"] == "Simples Nacional"


def test_consulta_individual_executa_cascata_e_retorna_decisor_atribuivel(
    monkeypatch,
) -> None:
    tenant = get_internal_tenant()
    monkeypatch.setattr(
        "leadstream.providers.live_enrichment.fetch_official_rfb_data",
        lambda _cnpj: {
            "_leadstream_source": "Fonte cadastral de teste",
            "_leadstream_observed_at": timezone.now(),
            "razao_social": "Empresa Decisora Ltda",
            "nome_fantasia": "Empresa Decisora",
            "descricao_situacao_cadastral": "ATIVA",
        },
    )

    def fake_cascade(*, tenant, batch, item, requested_blocks):  # type: ignore[no-untyped-def]
        assert item.entity_id is not None
        assert DataBlock.DECISION_MAKER in requested_blocks
        assert DataBlock.DIRECT_EMAIL in requested_blocks
        assert DataBlock.DIRECT_PHONE in requested_blocks
        assert DataBlock.SOCIAL_PROFILES in requested_blocks
        company = Company.objects.get(entity=item.entity)
        person = create_person(
            tenant=tenant,
            full_name="Maria Decisora",
            external_key="provider:maria-decisora",
        )
        create_relationship(
            tenant=tenant,
            person=person,
            company=company,
            qualification=Relationship.Qualification.ADMINISTRATOR,
            observed_title="Diretora comercial",
            seniority=Relationship.Seniority.DIRECTOR,
        )
        create_contact_point(
            tenant=tenant,
            owner=person.entity,
            kind=ContactPoint.Kind.EMAIL,
            value="maria@example.com",
        )
        create_contact_point(
            tenant=tenant,
            owner=person.entity,
            kind=ContactPoint.Kind.PHONE,
            value="11987654321",
        )
        create_social_profile(
            tenant=tenant,
            owner=person.entity,
            network="LINKEDIN",
            profile_url="https://www.linkedin.com/in/maria-decisora",
        )
        return CascadeResult(
            delivered_blocks=frozenset(
                {
                    DataBlock.DECISION_MAKER,
                    DataBlock.DIRECT_EMAIL,
                    DataBlock.DIRECT_PHONE,
                    DataBlock.SOCIAL_PROFILES,
                }
            ),
            missing_blocks=frozenset(),
            providers_called=1,
            errors=(),
        )

    monkeypatch.setattr(
        "leadstream.providers.live_enrichment.run_enrichment_cascade",
        fake_cascade,
    )

    result = enrich_company_live(
        "04.252.011/0001-10",
        tenant,
        capabilities=["cnpj_qsa", "emails_smtp", "phones_whatsapp"],
        execution_key="job-test-decision-maker",
    )
    decision_section = next(
        section for section in result["sections"] if section["id"] == "decision_makers"
    )
    fields = {
        field["label"]: field["value"] for field in decision_section["items"][0]["fields"]
    }

    assert decision_section["status"] == "available"
    assert decision_section["items"][0]["title"] == "Maria Decisora"
    assert fields["E-mail 1"] == "maria@example.com"
    assert fields["Telefone 1"] == "(11) 98765-4321"
    assert fields["LinkedIn"] == "https://linkedin.com/in/maria-decisora"
    assert result["providerCoverage"]["missing"] == []
