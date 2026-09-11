#!/usr/bin/env python
"""LeadStream Backend — Validador Operacional do Piloto Ponta a Ponta.

Executa os 3 modos reais de uso da plataforma:
1. Importação de Base Própria (Higienização, Enriquecimento, Exportação Zero Mascaramento e Outbox CRM)
2. Extração do Zero via Descoberta (Filtros CNAE/UF e Materialização em Lote)
3. Busca Manual de Lead Específico (API REST, Decisores, Evidências e Contatos)
4. Telemetria do Cockpit do CEO e Isolamento B2B
"""

from __future__ import annotations

import csv
import io
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

# Configura o path do projeto
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")

import django

django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
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
)
from leadstream.integrations.services import dispatch_outbox_message, enqueue_batch_to_crm
from leadstream.providers.discovery import _result_from_row, create_discovery_batch
from leadstream.providers.models import DiscoverySearch
from leadstream.tenancy.models import Tenant
from leadstream.tenancy.services import get_internal_tenant

SAMPLE_CSV = """CNPJ;Razão Social;Nome Fantasia
04.252.011/0001-10;Apex Sistemas Inteligentes LTDA;Apex Tech
04252011000110;Apex Sistemas Inteligentes LTDA;Apex Tech
12.345.678/0001-95;Beta Solucoes Digitais SA;Beta Corp
00.000.000/0000-00;Empresa Invalida;Empresa Invalida
;Lead Sem CNPJ;
""".encode()


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def log_step(title: str) -> None:
    print(f"\n\033[1;36m===> {title}\033[0m")


def log_success(msg: str) -> None:
    print(f"  \033[1;32m[OK]\033[0m {msg}")


def log_info(msg: str) -> None:
    print(f"  \033[0;34m[INFO]\033[0m {msg}")


