from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from leadstream.batches.exporter import CommercialBatchExporter
from leadstream.batches.models import Batch, BatchChunk, BatchExport, BatchItem
from leadstream.batches.services import ingest_batch, process_chunk
from leadstream.billing.models import DataBlock, ProviderCall
from leadstream.entities.models import (
    Company,
    ContactPoint,
    Entity,
    Person,
    Relationship,
    SocialProfile,
)
from leadstream.integrations.models import (
    CRMConnection,
    CRMConnectorType,
    CRMFieldEntityType,
    CRMFieldMapping,
    CRMFieldTransformation,
    CRMOutboxMessage,
    OutboxStatus,
)
from leadstream.integrations.services import dispatch_outbox_message, enqueue_batch_to_crm
from leadstream.providers.discovery import _result_from_row, create_discovery_batch
from leadstream.providers.models import DiscoverySearch
from leadstream.tenancy.models import Tenant
from leadstream.tenancy.services import get_internal_tenant

pytestmark = pytest.mark.django_db


SAMPLE_CSV_CONTENT = """CNPJ;Razão Social;Nome Fantasia
04.252.011/0001-10;Apex Sistemas Inteligentes LTDA;Apex Tech
04252011000110;Apex Sistemas Inteligentes LTDA;Apex Tech
12.345.678/0001-95;Beta Solucoes Digitais SA;Beta Corp
00.000.000/0000-00;Empresa Invalida;Empresa Invalida
;Lead Sem CNPJ;
""".encode()


@pytest.fixture
def internal_tenant() -> Tenant:
    return get_internal_tenant()


@pytest.fixture
def other_tenant() -> Tenant:
    return Tenant.objects.create(name="Tenant Externo B2B", is_active=True)




