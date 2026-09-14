from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet
from django.db import connection
from django.test import override_settings
from rest_framework.test import APIClient

from leadstream.batches.models import Batch, BatchItem
from leadstream.entities.models import (
    Company,
    ContactPoint,
    Entity,
    Establishment,
    Person,
    Relationship,
    SocialProfile,
)
from leadstream.integrations.connectors.hubspot import HubSpotConnector
from leadstream.integrations.connectors.pipedrive import PipedriveConnector
from leadstream.integrations.connectors.ploomes import PloomesConnector
from leadstream.integrations.connectors.rdstation import RDStationConnector
from leadstream.integrations.connectors.salesforce import SalesforceConnector
from leadstream.integrations.connectors.webhook import WebhookConnector
from leadstream.integrations.models import (
    CRMConnection,
    CRMConnectorType,
    CRMFieldEntityType,
    CRMFieldMapping,
    CRMFieldTransformation,
    CRMOutboxMessage,
    OutboxStatus,
)
from leadstream.integrations.services import (
    dispatch_outbox_message,
    enqueue_batch_to_crm,
)
from leadstream.security.crypto import generate_api_key
from leadstream.security.models import WorkspaceRole
from leadstream.tenancy.models import Tenant
from leadstream.tenancy.services import get_internal_tenant

pytestmark = pytest.mark.django_db


@pytest.fixture
def internal_tenant() -> Tenant:
    return get_internal_tenant()


@pytest.fixture
def other_tenant() -> Tenant:
    return Tenant.objects.create(name="Outro Cliente", slug="outro-cliente")


@pytest.fixture
def sample_batch_with_data(internal_tenant: Tenant) -> Batch:
    batch = Batch.objects.create(
        tenant=internal_tenant,
        name="Lote CRM Teste",
        source_type=Batch.SourceType.CSV,
        status=Batch.Status.COMPLETED,
        total_rows=1,
        succeeded_rows=1,
    )
    comp_ent = Entity.objects.create(
        tenant=internal_tenant, kind=Entity.Kind.COMPANY, natural_key="11222333"
    )
    company = Company.objects.create(
        entity=comp_ent,
        cnpj_root="11222333",
        legal_name="Apex Sistemas LTDA",
        trade_name="Apex Tech",
        registration_status="ATIVA",
    )
    estab_ent = Entity.objects.create(
        tenant=internal_tenant, kind=Entity.Kind.ESTABLISHMENT, natural_key="11222333000181"
    )
    Establishment.objects.create(
        entity=estab_ent,
        company=company,
        cnpj="11222333000181",
        is_headquarters=True,
        registration_status="ATIVA",
    )
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
        company=company,
        person=person,
        qualification=Relationship.Qualification.ADMINISTRATOR,
        observed_title="Diretor de Tecnologia",
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
        kind=ContactPoint.Kind.WHATSAPP,
        scope=ContactPoint.Scope.PERSON,
        original_value="+5511998877665",
        normalized_value="+5511998877665",
        capabilities={"is_whatsapp": True},
        status=ContactPoint.Status.CONFIRMED,
    )
    SocialProfile.objects.create(
        tenant=internal_tenant,
        owner=person_ent,
        network=SocialProfile.Network.LINKEDIN,
        profile_url="https://linkedin.com/in/joaosilva",
        normalized_url="https://linkedin.com/in/joaosilva",
        status=ContactPoint.Status.OBSERVED,
    )

    BatchItem.objects.create(
        tenant=internal_tenant,
        batch=batch,
        row_number=1,
        original_data={"cnpj": "11.222.333/0001-81"},
        normalized_data={"cnpj": "11222333000181", "razao_social": "Apex Sistemas LTDA"},
        entity=comp_ent,
        status="COMPLETED",
    )
    return batch


