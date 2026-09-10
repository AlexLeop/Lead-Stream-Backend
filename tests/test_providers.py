from __future__ import annotations

from typing import Any

import httpx
import pytest
from django.test import override_settings

from leadstream.batches.models import Batch, BatchChunk, BatchItem
from leadstream.billing.models import BillableEvent, DataBlock, ProviderCall
from leadstream.entities.models import ContactPoint, Person, Relationship, SocialProfile
from leadstream.entities.normalization import fingerprint_value
from leadstream.entities.services import create_company
from leadstream.evidence.models import CaptureMethod, EvidenceStatus, Observation, SourceRecord
from leadstream.providers.adapters.apify import ApifyDecisionMakerAdapter
from leadstream.providers.adapters.bigdatacorp import BigDataCorpAdapter
from leadstream.providers.adapters.bigquery import BigQueryOpenCNPJAdapter, QueryResponse
from leadstream.providers.adapters.fixture import FixtureProviderAdapter
from leadstream.providers.contracts import (
    ContactCandidate,
    FieldObservation,
    PersonCandidate,
    ProviderContext,
    ProviderResult,
    SocialCandidate,
)
from leadstream.providers.discovery import execute_discovery_search
from leadstream.providers.exceptions import (
    ProviderBudgetExceeded,
    ProviderCircuitOpen,
    ProviderTemporaryError,
)
from leadstream.providers.executor import execute_provider
from leadstream.providers.models import (
    DiscoveryResult,
    DiscoverySearch,
    ProviderHealth,
    ProviderPolicy,
)
from leadstream.tenancy.services import get_internal_tenant

pytestmark = pytest.mark.django_db


def make_context(*, suffix: str = "001") -> ProviderContext:
    tenant = get_internal_tenant()
    identity = create_company(
        tenant=tenant,
        cnpj="04.252.011/0001-10",
        legal_name="Empresa Exemplo",
    )
    batch = Batch.objects.create(
        tenant=tenant,
        name=f"Lote provider {suffix}",
        source_type=Batch.SourceType.CSV,
        status=Batch.Status.COMPLETED,
        idempotency_key=f"provider-batch-{suffix}",
        total_rows=1,
        processed_rows=1,
        succeeded_rows=1,
    )
    item = BatchItem.objects.create(
        tenant=tenant,
        batch=batch,
        row_number=2,
        original_data={"CNPJ": "04.252.011/0001-10"},
        normalized_data={"cnpj": "04252011000110", "legal_name": "Empresa Exemplo"},
        hygiene_state=BatchItem.HygieneState.CORRECTED,
        fingerprint=fingerprint_value(("cnpj", "04252011000110")),
        entity=identity.company.entity,
        status=BatchItem.Status.SUCCEEDED,
    )
    return ProviderContext(
        tenant=tenant,
        batch=batch,
        item=item,
        cnpj="04252011000110",
        missing_blocks=frozenset(
            {
                DataBlock.COMPANY_REGISTRY,
                DataBlock.DECISION_MAKER,
                DataBlock.DIRECT_EMAIL,
                DataBlock.WHATSAPP,
                DataBlock.SOCIAL_PROFILES,
            }
        ),
    )


def make_policy(
    context: ProviderContext, *, slug: str = "fixture", **overrides: Any
) -> ProviderPolicy:
    values: dict[str, Any] = {
        "display_name": "Fixture",
        "enabled": True,
        "priority": 10,
        "requests_per_minute": 100,
        "estimated_cost_cents": 16,
        "daily_budget_cents": 1000,
        "batch_budget_cents": 1000,
        "failure_threshold": 2,
        "allowed_blocks": sorted(context.missing_blocks),
    }
    values.update(overrides)
    return ProviderPolicy.objects.create(
        tenant=context.tenant,
        provider=slug,
        **values,
    )