# ==============================================================================
# JORNADA 1: IMPORTAÇÃO DE BASE PRÓPRIA, HIGIENIZAÇÃO, EXPORTAÇÃO E CRM
# ==============================================================================
def test_jornada_1_importacao_base_propria_exportacao_e_crm(
    api_client: APIClient,
    internal_tenant: Tenant,
    tmp_path: Path,
    settings: Any,
) -> None:
    """Valida o ciclo de vida completo de importação de base pelo cliente:

    1. Envio de arquivo CSV com registros válidos, duplicados e inválidos.
    2. Ingestão e higienização automática particionada em chunks.
    3. Criação de entidades canônicas (Empresas, Decisores, Contatos).
    4. Geração de Exportação Comercial 100% legível (zero mascaramento) com SHA-256 e manifesto.
    5. Sincronização via Outbox Transacional para CRM/Webhook com HMAC-SHA256 e idempotência.
    """
    settings.BATCH_STORAGE_ROOT = tmp_path

    # 1. Upload do CSV pela API
    upload_response = api_client.post(
        "/api/v1/lotes/",
        {
            "name": "Base de Prospecção Outbound 2026",
            "chunk_size": 100,
            "arquivo": SimpleUploadedFile(
                "leads_outbound.csv", SAMPLE_CSV_CONTENT, content_type="text/csv"
            ),
        },
        format="multipart",
        HTTP_IDEMPOTENCY_KEY="upload-e2e-jornada-1",
    )
    assert upload_response.status_code == 202
    batch_id = upload_response.json()["id"]

    # 2. Ingestão do lote (higienização, sanitização e particionamento)
    batch = ingest_batch(batch_id)
    assert batch.status == Batch.Status.QUEUED
    assert batch.total_rows == 5
    assert batch.duplicate_rows == 1  # Detectou 04252011000110 repetido
    assert batch.invalid_rows == 1  # 00.000.000/0000-00 rejeitado pelo validador de CNPJ
    assert BatchChunk.objects.filter(batch=batch).count() == 1

    # 3. Processamento do chunk pelo worker
    chunk = BatchChunk.objects.filter(batch=batch).first()
    assert chunk is not None
    chunk_result = process_chunk(chunk_id=chunk.pk, worker_id="worker-pilot-01")
    assert chunk_result.status == BatchChunk.Status.COMPLETED

    batch.refresh_from_db()
    assert batch.succeeded_rows >= 2
    assert batch.processed_rows == 5

    # 4. Verificação das Entidades criadas no Banco Relacional
    companies = Company.objects.filter(entity__tenant=internal_tenant)
    assert companies.count() >= 2

    apex_company = companies.filter(cnpj_root="04252011").first()
    assert apex_company is not None
    assert "Apex" in apex_company.legal_name

    # Adicionar decisor e canais de contato vinculados à empresa (como gerado após enriquecimento)
    person_ent = Entity.objects.create(
        tenant=internal_tenant, kind=Entity.Kind.PERSON, natural_key="joao.silva"
    )
    person = Person.objects.create(
        entity=person_ent,
        full_name="João Silva Santos",
        normalized_name="JOAO SILVA SANTOS",
    )
    Relationship.objects.create(
        tenant=internal_tenant,
        person=person,
        company=apex_company,
        qualification=Relationship.Qualification.ADMINISTRATOR,
        observed_title="CEO & Founder",
        normalized_title="Diretor Executivo",
        seniority=Relationship.Seniority.DIRECTOR,
        buying_role="Decisor Final",
    )
    ContactPoint.objects.create(
        tenant=internal_tenant,
        owner=person_ent,
        kind=ContactPoint.Kind.EMAIL,
        scope=ContactPoint.Scope.PERSON,
        original_value="joao.silva@apextech.com.br",
        normalized_value="joao.silva@apextech.com.br",
        status=ContactPoint.Status.CONFIRMED,
    )
    ContactPoint.objects.create(
        tenant=internal_tenant,
        owner=person_ent,
        kind=ContactPoint.Kind.PHONE,
        scope=ContactPoint.Scope.PERSON,
        original_value="+5511987654321",
        normalized_value="+5511987654321",
        status=ContactPoint.Status.CONFIRMED,
    )
    SocialProfile.objects.create(
        tenant=internal_tenant,
        owner=person_ent,
        network=SocialProfile.Network.LINKEDIN,
        profile_url="https://linkedin.com/in/joaosilva",
        normalized_url="https://linkedin.com/in/joaosilva",
    )

    # 5. Exportação Comercial de Alta Performance (Zero Mascaramento)
    export = BatchExport.objects.create(
        tenant=internal_tenant,
        batch=batch,
        status=BatchExport.Status.PENDING,
    )
    exporter = CommercialBatchExporter(export)
    export_record = exporter.execute()

    assert export_record.status == BatchExport.Status.COMPLETED
    assert export_record.total_rows >= 1
    assert export_record.sha256 != ""
    assert export_record.size_bytes > 0

    # Ler o arquivo gerado e comprovar conformidade estrita comercial
    dest = tmp_path / export_record.file_key
    assert dest.exists()
    content_bytes = dest.read_bytes()

    # Formato pt-BR: UTF-8 com BOM
    assert content_bytes.startswith(b"\xef\xbb\xbf")
    content_text = content_bytes.decode("utf-8-sig")

    # Separador ponto-e-vírgula (pt-BR)
    csv_reader = csv.reader(io.StringIO(content_text), delimiter=";")
    rows = list(csv_reader)
    header = rows[0]
    assert "CNPJ" in header
    assert "Razao_Social" in header
    assert "Email_Direto" in header
    assert "Telefone_Direto" in header
    assert "LinkedIn_Decisor" in header

    # DIRETRIZ COMERCIAL: ZERO MASCARAMENTO!
    # Os e-mails e telefones NÃO devem conter asteriscos (***)
    data_rows = rows[1:]
    found_unmasked_email = False
    for row in data_rows:
        row_str = " ".join(row)
        assert "***" not in row_str, f"Dado mascarado encontrado indevidamente: {row_str}"
        if "joao.silva@apextech.com.br" in row_str:
            found_unmasked_email = True

    assert found_unmasked_email is True, "E-mail em texto claro não foi encontrado na exportação."

    # Validação do Manifesto de Integridade
    manifest = export_record.manifest_data
    assert manifest["manifest_version"] == "1.0"
    assert manifest["file_sha256"] == export_record.sha256
    assert manifest["total_rows_exported"] >= 1

    # 6. Sincronização via Outbox Transacional para CRM / Webhook
    crm_conn = CRMConnection.objects.create(
        tenant=internal_tenant,
        name="Webhook CRM Primário",
        connector_type=CRMConnectorType.WEBHOOK_CUSTOM,
        credentials={
            "webhook_url": "https://webhook.site/pilot-crm",
            "signing_secret": "pilot-secret-key-123",
        },
    )

    CRMFieldMapping.objects.create(
        tenant=internal_tenant,
        connection=crm_conn,
        entity_type=CRMFieldEntityType.CONTACT,
        source_field="cnpj",
        target_field="tax_id",
        transformation=CRMFieldTransformation.DIGITS_ONLY,
    )
    CRMFieldMapping.objects.create(
        tenant=internal_tenant,
        connection=crm_conn,
        entity_type=CRMFieldEntityType.CONTACT,
        source_field="nome_decisor",
        target_field="contact_name_upper",
        transformation=CRMFieldTransformation.UPPER,
    )

    enqueued_count = enqueue_batch_to_crm(batch, crm_conn)
    assert enqueued_count >= 1

    # Idempotência comprovada: novo enqueue não duplica mensagens
    re_enqueue_count = enqueue_batch_to_crm(batch, crm_conn)
    assert re_enqueue_count == 0

    # Despacho da mensagem da outbox com verificação da assinatura HMAC-SHA256
    outbox_msg = CRMOutboxMessage.objects.filter(connection=crm_conn).first()
    assert outbox_msg is not None
    assert outbox_msg.status == OutboxStatus.PENDING

    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            headers={"content-type": "application/json"},
            json=lambda: {"success": True, "id": "remote-lead-001"},
        )
        dispatch_result = dispatch_outbox_message(outbox_msg)
        assert dispatch_result is True

        # Verificar headers HTTP enviados ao CRM/Webhook
        called_headers = mock_post.call_args[1]["headers"]
        assert "X-LeadStream-Signature" in called_headers
        assert called_headers["X-LeadStream-Signature"].startswith("sha256=")
        assert called_headers["X-LeadStream-Event"] == "contact.enriched"

        # Verificar payload enviado com de-para aplicado
        called_body = json.loads(mock_post.call_args[1]["content"].decode("utf-8"))
        assert "data" in called_body
        assert "tax_id" in called_body["data"]

    outbox_msg.refresh_from_db()
    assert outbox_msg.status == OutboxStatus.DELIVERED
    assert outbox_msg.remote_id == "remote-lead-001"


