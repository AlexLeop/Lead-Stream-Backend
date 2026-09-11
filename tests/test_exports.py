from __future__ import annotations

import csv
import io
from pathlib import Path
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from leadstream.batches.exporter import CommercialBatchExporter, sanitize_csv_cell
from leadstream.batches.models import Batch, BatchExport, BatchItem
from leadstream.entities.models import (
    Company,
    ContactPoint,
    Entity,
    Establishment,
    Person,
    Relationship,
    SocialProfile,
)
from leadstream.tenancy.models import Tenant
from leadstream.tenancy.services import get_internal_tenant

pytestmark = pytest.mark.django_db


@pytest.fixture
def sample_batch(tmp_path: Path, settings: object) -> Batch:
    settings.BATCH_STORAGE_ROOT = tmp_path  # type: ignore[attr-defined]
    tenant = get_internal_tenant()
    batch = Batch.objects.create(
        tenant=tenant,
        name="Lote Teste Export",
        source_type=Batch.SourceType.CSV,
        status=Batch.Status.COMPLETED,
        total_rows=2,
        succeeded_rows=2,
    )
    return batch


@pytest.fixture
def enriched_batch_data(sample_batch: Batch) -> tuple[BatchItem, BatchItem]:
    tenant = sample_batch.tenant

    # Empresa 1
    company_ent1 = Entity.objects.create(
        tenant=tenant, kind=Entity.Kind.COMPANY, natural_key="12345678"
    )
    company1 = Company.objects.create(
        entity=company_ent1,
        cnpj_root="12345678",
        legal_name="Alpha Tech Soluções LTDA",
        trade_name="Alpha Tech",
        registration_status="ATIVA",
    )
    Establishment.objects.create(
        entity=Entity.objects.create(
            tenant=tenant, kind=Entity.Kind.ESTABLISHMENT, natural_key="12345678000195"
        ),
        company=company1,
        cnpj="12345678000195",
        is_headquarters=True,
    )

    # Decisor 1 (Com contatos diretos 100% visíveis e fórmula no cargo para testar sanitização)
    person_ent1 = Entity.objects.create(
        tenant=tenant, kind=Entity.Kind.PERSON, natural_key="joao.silva"
    )
    person1 = Person.objects.create(
        entity=person_ent1,
        full_name="João Silva",
        normalized_name="JOAO SILVA",
    )
    Relationship.objects.create(
        tenant=tenant,
        person=person1,
        company=company1,
        qualification=Relationship.Qualification.ADMINISTRATOR,
        observed_title="=CMD|' /C calc'!A0",  # Teste de tentativa de formula injection
        normalized_title="Diretor Executivo",
        seniority=Relationship.Seniority.DIRECTOR,
        buying_role="Decisor Final",
    )
    ContactPoint.objects.create(
        tenant=tenant,
        owner=person_ent1,
        kind=ContactPoint.Kind.EMAIL,
        scope=ContactPoint.Scope.PERSON,
        original_value="joao.silva@alphatech.com.br",
        normalized_value="joao.silva@alphatech.com.br",
        status=ContactPoint.Status.CONFIRMED,
    )
    ContactPoint.objects.create(
        tenant=tenant,
        owner=person_ent1,
        kind=ContactPoint.Kind.PHONE,
        scope=ContactPoint.Scope.PERSON,
        original_value="(11) 98765-4321",
        normalized_value="+5511987654321",
        status=ContactPoint.Status.CONFIRMED,
        capabilities={"whatsapp": True},
    )
    SocialProfile.objects.create(
        tenant=tenant,
        owner=person_ent1,
        network=SocialProfile.Network.LINKEDIN,
        profile_url="https://linkedin.com/in/joaosilva",
        normalized_url="https://linkedin.com/in/joaosilva",
    )

    item1 = BatchItem.objects.create(
        tenant=tenant,
        batch=sample_batch,
        row_number=1,
        entity=company_ent1,
        status=BatchItem.Status.SUCCEEDED,
        enrichment_status=BatchItem.EnrichmentStatus.SUCCEEDED,
        delivered_blocks=["Receita Federal", "BigDataCorp", "Apify"],
        normalized_data={
            "cnpj": "12.345.678/0001-95",
            "razao_social": "Alpha Tech Soluções LTDA",
            "state": "SP",
            "city": "São Paulo",
            "primary_cnae": "6201-5/01",
        },
        processed_at=timezone.now(),
    )

    # Empresa 2 (Sem decisor, apenas contatos da empresa)
    company_ent2 = Entity.objects.create(
        tenant=tenant, kind=Entity.Kind.COMPANY, natural_key="98765432"
    )
    company2 = Company.objects.create(
        entity=company_ent2,
        cnpj_root="98765432",
        legal_name="Beta Distribuidora LTDA",
        trade_name="Beta Brasil",
        registration_status="ATIVA",
    )
    Establishment.objects.create(
        entity=Entity.objects.create(
            tenant=tenant, kind=Entity.Kind.ESTABLISHMENT, natural_key="98765432000188"
        ),
        company=company2,
        cnpj="98765432000188",
        is_headquarters=True,
    )
    ContactPoint.objects.create(
        tenant=tenant,
        owner=company_ent2,
        kind=ContactPoint.Kind.EMAIL,
        scope=ContactPoint.Scope.COMPANY,
        original_value="contato@betabrasil.com.br",
        normalized_value="contato@betabrasil.com.br",
        status=ContactPoint.Status.DOMAIN_VALID,
    )

    item2 = BatchItem.objects.create(
        tenant=tenant,
        batch=sample_batch,
        row_number=2,
        entity=company_ent2,
        status=BatchItem.Status.SUCCEEDED,
        enrichment_status=BatchItem.EnrichmentStatus.SUCCEEDED,
        delivered_blocks=["Receita Federal"],
        normalized_data={
            "cnpj": "98.765.432/0001-88",
            "razao_social": "Beta Distribuidora LTDA",
            "state": "PR",
            "city": "Curitiba",
        },
        processed_at=timezone.now(),
    )

    return item1, item2