def test_webhook_connector_signature_and_dispatch(internal_tenant: Tenant) -> None:
    conn = CRMConnection.objects.create(
        tenant=internal_tenant,
        name="Meu Webhook n8n",
        connector_type=CRMConnectorType.WEBHOOK_CUSTOM,
        credentials={
            "webhook_url": "https://meu-n8n.webhook.site/leads",
            "signing_secret": "minha-chave-secreta-hmac-123",
        },
    )

    connector = WebhookConnector()
    test_data = {"cnpj": "11222333000181", "razao_social": "Empresa Teste LTDA"}

    with patch("httpx.Client.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {"id": "n8n_event_999"}
        mock_post.return_value = mock_resp

        result = connector.sync_company(conn, test_data, [])

        assert result.success is True
        assert result.remote_id == "n8n_event_999"
        assert mock_post.called

        called_kwargs = mock_post.call_args.kwargs
        body = called_kwargs["content"]
        headers = called_kwargs["headers"]

        assert "X-LeadStream-Signature" in headers
        expected_sig = hmac.new(b"minha-chave-secreta-hmac-123", body, hashlib.sha256).hexdigest()
        assert headers["X-LeadStream-Signature"] == f"sha256={expected_sig}"

        payload = json.loads(body.decode("utf-8"))
        assert payload["event"] == "company.enriched"
        assert payload["data"]["cnpj"] == "11222333000181"


def test_enqueue_batch_to_crm_idempotency(sample_batch_with_data: Batch) -> None:
    tenant = sample_batch_with_data.tenant
    conn = CRMConnection.objects.create(
        tenant=tenant,
        name="Pipedrive Vendas",
        connector_type=CRMConnectorType.PIPEDRIVE,
        credentials={"api_token": "pipedrive-token-fake"},
    )

    # Primeira execução: deve enfileirar
    enqueued_1 = enqueue_batch_to_crm(sample_batch_with_data, conn, lead_level="DECISION_MAKER")
    assert enqueued_1 == 1

    messages = CRMOutboxMessage.objects.filter(connection=conn)
    assert messages.count() == 1
    msg = messages.first()
    assert msg is not None
    assert msg.status == OutboxStatus.PENDING
    assert msg.entity_type == CRMFieldEntityType.CONTACT
    assert msg.canonical_payload["nome_decisor"] == "João Silva Santos"
    assert msg.canonical_payload["email_direto"] == "joao.silva@apextech.com.br"
    assert msg.canonical_payload["whatsapp_validado"] is True

    # Segunda execução idêntica: idempotência estrita (zero novas mensagens criadas)
    enqueued_2 = enqueue_batch_to_crm(sample_batch_with_data, conn, lead_level="DECISION_MAKER")
    assert enqueued_2 == 0
    assert CRMOutboxMessage.objects.filter(connection=conn).count() == 1


def test_dispatch_outbox_message_retry_and_dead_letter(internal_tenant: Tenant) -> None:
    conn = CRMConnection.objects.create(
        tenant=internal_tenant,
        name="HubSpot",
        connector_type=CRMConnectorType.HUBSPOT,
        credentials={"access_token": "hubspot-token-fake"},
    )
    msg = CRMOutboxMessage.objects.create(
        tenant=internal_tenant,
        connection=conn,
        entity_type=CRMFieldEntityType.COMPANY,
        idempotency_key="idemp_key_fail_test",
        canonical_payload={"name": "Empresa Falha"},
        max_retries=2,
    )

    with patch("httpx.Client.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_resp.headers = {}
        mock_post.return_value = mock_resp

        # Tentativa 1: FAILED com retry_count = 1
        ok1 = dispatch_outbox_message(msg)
        assert ok1 is False
        msg.refresh_from_db()
        assert msg.status == OutboxStatus.FAILED
        assert msg.retry_count == 1
        assert len(msg.execution_log) == 1

        # Tentativa 2: Atinge max_retries (2) -> DEAD_LETTER
        ok2 = dispatch_outbox_message(msg)
        assert ok2 is False
        msg.refresh_from_db()
        assert msg.status == OutboxStatus.DEAD_LETTER
        assert msg.retry_count == 2
        assert len(msg.execution_log) == 2


def test_native_connectors_fixtures(internal_tenant: Tenant) -> None:
    # 1. HubSpot
    hs_conn = CRMConnection(
        tenant=internal_tenant,
        connector_type=CRMConnectorType.HUBSPOT,
        credentials={"access_token": "hs_token"},
    )
    hs_connector = HubSpotConnector()
    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=201,
            headers={"content-type": "application/json"},
            json=lambda: {"id": "hs_comp_1"},
        )
        res = hs_connector.sync_company(hs_conn, {"razao_social": "Beta Corp"}, [])
        assert res.success is True
        assert res.remote_id == "hs_comp_1"

    # 2. Pipedrive
    pipe_conn = CRMConnection(
        tenant=internal_tenant,
        connector_type=CRMConnectorType.PIPEDRIVE,
        credentials={"api_token": "pipe_token"},
    )
    pipe_connector = PipedriveConnector()
    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=201, json=lambda: {"data": {"id": 1001}})
        res = pipe_connector.sync_company(pipe_conn, {"razao_social": "Gama Corp"}, [])
        assert res.success is True
        assert res.remote_id == "1001"

    # 3. RD Station
    rd_conn = CRMConnection(
        tenant=internal_tenant,
        connector_type=CRMConnectorType.RD_STATION,
        credentials={"token": "rd_token"},
    )
    rd_connector = RDStationConnector()
    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            headers={"content-type": "application/json"},
            json=lambda: {"_id": "rd_999"},
        )
        res = rd_connector.sync_company(rd_conn, {"razao_social": "Delta Corp"}, [])
        assert res.success is True
        assert res.remote_id == "rd_999"

    # 4. Salesforce
    sf_conn = CRMConnection(
        tenant=internal_tenant,
        connector_type=CRMConnectorType.SALESFORCE,
        credentials={"instance_url": "https://fake.salesforce.com", "access_token": "sf_token"},
    )
    sf_connector = SalesforceConnector()
    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=201,
            headers={"content-type": "application/json"},
            json=lambda: {"id": "001xx000003DGS1AA4"},
        )
        res = sf_connector.sync_company(sf_conn, {"razao_social": "Epsilon Corp"}, [])
        assert res.success is True
        assert res.remote_id == "001xx000003DGS1AA4"

    # 5. Ploomes
    ploomes_conn = CRMConnection(
        tenant=internal_tenant,
        connector_type=CRMConnectorType.PLOOMES,
        credentials={"user_key": "ploomes_key"},
    )
    ploomes_connector = PloomesConnector()
    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {"value": [{"Id": 777}]})
        res = ploomes_connector.sync_company(ploomes_conn, {"razao_social": "Zeta Corp"}, [])
        assert res.success is True
        assert res.remote_id == "777"