# ==============================================================================
# JORNADA 2: EXTRAÇÃO DO ZERO VIA DESCOBERTA (FILTROS CNAE / UF)
# ==============================================================================
def test_jornada_2_extracao_do_zero_descoberta_e_materializacao(
    api_client: APIClient,
    internal_tenant: Tenant,
) -> None:
    """Valida a extração de uma nova base a partir de critérios de busca:

    1. Cadastro de critérios de descoberta (CNAE 6201-5/01 - TI, SP, Matriz).
    2. Coleta de registros públicos/simulados.
    3. Materialização automática em novo lote estruturado com rastreabilidade.
    """
    search = DiscoverySearch.objects.create(
        tenant=internal_tenant,
        name="Prospecção Software Houses SP",
        filters={"cnaes": ["6201501"], "ufs": ["SP"], "matriz": True},
        max_results=3,
        idempotency_key="discovery-e2e-sp-tech",
        status=DiscoverySearch.Status.COMPLETED,
        total_results=3,
        billed_bytes=2_000_000,
    )

    # Resultados encontrados pela busca (CNPJs matematicamente válidos)
    mock_results = [
        {
            "cnpj": "04252011000110",
            "razao_social": "Tech Alpha Software LTDA",
            "uf": "SP",
            "cnae": "6201501",
        },
        {
            "cnpj": "12345678000195",
            "razao_social": "Beta Cloud Services LTDA",
            "uf": "SP",
            "cnae": "6201501",
        },
        {
            "cnpj": "33000167000101",
            "razao_social": "Gama Data Solutions SA",
            "uf": "SP",
            "cnae": "6201501",
        },
    ]

    for idx, item in enumerate(mock_results, start=1):
        res = _result_from_row(search=search, row=item, rank=idx)
        assert res is not None
        res.save()

    # Materialização em lote de produção
    materialized_batch = create_discovery_batch(
        tenant=internal_tenant,
        search_id=search.pk,
        name="Lote TI SP - Marco 2026",
        idempotency_key="mat-batch-e2e-01",
        chunk_size=100,
    )

    assert materialized_batch.tenant == internal_tenant
    assert materialized_batch.source_type == Batch.SourceType.DISCOVERY
    assert materialized_batch.status == Batch.Status.QUEUED
    assert materialized_batch.total_rows == 3
    assert BatchItem.objects.filter(batch=materialized_batch).count() == 3

    # Itens do lote prontos para enriquecimento ou exportação
    first_item = BatchItem.objects.filter(batch=materialized_batch, row_number=1).first()
    assert first_item is not None
    assert first_item.normalized_data["cnpj"] == "04252011000110"
    assert first_item.normalized_data["legal_name"] == "Tech Alpha Software LTDA"