def test_sanitize_csv_cell() -> None:
    assert sanitize_csv_cell("Texto normal") == "Texto normal"
    assert sanitize_csv_cell("=1+1") == "'=1+1"
    assert sanitize_csv_cell("+551199999999") == "'+551199999999"
    assert sanitize_csv_cell("-100") == "'-100"
    assert sanitize_csv_cell("@username") == "'@username"
    assert sanitize_csv_cell(None) == ""


def test_exporter_pt_br_unmasked_data_and_manifest(
    sample_batch: Batch,
    enriched_batch_data: tuple[BatchItem, BatchItem],
    tmp_path: Path,
    settings: object,
) -> None:
    settings.BATCH_STORAGE_ROOT = tmp_path  # type: ignore[attr-defined]
    tenant = sample_batch.tenant

    export = BatchExport.objects.create(
        tenant=tenant,
        batch=sample_batch,
        status=BatchExport.Status.PENDING,
    )

    exporter = CommercialBatchExporter(export)
    completed_export = exporter.execute()

    assert completed_export.status == BatchExport.Status.COMPLETED
    assert completed_export.total_rows == 2
    assert completed_export.total_companies == 2
    assert completed_export.total_decision_makers == 1
    assert completed_export.total_direct_contacts == 2
    assert completed_export.sha256 != ""
    assert completed_export.size_bytes > 0

    # Valida manifesto
    manifest = completed_export.manifest_data
    assert manifest["manifest_version"] == "1.0"
    assert manifest["file_sha256"] == completed_export.sha256
    assert manifest["total_rows_exported"] == 2

    # Lê o arquivo gerado e verifica se o formato pt-BR e dados estão 100% visíveis
    dest = tmp_path / completed_export.file_key
    assert dest.exists()

    content = dest.read_bytes()
    # Verifica BOM UTF-8 (EF BB BF)
    assert content.startswith(b"\xef\xbb\xbf")

    text = content.decode("utf-8-sig")
    lines = list(csv.reader(io.StringIO(text), delimiter=";"))
    assert len(lines) == 3  # Header + 2 rows
    header = lines[0]
    assert "CNPJ" in header
    assert "Razao_Social" in header
    assert "Email_Direto" in header
    assert "Telefone_Direto" in header
    assert "LinkedIn_Decisor" in header

    row_alpha = lines[1]
    # CNPJ e Razão Social
    assert "Alpha Tech" in row_alpha[1]
    # Decisor e contatos 100% visíveis sem mascaramento
    assert "João Silva" in row_alpha[header.index("Nome_Decisor")]
    assert "joao.silva@alphatech.com.br" in row_alpha[header.index("Email_Direto")]
    assert (
        "+5511987654321" in row_alpha[header.index("Telefone_Direto")]
        or "'+5511987654321" in row_alpha[header.index("Telefone_Direto")]
    )
    assert "https://linkedin.com/in/joaosilva" in row_alpha[header.index("LinkedIn_Decisor")]
    # Sanitização da tentativa de formula injection
    assert row_alpha[header.index("Cargo_Observado")].startswith("'=")