def test_executor_persiste_decisor_contatos_e_cobra_apenas_qualidade_suficiente() -> None:
    context = make_context()
    policy = make_policy(context)
    calls = 0

    def handler(request_context: ProviderContext) -> ProviderResult:
        nonlocal calls
        calls += 1
        assert request_context.cnpj == context.cnpj
        return ProviderResult(
            outcome=ProviderCall.Status.SUCCEEDED,
            confirmed_cost_cents=16,
            observations=(
                FieldObservation(
                    field_path="company.city",
                    value="São Paulo",
                    confidence=100,
                    evidence_status=EvidenceStatus.CONFIRMED,
                    method=CaptureMethod.API,
                    source_url="https://provider.example/company",
                ),
            ),
            people=(
                PersonCandidate(
                    full_name="João da Silva",
                    external_key="person-1",
                    qualification="Administrador",
                    observed_title="Diretor Comercial",
                    confidence=100,
                    evidence_status=EvidenceStatus.CONFIRMED,
                    contacts=(
                        ContactCandidate(
                            kind=ContactPoint.Kind.EMAIL,
                            value="joao@example.com",
                            confidence=95,
                            evidence_status=EvidenceStatus.TECHNICALLY_VALIDATED,
                            source_url="https://provider.example/person/1",
                        ),
                        ContactCandidate(
                            kind=ContactPoint.Kind.WHATSAPP,
                            value="+55 11 99999-9999",
                            confidence=75,
                            source_url="https://provider.example/person/1",
                        ),
                    ),
                    socials=(
                        SocialCandidate(
                            network=SocialProfile.Network.LINKEDIN,
                            profile_url="https://linkedin.com/in/joao",
                            confidence=80,
                            source_url="https://linkedin.com/in/joao",
                        ),
                    ),
                    source_url="https://provider.example/person/1",
                ),
            ),
            delivered_blocks=context.missing_blocks,
            external_request_id="req-1",
        )

    adapter = FixtureProviderAdapter("fixture", handler)
    execution = execute_provider(adapter=adapter, policy=policy, context=context)
    replay = execute_provider(adapter=adapter, policy=policy, context=context)

    assert execution.status == ProviderCall.Status.SUCCEEDED
    assert replay.call_id == execution.call_id
    assert calls == 1
    assert Person.objects.filter(entity__tenant=context.tenant).count() == 1
    assert Relationship.objects.filter(tenant=context.tenant).count() == 1
    assert ContactPoint.objects.filter(tenant=context.tenant).count() == 2
    assert SocialProfile.objects.filter(tenant=context.tenant).count() == 1
    assert Observation.objects.filter(tenant=context.tenant).count() >= 4
    assert SourceRecord.objects.filter(tenant=context.tenant).count() == 1
    assert execution.call_id is not None
    assert ProviderCall.objects.get(pk=execution.call_id).confirmed_cost_cents == 16
    assert BillableEvent.objects.filter(batch=context.batch).count() == 3
    assert sum(
        BillableEvent.objects.filter(batch=context.batch).values_list(
            "unit_price_cents", flat=True
        )
    ) == 34


def test_circuit_breaker_e_orcamento_bloqueiam_chamadas() -> None:
    context = make_context(suffix="002")
    policy = make_policy(context, slug="unstable", failure_threshold=2)

    def failing(_: ProviderContext) -> ProviderResult:
        raise ProviderTemporaryError("offline")

    adapter = FixtureProviderAdapter("unstable", failing)
    with pytest.raises(ProviderTemporaryError):
        execute_provider(adapter=adapter, policy=policy, context=context)
    with pytest.raises(ProviderTemporaryError):
        execute_provider(adapter=adapter, policy=policy, context=context)
    with pytest.raises(ProviderCircuitOpen):
        execute_provider(adapter=adapter, policy=policy, context=context)
    health = ProviderHealth.objects.get(policy=policy)
    assert health.consecutive_failures == 2
    assert health.circuit_open_until is not None
    assert ProviderCall.objects.filter(provider="unstable").count() == 2

    budget_context = make_context(suffix="003")
    budget_policy = make_policy(
        budget_context,
        slug="budget",
        estimated_cost_cents=10,
        batch_budget_cents=5,
    )
    budget_adapter = FixtureProviderAdapter(
        "budget",
        lambda _: ProviderResult(outcome="ABSENT", confirmed_cost_cents=0),
    )
    with pytest.raises(ProviderBudgetExceeded):
        execute_provider(adapter=budget_adapter, policy=budget_policy, context=budget_context)
    assert not ProviderCall.objects.filter(provider="budget").exists()


@override_settings(
    BIGQUERY_PROJECT_ID="project-test",
    OPEN_CNPJ_BIGQUERY_SQL="SELECT * FROM table WHERE cnpj=@cnpj",
    BIGQUERY_COST_CENTS_PER_TIB=100,
)
def test_adapter_bigquery_mapeia_empresa_e_qsa_sem_rede() -> None:
    context = make_context(suffix="004")

    def runner(sql: str, parameters: dict[str, Any]) -> QueryResponse:
        assert "@cnpj" in sql
        assert parameters == {"cnpj": context.cnpj}
        return QueryResponse(
            rows=(
                {
                    "razao_social": "Empresa Exemplo S.A.",
                    "municipio": "São Paulo",
                    "socios": [
                        {"nome_socio": "Maria Souza", "qualificacao_socio": "Administradora"}
                    ],
                },
            ),
            billed_bytes=0,
        )

    result = BigQueryOpenCNPJAdapter(runner=runner).enrich(context)
    assert result.outcome == ProviderCall.Status.SUCCEEDED
    assert result.observations[0].evidence_status == EvidenceStatus.CONFIRMED
    assert result.people[0].full_name == "Maria Souza"
    assert DataBlock.COMPANY_REGISTRY in result.delivered_blocks
    assert DataBlock.DECISION_MAKER in result.delivered_blocks