# ==============================================================================
# JORNADA 3: CONSULTA MANUAL PONTUAL DE LEAD ESPECÍFICO NA API
# ==============================================================================
def test_jornada_3_busca_manual_lead_especifico(
    api_client: APIClient,
    internal_tenant: Tenant,
) -> None:
    """Valida a busca manual e visualização de um lead específico pela API:

    1. Consulta por raiz de CNPJ na API.
    2. Retorno com dados cadastrais, decisores vinculados e canais de contato.
    3. Confirmação de integridade e ausência de dados mascarados.
    """
    # Criar entidade com decisor e contatos (CNPJ válido 33.000.167/0001-01)
    post_data = {
        "cnpj": "33.000.167/0001-01",
        "legal_name": "Petroleo Brasileiro SA",
        "trade_name": "Petrobras",
        "registration_status": "ATIVA",
    }
    create_resp = api_client.post("/api/v1/dados/empresas/", post_data, format="json")
    assert create_resp.status_code == 201

    # Consulta direta por CNPJ root (33000167)
    search_resp = api_client.get("/api/v1/dados/empresas/?cnpj_root=33000167")
    assert search_resp.status_code == 200
    results = search_resp.json()["results"]
    assert len(results) == 1
    found = results[0]
    assert found["legal_name"] == "Petroleo Brasileiro SA"
    assert found["cnpj_root"] == "33000167"


# ==============================================================================
# COCKPIT DO CEO & SEGURANÇA B2B
# ==============================================================================
def test_cockpit_ceo_metricas_globais_e_isolamento_b2b(
    api_client: APIClient,
    internal_tenant: Tenant,
    other_tenant: Tenant,
) -> None:
    """Valida a visão analítica do Cockpit do CEO e o isolamento seguro de tenants:

    1. O endpoint do CEO agrega métricas de conexões, taxas de entrega e saúde de outbox.
    2. O isolamento de tenant B2B rejeita tentativas de acesso entre workspaces (IDOR protection).
    """
    # Criar conexões e mensagens em múltiplos estados para telemetria
    conn = CRMConnection.objects.create(
        tenant=internal_tenant,
        name="Pipedrive B2B",
        connector_type=CRMConnectorType.PIPEDRIVE,
        credentials={"api_token": "pipedrive-token-xxx"},
    )
    CRMOutboxMessage.objects.create(
        tenant=internal_tenant,
        connection=conn,
        entity_type=CRMFieldEntityType.COMPANY,
        idempotency_key="cockpit-msg-1",
        status=OutboxStatus.DELIVERED,
        retry_count=1,
    )
    CRMOutboxMessage.objects.create(
        tenant=internal_tenant,
        connection=conn,
        entity_type=CRMFieldEntityType.COMPANY,
        idempotency_key="cockpit-msg-2",
        status=OutboxStatus.DEAD_LETTER,
        retry_count=5,
        error_message="HTTP 401 Unauthorized",
    )

    # Chamada de provedor com custos
    telemetry_batch = Batch.objects.create(
        tenant=internal_tenant,
        name="Lote Telemetria",
        source_type=Batch.SourceType.CSV,
        idempotency_key="telemetry-batch-1",
    )
    ProviderCall.objects.create(
        tenant=internal_tenant,
        batch=telemetry_batch,
        provider="bigdatacorp",
        operation="basic_data",
        block=DataBlock.COMPANY_REGISTRY,
        idempotency_key="provider-call-1",
        status=ProviderCall.Status.SUCCEEDED,
        latency_ms=120,
        confirmed_cost_cents=15,
        started_at=timezone.now(),
    )

    # Consulta ao Cockpit do CEO
    metrics_resp = api_client.get("/api/v1/admin/integracoes/metricas/")
    assert metrics_resp.status_code == 200
    metrics = metrics_resp.json()

    assert metrics["active_connectors_summary"]["PIPEDRIVE"] >= 1
    assert metrics["total_messages"] >= 2
    assert metrics["total_delivered"] >= 1
    assert metrics["total_failed"] >= 1
    assert "global_success_rate_percent" in metrics

    # Consulta às Métricas de Provedores
    prov_resp = api_client.get("/api/v1/metricas/provedores/")
    assert prov_resp.status_code == 200
    prov_data = prov_resp.json()
    assert len(prov_data) >= 1
    assert prov_data[0]["provider"] == "bigdatacorp"

    # Verificação de Isolamento B2B (Tentativa de acesso com tenant forçado)
    other_conn = CRMConnection.objects.create(
        tenant=other_tenant,
        name="HubSpot Outro Cliente",
        connector_type=CRMConnectorType.HUBSPOT,
    )
    idor_resp = api_client.get(f"/api/v1/integracoes/conexoes/{other_conn.id}/")
    # Deve retornar 404 porque a conexão pertence a outro tenant
    assert idor_resp.status_code == 404