def test_field_mapping_transformation(internal_tenant: Tenant) -> None:
    conn = CRMConnection.objects.create(
        tenant=internal_tenant,
        name="Webhook Custom",
        connector_type=CRMConnectorType.WEBHOOK_CUSTOM,
        credentials={"webhook_url": "https://test.com"},
    )
    CRMFieldMapping.objects.create(
        tenant=internal_tenant,
        connection=conn,
        entity_type=CRMFieldEntityType.COMPANY,
        source_field="cnpj",
        target_field="tax_id_numbers_only",
        transformation=CRMFieldTransformation.DIGITS_ONLY,
    )
    CRMFieldMapping.objects.create(
        tenant=internal_tenant,
        connection=conn,
        entity_type=CRMFieldEntityType.COMPANY,
        source_field="razao_social",
        target_field="company_upper",
        transformation=CRMFieldTransformation.UPPER,
    )

    connector = WebhookConnector()
    mappings = list(CRMFieldMapping.objects.filter(connection=conn))
    data = {"cnpj": "12.345.678/0001-90", "razao_social": "empresa legal ltda"}
    mapped = connector.apply_mapping(data, mappings)

    assert mapped["tax_id_numbers_only"] == "12345678000190"
    assert mapped["company_upper"] == "EMPRESA LEGAL LTDA"


def test_api_connection_crud_and_tenant_isolation(
    api_client: APIClient, internal_tenant: Tenant, other_tenant: Tenant
) -> None:
    client = api_client

    # 1. Cria conexão para internal_tenant
    resp = client.post(
        "/api/v1/integracoes/conexoes/",
        {
            "name": "HubSpot Principal",
            "connector_type": "HUBSPOT",
            "credentials": {"access_token": "hs_secret_123"},
        },
        format="json",
    )
    assert resp.status_code == 201
    conn_id = resp.data["id"]
    # Garante que credenciais NÃO são expostas na leitura
    assert resp.data["has_credentials"] is True
    assert "credentials" not in resp.data or not resp.data["credentials"]

    # 2. Outro tenant NÃO pode ver a conexão (Proteção IDOR)
    _, other_raw_key = generate_api_key(
        tenant=other_tenant,
        name="Outro tenant",
        role=WorkspaceRole.ADMIN,
    )
    other_client = APIClient()
    other_client.credentials(HTTP_X_API_KEY=other_raw_key)
    resp_other = other_client.get(f"/api/v1/integracoes/conexoes/{conn_id}/")
    assert resp_other.status_code == 404

    # 3. Cockpit do CEO: métricas consolidadas
    resp_admin = client.get("/api/v1/admin/integracoes/metricas/")
    assert resp_admin.status_code == 200
    assert "outbox_status_summary" in resp_admin.data
    assert "active_connectors_summary" in resp_admin.data


