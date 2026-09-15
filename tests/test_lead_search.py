from __future__ import annotations

import pytest

from leadstream.analytics.lead_search import search_leads
from leadstream.analytics.views import _lead_for_entity
from leadstream.entities.models import ContactPoint, Entity, Relationship
from leadstream.entities.projections import update_company_registry_projection
from leadstream.entities.services import (
    create_company,
    create_contact_point,
    create_person,
    create_relationship,
)
from leadstream.providers.live_enrichment import calculate_expected_dv
from leadstream.tenancy.services import get_internal_tenant

pytestmark = pytest.mark.django_db


def _cnpj(base: str) -> str:
    assert len(base) == 12
    return base + calculate_expected_dv(base)


def _company(tenant, *, base: str, name: str, state: str, cnae: str, size: str):
    identity = create_company(
        tenant=tenant,
        cnpj=_cnpj(base),
        legal_name=name,
        registration_status="ATIVA",
    )
    update_company_registry_projection(
        company=identity.company,
        data={
            "company_size": size,
            "primary_cnae": cnae,
            "primary_cnae_description": "Tecnologia da informação",
            "city": "São Paulo" if state == "SP" else "Curitiba",
            "state": state,
        },
        source="OpenCNPJ",
    )
    return identity.company


def test_busca_de_leads_pagina_filtra_e_inclui_pf_sem_vinculo(
    api_client, django_assert_max_num_queries
) -> None:
    tenant = get_internal_tenant()
    alpha = _company(
        tenant,
        base="100000000001",
        name="Alpha Tecnologia Ltda",
        state="SP",
        cnae="6201501",
        size="ME",
    )
    _company(
        tenant,
        base="200000000001",
        name="Beta Comércio Ltda",
        state="PR",
        cnae="4711302",
        size="EPP",
    )
    linked_person = create_person(
        tenant=tenant,
        full_name="Maria Diretora",
        external_key="maria-diretora",
    )
    create_relationship(
        tenant=tenant,
        person=linked_person,
        company=alpha,
        qualification=Relationship.Qualification.ADMINISTRATOR,
        observed_title="Diretora Comercial",
        seniority=Relationship.Seniority.DIRECTOR,
    )
    standalone = create_person(
        tenant=tenant,
        full_name="João Independente",
        external_key="joao-independente",
    )
    create_contact_point(
        tenant=tenant,
        owner=alpha.entity,
        kind=ContactPoint.Kind.EMAIL,
        value="vendas@alpha.example",
        status=ContactPoint.Status.CONFIRMED,
    )

    first_page = api_client.get("/api/v1/leads/?page=1&page_size=2")
    assert first_page.status_code == 200
    assert first_page.data["count"] == 4
    assert len(first_page.data["results"]) == 2
    assert first_page.data["totalPages"] == 2
    assert first_page.data["nextPage"] == 2
    assert first_page.data["facets"] == {"PJ": 2, "PF": 2}

    second_page = api_client.get("/api/v1/leads/?page=2&page_size=2")
    assert second_page.status_code == 200
    all_ids = {lead["id"] for lead in first_page.data["results"] + second_page.data["results"]}
    assert str(standalone.entity_id) in all_ids
    assert len(all_ids) == 4

    filtered = api_client.get(
        "/api/v1/leads/?lead_type=PJ&uf=SP&cnae=6201&company_size=ME&has_email=true"
    )
    assert filtered.status_code == 200
    assert filtered.data["count"] == 1
    lead = filtered.data["results"][0]
    assert lead["razaoSocial"] == "Alpha Tecnologia Ltda"
    assert lead["city"] == "São Paulo"
    assert lead["cnae"] == "6201501"
    assert lead["email"] == "vendas@alpha.example"

    person_search = api_client.get("/api/v1/leads/?q=Diretora&lead_type=PF")
    assert person_search.status_code == 200
    assert person_search.data["count"] == 1
    assert person_search.data["results"][0]["name"] == "Maria Diretora"

    with django_assert_max_num_queries(10):
        page = search_leads(tenant=tenant, params={}, page=1, page_size=100)
        serialized = [_lead_for_entity(entity) for entity in page.entities]
    assert len(serialized) == 4


def test_busca_rejeita_paginacao_e_filtros_invalidos(api_client) -> None:
    invalid_page = api_client.get("/api/v1/leads/?page_size=1000")
    assert invalid_page.status_code == 400
    invalid_type = api_client.get("/api/v1/leads/?lead_type=XPTO")
    assert invalid_type.status_code == 400
    invalid_dataset = api_client.get("/api/v1/leads/?dataset_id=invalido")
    assert invalid_dataset.status_code == 400


def test_busca_permanece_isolada_por_workspace(api_client) -> None:
    tenant = get_internal_tenant()
    _company(
        tenant,
        base="300000000001",
        name="Empresa Interna",
        state="SP",
        cnae="6201501",
        size="ME",
    )

    response = api_client.get("/api/v1/leads/")

    assert response.status_code == 200
    assert (
        response.data["count"]
        == Entity.objects.filter(tenant=tenant).exclude(kind=Entity.Kind.ESTABLISHMENT).count()
    )