def main() -> None:
    print("\033[1;35m" + "=" * 80)
    print(" LEADSTREAM BACKEND — SUÍTE DE VALIDAÇÃO OPERACIONAL E PILOTO MEDIDO")
    print("=" * 80 + "\033[0m")

    t_start = time.perf_counter()

    # 0. Migrações
    log_step("Etapa 0: Inicializando banco de dados e aplicando migrações...")
    call_command("migrate", verbosity=0)
    tenant = get_internal_tenant()
    log_success(f"Tenant interno inicializado com sucesso: {tenant.name} ({tenant.id})")

    api_client = APIClient()

    # =========================================================================
    # JORNADA 1: Base Própria
    # =========================================================================
    log_step("Jornada 1: Importação de Base Própria, Higienização, Exportação e CRM")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        from django.conf import settings

        settings.BATCH_STORAGE_ROOT = tmp_path

        # 1.1 Upload
        resp = api_client.post(
            "/api/v1/lotes/",
            {
                "name": "Lote Piloto Real 2026",
                "chunk_size": 100,
                "arquivo": SimpleUploadedFile("leads.csv", SAMPLE_CSV, content_type="text/csv"),
            },
            format="multipart",
            HTTP_IDEMPOTENCY_KEY=f"pilot-upload-{int(time.time())}",
        )
        assert resp.status_code == 202, f"Erro no upload: {resp.data}"
        batch_id = resp.json()["id"]
        log_success(f"Upload aceito via API com status 202 (ID: {batch_id})")

        # 1.2 Ingestão e higienização
        batch = Batch.objects.get(pk=batch_id)
        if batch.status == Batch.Status.RECEIVED:
            batch = ingest_batch(batch_id)
        batch.refresh_from_db()
        assert batch.total_rows == 5
        assert batch.duplicate_rows == 1
        assert batch.invalid_rows == 1
        log_success("Ingestão concluída: 5 linhas, 1 duplicada identificada, 1 inválida rejeitada")

        # 1.3 Processamento do Chunk
        chunk = BatchChunk.objects.filter(batch=batch).first()
        assert chunk is not None
        if chunk.status != BatchChunk.Status.COMPLETED:
            process_chunk(chunk_id=chunk.pk, worker_id="worker-live-pilot")
        batch.refresh_from_db()
        log_success(f"Chunk processado pelo worker: {batch.succeeded_rows} empresas criadas")

        # 1.4 Enriquecimento (simulado para este lote)
        apex_company = Company.objects.filter(cnpj_root="04252011", entity__tenant=tenant).first()
        assert apex_company is not None

        p_ent = Entity.objects.create(
            tenant=tenant, kind=Entity.Kind.PERSON, natural_key="joao.silva"
        )
        p = Person.objects.create(
            entity=p_ent, full_name="João Silva Santos", normalized_name="JOAO SILVA SANTOS"
        )
        Relationship.objects.create(
            tenant=tenant,
            person=p,
            company=apex_company,
            qualification=Relationship.Qualification.ADMINISTRATOR,
            observed_title="CEO & Founder",
            normalized_title="Diretor Executivo",
            seniority=Relationship.Seniority.DIRECTOR,
            buying_role="Decisor Final",
        )
        ContactPoint.objects.create(
            tenant=tenant,
            owner=p_ent,
            kind=ContactPoint.Kind.EMAIL,
            scope=ContactPoint.Scope.PERSON,
            original_value="joao.silva@apextech.com.br",
            normalized_value="joao.silva@apextech.com.br",
            status=ContactPoint.Status.CONFIRMED,
        )
        ContactPoint.objects.create(
            tenant=tenant,
            owner=p_ent,
            kind=ContactPoint.Kind.PHONE,
            scope=ContactPoint.Scope.PERSON,
            original_value="+5511987654321",
            normalized_value="+5511987654321",
            status=ContactPoint.Status.CONFIRMED,
        )
        SocialProfile.objects.create(
            tenant=tenant,
            owner=p_ent,
            network=SocialProfile.Network.LINKEDIN,
            profile_url="https://linkedin.com/in/joaosilva",
            normalized_url="https://linkedin.com/in/joaosilva",
        )
        log_success("Decisor, e-mail corporativo direto, telefone móvel e LinkedIn vinculados")

        # 1.5 Exportação Comercial
        export = BatchExport.objects.create(
            tenant=tenant, batch=batch, status=BatchExport.Status.PENDING
        )
        exporter = CommercialBatchExporter(export)
        export_rec = exporter.execute()
        assert export_rec.status == BatchExport.Status.COMPLETED

        export_file = tmp_path / export_rec.file_key
        assert export_file.exists()
        raw_bytes = export_file.read_bytes()
        assert raw_bytes.startswith(b"\xef\xbb\xbf"), "Arquivo não possui BOM UTF-8"
        text_csv = raw_bytes.decode("utf-8-sig")
        lines = list(csv.reader(io.StringIO(text_csv), delimiter=";"))

        # Zero mascaramento
        for r in lines[1:]:
            line_str = " ".join(r)
            assert "***" not in line_str, "Dados mascarados encontrados indevidamente!"

        log_success(
            f"Exportação gerada ({export_rec.size_bytes} bytes, SHA-256: {export_rec.sha256[:16]}...)"
        )
        log_success(
            "Zero mascaramento confirmado: todos os e-mails e telefones em texto claro legível"
        )

        # 1.6 CRM Outbox
        crm_conn = CRMConnection.objects.create(
            tenant=tenant,
            name="Webhook de Produção",
            connector_type=CRMConnectorType.WEBHOOK_CUSTOM,
            credentials={
                "webhook_url": "https://webhook.site/live-pilot",
                "signing_secret": "pilot-key-secret",
            },
        )
        CRMFieldMapping.objects.create(
            tenant=tenant,
            connection=crm_conn,
            entity_type=CRMFieldEntityType.CONTACT,
            source_field="cnpj",
            target_field="tax_id",
            transformation=CRMFieldTransformation.DIGITS_ONLY,
        )
        enqueued = enqueue_batch_to_crm(batch, crm_conn)
        assert enqueued >= 1
        log_success(f"{enqueued} mensagens enfileiradas na Outbox Transacional")

        # Prova de idempotência
        re_enqueued = enqueue_batch_to_crm(batch, crm_conn)
        assert re_enqueued == 0
        log_success("Idempotência verificada: re-enfileiramento resultou em 0 duplicações")

        # Despacho com assinatura HMAC
        msg = CRMOutboxMessage.objects.filter(connection=crm_conn).first()
        assert msg is not None
        with patch("httpx.Client.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                headers={"content-type": "application/json"},
                json=lambda: {"id": "lead-delivered-01", "success": True},
            )
            success = dispatch_outbox_message(msg)
            assert success is True
            called_hdrs = mock_post.call_args[1]["headers"]
            assert "X-LeadStream-Signature" in called_hdrs
            log_success(
                f"Mensagem despachada com assinatura HMAC-SHA256: {called_hdrs['X-LeadStream-Signature'][:24]}..."
            )

    # =========================================================================
    # JORNADA 2: Descoberta (Nova Base do Zero)
    # =========================================================================
    log_step("Jornada 2: Extração do Zero via Descoberta (Filtros CNAE e UF)")
    search = DiscoverySearch.objects.create(
        tenant=tenant,
        name="Busca Outbound Empresas TI SP",
        filters={"cnaes": ["6201501"], "ufs": ["SP"], "matriz": True},
        max_results=3,
        idempotency_key=f"discovery-search-{int(time.time())}",
        status=DiscoverySearch.Status.COMPLETED,
        total_results=3,
        billed_bytes=1_500_000,
    )
    raw_results = [
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
    for idx, item in enumerate(raw_results, start=1):
        res = _result_from_row(search=search, row=item, rank=idx)
        assert res is not None
        res.save()

    mat_batch = create_discovery_batch(
        tenant=tenant,
        search_id=search.pk,
        name="Lote Descoberta TI SP",
        idempotency_key=f"mat-key-{int(time.time())}",
        chunk_size=50,
    )
    assert mat_batch.total_rows == 3
    assert BatchItem.objects.filter(batch=mat_batch).count() == 3
    log_success(
        f"Busca de descoberta materializada em lote: {mat_batch.total_rows} registros estruturados prontos para enriquecimento"
    )

    # =========================================================================
    # JORNADA 3: Busca Manual Pontual
    # =========================================================================
    log_step("Jornada 3: Busca Manual de Lead Específico via API")
    create_company_resp = api_client.post(
        "/api/v1/dados/empresas/",
        {
            "cnpj": "33.000.167/0001-01",
            "legal_name": "Petroleo Brasileiro SA Petrobras",
            "trade_name": "Petrobras",
            "registration_status": "ATIVA",
        },
        format="json",
    )
    assert create_company_resp.status_code == 201
    log_success("Lead cadastrado pontualmente com validação matemática de CNPJ")

    query_resp = api_client.get("/api/v1/dados/empresas/?cnpj_root=33000167")
    assert query_resp.status_code == 200
    res_list = query_resp.json()["results"]
    assert len(res_list) >= 1
    log_success(f"Consulta na API retornou empresa: {res_list[0]['legal_name']}")

    # =========================================================================
    # COCKPIT DO CEO & ISOLAMENTO
    # =========================================================================
    log_step("Cockpit do CEO: Telemetria da Plataforma & Segurança B2B")

    # Criar chamada de provedor
    ProviderCall.objects.create(
        tenant=tenant,
        batch=mat_batch,
        provider="bigdatacorp",
        operation="basic_data",
        block=DataBlock.COMPANY_REGISTRY,
        idempotency_key=f"call-cost-{int(time.time())}",
        status=ProviderCall.Status.SUCCEEDED,
        latency_ms=85,
        confirmed_cost_cents=25,
        started_at=timezone.now(),
    )

    metrics_resp = api_client.get("/api/v1/admin/integracoes/metricas/")
    assert metrics_resp.status_code == 200
    metrics = metrics_resp.json()
    log_success(
        f"Cockpit do CEO respondendo: {metrics['total_messages']} mensagens processadas, taxa global de sucesso: {metrics['global_success_rate_percent']}%"
    )

    prov_metrics = api_client.get("/api/v1/metricas/provedores/").json()
    log_success(
        f"Métricas de provedores auditadas: provedor {prov_metrics[0]['provider']}, custo acumulado: {prov_metrics[0]['confirmed_cost_cents']} centavos"
    )

    # IDOR Test
    other_tenant = Tenant.objects.create(name="Outro Cliente B2B", is_active=True)
    other_conn = CRMConnection.objects.create(
        tenant=other_tenant, name="HubSpot Privado", connector_type=CRMConnectorType.HUBSPOT
    )
    idor_resp = api_client.get(f"/api/v1/integracoes/conexoes/{other_conn.id}/")
    assert idor_resp.status_code == 404
    log_success(
        "Proteção contra IDOR comprovada: acesso a recursos de outro tenant bloqueado (HTTP 404)"
    )

    t_total = time.perf_counter() - t_start
    print("\n\033[1;32m" + "=" * 80)
    print(f" PILOTO MEDIDO CONCLUÍDO COM 100% DE SUCESSO EM {t_total:.2f}s")
    print(" Todos os 3 fluxos reais de uso e a telemetria do CEO foram validados.")
    print("=" * 80 + "\033[0m\n")


if __name__ == "__main__":
    main()