def test_crm_credentials_are_encrypted_at_rest(internal_tenant: Tenant) -> None:
    secret = "segredo-que-nao-pode-aparecer-no-banco"
    crm_connection = CRMConnection.objects.create(
        tenant=internal_tenant,
        name="HubSpot cifrado",
        connector_type=CRMConnectorType.HUBSPOT,
        credentials={"access_token": secret},
    )

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT credentials FROM leadstream_crm_connection WHERE name = %s",
            ["HubSpot cifrado"],
        )
        raw_credentials = str(cursor.fetchone()[0])

    assert raw_credentials.startswith("enc:v1:")
    assert secret not in raw_credentials
    crm_connection.refresh_from_db()
    assert crm_connection.credentials == {"access_token": secret}


def test_crm_encryption_key_rotation_preserves_existing_secrets(
    internal_tenant: Tenant,
) -> None:
    old_key = Fernet.generate_key().decode("ascii")
    new_key = Fernet.generate_key().decode("ascii")
    with override_settings(FIELD_ENCRYPTION_KEYS=[old_key]):
        crm_connection = CRMConnection.objects.create(
            tenant=internal_tenant,
            name="Conexão antes da rotação",
            connector_type=CRMConnectorType.PIPEDRIVE,
            credentials={"api_token": "token-historico"},
        )

    with override_settings(FIELD_ENCRYPTION_KEYS=[new_key, old_key]):
        recovered = CRMConnection.objects.get(pk=crm_connection.pk)
        assert recovered.credentials == {"api_token": "token-historico"}


def test_admin_crm_metrics_do_not_cross_tenants(
    api_client: APIClient, internal_tenant: Tenant, other_tenant: Tenant
) -> None:
    CRMConnection.objects.create(
        tenant=internal_tenant,
        name="Visível",
        connector_type=CRMConnectorType.HUBSPOT,
        credentials={"access_token": "visible"},
    )
    CRMConnection.objects.create(
        tenant=other_tenant,
        name="Isolado",
        connector_type=CRMConnectorType.PIPEDRIVE,
        credentials={"api_token": "hidden"},
    )

    response = api_client.get("/api/v1/admin/integracoes/metricas/")

    assert response.status_code == 200
    assert response.data["active_connectors_summary"] == {"HUBSPOT": 1}


def test_batch_sync_to_crm_api(api_client: APIClient, sample_batch_with_data: Batch) -> None:
    tenant = sample_batch_with_data.tenant
    conn = CRMConnection.objects.create(
        tenant=tenant,
        name="HubSpot Sync API Test",
        connector_type=CRMConnectorType.HUBSPOT,
        credentials={"access_token": "hs_secret_api"},
    )
    client = api_client
    client.defaults["HTTP_X_TENANT_ID"] = str(tenant.id)

    with patch("leadstream.integrations.tasks.sync_batch_to_crm_task.delay") as mock_delay:
        resp = client.post(
            f"/api/v1/lotes/{sample_batch_with_data.id}/sincronizar-crm/",
            {"connection_id": str(conn.id), "lead_level": "DECISION_MAKER"},
            format="json",
        )
        assert resp.status_code == 202
        assert resp.data["status"] == "QUEUED"
        assert resp.data["connection_id"] == str(conn.id)
        assert mock_delay.called


def test_process_crm_outbox_batch_celery_task(internal_tenant: Tenant) -> None:
    from leadstream.integrations.tasks import process_crm_outbox_batch

    conn = CRMConnection.objects.create(
        tenant=internal_tenant,
        name="Webhook Worker Test",
        connector_type=CRMConnectorType.WEBHOOK_CUSTOM,
        credentials={"webhook_url": "https://worker.webhook.site/leads"},
    )
    msg = CRMOutboxMessage.objects.create(
        tenant=internal_tenant,
        connection=conn,
        entity_type=CRMFieldEntityType.COMPANY,
        idempotency_key="worker_msg_test_1",
        canonical_payload={"name": "Empresa Worker"},
        status=OutboxStatus.PENDING,
    )

    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200, headers={}, json=lambda: {"id": "wh_123"}
        )
        result = process_crm_outbox_batch(batch_size=10)
        assert result["processed"] == 1
        assert result["success"] == 1
        assert result["failed"] == 0

        msg.refresh_from_db()
        assert msg.status == OutboxStatus.DELIVERED