def test_api_export_create_and_cache(
    api_client: APIClient,
    sample_batch: Batch,
    enriched_batch_data: tuple[BatchItem, BatchItem],
    tmp_path: Path,
    settings: object,
) -> None:
    settings.BATCH_STORAGE_ROOT = tmp_path  # type: ignore[attr-defined]

    with patch("leadstream.batches.views.generate_export_task.delay") as mock_task:
        response = api_client.post(
            f"/api/v1/lotes/{sample_batch.id}/exportar/",
            {"lead_level": "DECISION_MAKER"},
            format="json",
        )
        assert response.status_code == 202
        export_id = response.json()["id"]
        assert mock_task.call_count == 1

    # Executa a geração
    export = BatchExport.objects.get(pk=export_id)
    CommercialBatchExporter(export).execute()

    # Segunda chamada idêntica deve retornar 200 OK com o export em cache imediatamente
    response_cache = api_client.post(
        f"/api/v1/lotes/{sample_batch.id}/exportar/",
        {"lead_level": "DECISION_MAKER"},
        format="json",
    )
    assert response_cache.status_code == 200
    assert response_cache.json()["id"] == str(export.id)
    assert response_cache.json()["status"] == "COMPLETED"


def test_api_export_download_and_security_headers(
    api_client: APIClient,
    sample_batch: Batch,
    enriched_batch_data: tuple[BatchItem, BatchItem],
    tmp_path: Path,
    settings: object,
) -> None:
    settings.BATCH_STORAGE_ROOT = tmp_path  # type: ignore[attr-defined]

    export = BatchExport.objects.create(
        tenant=sample_batch.tenant,
        batch=sample_batch,
        status=BatchExport.Status.PENDING,
    )
    CommercialBatchExporter(export).execute()

    # Download do arquivo
    response = api_client.get(f"/api/v1/exportacoes/{export.id}/download/")
    assert response.status_code == 200
    assert "attachment;" in response["Content-Disposition"]
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Cache-Control"] == "private, no-transform"
    body = (
        b"".join(response.streaming_content)
        if hasattr(response, "streaming_content")
        else response.content
    )
    assert b"Alpha Tech" in body


def test_export_idor_protection(
    api_client: APIClient,
    sample_batch: Batch,
    tmp_path: Path,
    settings: object,
) -> None:
    settings.BATCH_STORAGE_ROOT = tmp_path  # type: ignore[attr-defined]
    other_tenant = Tenant.objects.create(
        name="Outro Cliente",
        slug="outro-cliente",
    )
    other_batch = Batch.objects.create(
        tenant=other_tenant,
        name="Lote de Outro Tenant",
        source_type=Batch.SourceType.CSV,
    )
    other_export = BatchExport.objects.create(
        tenant=other_tenant,
        batch=other_batch,
        status=BatchExport.Status.COMPLETED,
    )

    # Tentativa de exportar lote de outro tenant via API do tenant interno
    resp1 = api_client.post(f"/api/v1/lotes/{other_batch.id}/exportar/")
    assert resp1.status_code == 404

    # Tentativa de baixar export de outro tenant
    resp2 = api_client.get(f"/api/v1/exportacoes/{other_export.id}/download/")
    assert resp2.status_code == 404
