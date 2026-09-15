from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from leadstream.entities.models import ContactPoint
from leadstream.entities.services import create_company
from leadstream.security.crypto import generate_api_key
from leadstream.security.models import WorkspaceRole
from leadstream.tenancy.models import Tenant
from leadstream.tenancy.services import get_internal_tenant

pytestmark = pytest.mark.django_db


def test_activation_list_is_persistent_and_counts_real_contact_states(
    api_client: APIClient,
) -> None:
    tenant = get_internal_tenant()
    first = create_company(
        tenant=tenant,
        cnpj="11222333000181",
        legal_name="=Empresa com contato",
    )
    second = create_company(
        tenant=tenant,
        cnpj="19131243000197",
        legal_name="Empresa sem contato",
    )
    ContactPoint.objects.create(
        tenant=tenant,
        owner=first.company.entity,
        kind=ContactPoint.Kind.EMAIL,
        scope=ContactPoint.Scope.COMPANY,
        original_value="vendas@example.com",
        normalized_value="vendas@example.com",
        status=ContactPoint.Status.CAPABILITY_VALID,
    )

    response = api_client.post(
        "/api/v1/lists",
        {
            "name": "Contas prioritárias",
            "description": "Seleção operacional",
            "crmTarget": "HubSpot",
            "leadIds": [str(first.company.entity_id), str(second.company.entity_id)],
        },
        format="json",
    )
    assert response.status_code == 201
    assert response.data["leadCount"] == 2
    assert response.data["validCount"] == 1
    assert set(response.data["leadIds"]) == {
        str(first.company.entity_id),
        str(second.company.entity_id),
    }

    list_id = response.data["id"]
    repeated = api_client.post(
        f"/api/v1/lists/{list_id}/leads",
        {"leadIds": [str(first.company.entity_id)]},
        format="json",
    )
    assert repeated.status_code == 200
    assert repeated.data["leadCount"] == 2

    detail = api_client.get(f"/api/v1/lists/{list_id}/leads")
    assert detail.status_code == 200
    assert detail.data["count"] == 2
    assert {lead["company"] for lead in detail.data["results"]} == {
        "=Empresa com contato",
        "Empresa sem contato",
    }

    exported = api_client.get(f"/api/v1/lists/{list_id}/export")
    assert exported.status_code == 200
    assert exported["Cache-Control"] == "private, no-store"
    csv_text = b"".join(exported.streaming_content).decode("utf-8-sig")
    assert "tipo;nome;empresa;cnpj" in csv_text
    assert "'=Empresa com contato" in csv_text
    assert "vendas@example.com" in csv_text


def test_activation_list_is_tenant_isolated_and_archive_blocks_mutation(
    api_client: APIClient,
) -> None:
    tenant = get_internal_tenant()
    company = create_company(
        tenant=tenant,
        cnpj="11222333000181",
        legal_name="Empresa interna",
    )
    created = api_client.post(
        "/api/v1/lists",
        {"name": "Lista interna", "leadIds": [str(company.company.entity_id)]},
        format="json",
    )
    list_id = created.data["id"]
    archived = api_client.patch(f"/api/v1/lists/{list_id}/archive", {}, format="json")
    assert archived.status_code == 200
    assert archived.data["isArchived"] is True
    blocked = api_client.post(
        f"/api/v1/lists/{list_id}/leads",
        {"leadIds": [str(company.company.entity_id)]},
        format="json",
    )
    assert blocked.status_code == 400

    other = Tenant.objects.create(name="Outro workspace", slug="outro-workspace-listas")
    _, raw_key = generate_api_key(tenant=other, name="Outro", role=WorkspaceRole.ADMIN)
    other_client = APIClient()
    other_client.credentials(HTTP_X_API_KEY=raw_key)
    assert other_client.get(f"/api/v1/lists/{list_id}/leads").status_code == 404
    assert other_client.get("/api/v1/lists").data == []


def test_data_health_repair_only_expires_objectively_stale_data(api_client: APIClient) -> None:
    tenant = get_internal_tenant()
    company = create_company(
        tenant=tenant,
        cnpj="11222333000181",
        legal_name="Empresa com validade",
    )
    expired = ContactPoint.objects.create(
        tenant=tenant,
        owner=company.company.entity,
        kind=ContactPoint.Kind.EMAIL,
        scope=ContactPoint.Scope.COMPANY,
        original_value="expired@example.com",
        normalized_value="expired@example.com",
        status=ContactPoint.Status.CONFIRMED,
        expires_at=timezone.now() - timedelta(seconds=1),
    )
    preserved = ContactPoint.objects.create(
        tenant=tenant,
        owner=company.company.entity,
        kind=ContactPoint.Kind.PHONE,
        scope=ContactPoint.Scope.COMPANY,
        original_value="+5511999999999",
        normalized_value="+5511999999999",
        status=ContactPoint.Status.CONFIRMED,
        expires_at=timezone.now() + timedelta(days=30),
    )

    response = api_client.post("/api/v1/data-health/repair", {}, format="json")
    assert response.status_code == 200
    assert response.data["success"] is True
    assert response.data["repairedContacts"] == 1
    assert response.data["boostedScores"] == 0
    expired.refresh_from_db()
    preserved.refresh_from_db()
    assert expired.status == ContactPoint.Status.EXPIRED
    assert preserved.status == ContactPoint.Status.CONFIRMED