@override_settings(
    BIGDATACORP_ACCESS_TOKEN="test-token",
    BIGDATACORP_TOKEN_ID="test-id",
    BIGDATACORP_COST_CENTS=9,
)
def test_adapters_http_mapeiam_apenas_campos_explicitos() -> None:
    context = make_context(suffix="005")

    def bdc_handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["AccessToken"] == "test-token"
        return httpx.Response(
            200,
            json={
                "people": [
                    {
                        "name": "Ana Lima",
                        "role": "CEO",
                        "email": "ana@example.com",
                        "whatsapp": "+5511999999999",
                        "linkedinUrl": "https://linkedin.com/in/ana",
                    }
                ]
            },
            headers={"x-request-id": "bdc-1"},
        )

    with httpx.Client(transport=httpx.MockTransport(bdc_handler)) as client:
        result = BigDataCorpAdapter(client=client).enrich(context)
    assert result.people[0].full_name == "Ana Lima"
    assert {candidate.kind for candidate in result.people[0].contacts} == {
        ContactPoint.Kind.EMAIL,
        ContactPoint.Kind.WHATSAPP,
    }
    assert result.confirmed_cost_cents == 9


@override_settings(
    APIFY_TOKEN="test-token",
    APIFY_DECISION_MAKER_ACTOR_ID="vendor/actor",
    APIFY_COST_CENTS=7,
)
def test_adapter_apify_usa_actor_configurado_e_dataset_limpo() -> None:
    context = make_context(suffix="006")

    def handler(request: httpx.Request) -> httpx.Response:
        assert "/acts/vendor~actor/run-sync-get-dataset-items" in str(request.url)
        assert request.headers["Authorization"] == "Bearer test-token"
        return httpx.Response(
            200,
            json=[
                {
                    "fullName": "Carlos Melo",
                    "position": "Founder",
                    "linkedin": "https://linkedin.com/in/carlos",
                }
            ],
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = ApifyDecisionMakerAdapter(client=client).enrich(context)
    assert result.people[0].full_name == "Carlos Melo"
    assert result.people[0].socials[0].network == SocialProfile.Network.LINKEDIN
    assert result.confirmed_cost_cents == 7


def test_api_expoe_politicas_sem_credenciais_e_inicia_enriquecimento(
    api_client: Any,
    django_capture_on_commit_callbacks: Any,
) -> None:
    response = api_client.get("/api/v1/provedores/")
    assert response.status_code == 200
    assert len(response.json()) == 5
    assert all("token" not in str(item["config"]).casefold() for item in response.json())

    context = make_context(suffix="007")
    with pytest.MonkeyPatch.context() as monkeypatch:
        published: list[list[object]] = []
        monkeypatch.setattr(
            "leadstream.providers.pipeline._publish_chunks", lambda ids: published.append(ids)
        )
        with django_capture_on_commit_callbacks(execute=True):
            started = api_client.post(
                f"/api/v1/lotes/{context.batch.pk}/enriquecer/",
                {"blocks": [DataBlock.COMPANY_REGISTRY, DataBlock.DECISION_MAKER]},
                format="json",
            )
    assert started.status_code == 202
    assert started.json()["stage"] == BatchChunk.Stage.ENRICHMENT
    chunk = BatchChunk.objects.get(batch=context.batch, stage=BatchChunk.Stage.ENRICHMENT)
    assert chunk.requested_blocks == [DataBlock.COMPANY_REGISTRY, DataBlock.DECISION_MAKER]
    assert published == [[chunk.pk]]


@override_settings(
    BIGQUERY_PROJECT_ID="project-test",
    OPEN_CNPJ_DISCOVERY_SQL=(
        "SELECT * FROM table WHERE uf IN UNNEST(@ufs) LIMIT @limit OFFSET @offset"
    ),
    BIGQUERY_COST_CENTS_PER_TIB=3_500,
)
def test_descoberta_paginada_materializa_lote_idempotente(
    api_client: Any,
    django_capture_on_commit_callbacks: Any,
) -> None:
    with pytest.MonkeyPatch.context() as monkeypatch:
        dispatched: list[str] = []
        monkeypatch.setattr(
            "leadstream.providers.tasks.process_discovery_search_task.delay",
            lambda search_id: dispatched.append(search_id),
        )
        with django_capture_on_commit_callbacks(execute=True):
            response = api_client.post(
                "/api/v1/descobertas/",
                {
                    "name": "Empresas de tecnologia em SP",
                    "filters": {"cnaes": ["6201501"], "ufs": ["sp"], "matriz": True},
                    "max_results": 2,
                    "query_page_size": 100,
                },
                format="json",
                HTTP_IDEMPOTENCY_KEY="discovery-search-001",
            )
    assert response.status_code == 202
    search = DiscoverySearch.objects.get(pk=response.json()["id"])
    assert dispatched == [str(search.pk)]
    assert search.filters == {"cnaes": ["6201501"], "matriz": True, "ufs": ["SP"]}

    captured: list[dict[str, Any]] = []

    def runner(sql: str, parameters: dict[str, Any]) -> QueryResponse:
        assert "UNNEST(@ufs)" in sql
        captured.append(parameters)
        return QueryResponse(
            rows=(
                {
                    "cnpj": "04.252.011/0001-10",
                    "razao_social": "Empresa Exemplo Ltda",
                    "nome_fantasia": "Exemplo",
                    "cnae_fiscal": "6201501",
                    "uf": "SP",
                    "municipio": "São Paulo",
                    "situacao_cadastral": "ATIVA",
                    "porte": "ME",
                },
                {
                    "cnpj": "33.000.167/0001-01",
                    "razao_social": "Empresa Nacional S.A.",
                    "cnae_fiscal": "6201501",
                    "uf": "SP",
                    "municipio": "Santos",
                    "situacao_cadastral": "ATIVA",
                    "porte": "DEMAIS",
                },
            ),
            billed_bytes=1_000_000,
        )

    execution = execute_discovery_search(
        search_id=search.pk,
        worker_id="worker-discovery",
        adapter=BigQueryOpenCNPJAdapter(runner=runner),
    )
    assert execution.status == DiscoverySearch.Status.COMPLETED
    search.refresh_from_db()
    assert search.total_results == 2
    assert search.checkpoint_offset == 2
    assert DiscoveryResult.objects.filter(search=search).count() == 2
    assert captured == [
        {"cnaes": ["6201501"], "matriz": True, "ufs": ["SP"], "limit": 2, "offset": 0}
    ]

    first_page = api_client.get(f"/api/v1/descobertas/{search.pk}/resultados/?page_size=1")
    assert first_page.status_code == 200
    assert len(first_page.json()["results"]) == 1
    assert first_page.json()["next"] is not None

    with pytest.MonkeyPatch.context() as monkeypatch:
        chunks: list[str] = []
        monkeypatch.setattr(
            "leadstream.batches.tasks.process_chunk_task.delay",
            lambda chunk_id: chunks.append(chunk_id),
        )
        with django_capture_on_commit_callbacks(execute=True):
            materialized = api_client.post(
                f"/api/v1/descobertas/{search.pk}/materializar/",
                {"name": "Lote SP", "chunk_size": 50},
                format="json",
                HTTP_IDEMPOTENCY_KEY="discovery-batch-001",
            )
    assert materialized.status_code == 202
    batch = Batch.objects.get(pk=materialized.json()["id"])
    assert batch.source_type == Batch.SourceType.DISCOVERY
    assert batch.total_rows == 2
    assert batch.items.count() == 2
    assert batch.chunks.count() == 1
    assert chunks == [str(batch.chunks.get().pk)]

    replay = api_client.post(
        f"/api/v1/descobertas/{search.pk}/materializar/",
        {"name": "Outro nome", "chunk_size": 50},
        format="json",
        HTTP_IDEMPOTENCY_KEY="discovery-batch-001",
    )
    assert replay.status_code == 200
    assert replay.json()["id"] == str(batch.pk)


def test_api_bloqueia_descoberta_sem_bigquery_configurado(api_client: Any) -> None:
    response = api_client.post(
        "/api/v1/descobertas/",
        {"filters": {"ufs": ["SP"]}},
        format="json",
        HTTP_IDEMPOTENCY_KEY="discovery-disabled-001",
    )
    assert response.status_code == 503
    assert DiscoverySearch.objects.count() == 0
