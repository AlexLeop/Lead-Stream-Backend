from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone

from leadstream.batches.models import Batch, BatchChunk, BatchItem, ProcessingAttempt
from leadstream.billing.models import BillableEvent, DataBlock, ProviderCall
from leadstream.entities.models import Company, ContactPoint, Person, Relationship, SocialProfile
from leadstream.entities.normalization import fingerprint_value
from leadstream.entities.services import create_company
from leadstream.evidence.models import CaptureMethod, EvidenceStatus, Observation, SourceRecord
from leadstream.providers.adapters.apify import ApifyDecisionMakerAdapter
from leadstream.providers.adapters.bigdatacorp import BigDataCorpAdapter
from leadstream.providers.adapters.bigquery import BigQueryOpenCNPJAdapter, QueryResponse
from leadstream.providers.adapters.fixture import FixtureProviderAdapter
from leadstream.providers.adapters.portal_transparencia import (
    PortalTransparenciaAdapter,
    portal_requests_per_minute,
)
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
    ProviderRateLimited,
    ProviderTemporaryError,
)
from leadstream.providers.executor import execute_provider
from leadstream.providers.models import (
    DiscoveryResult,
    DiscoverySearch,
    ProviderHealth,
    ProviderPolicy,
)
from leadstream.providers.pipeline import process_enrichment_chunk
from leadstream.providers.resilience import _rate_limit, reserve_shared_rate_limit
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
    assert (
        sum(
            BillableEvent.objects.filter(batch=context.batch).values_list(
                "unit_price_cents", flat=True
            )
        )
        == 34
    )


def test_contato_cadastral_da_empresa_nao_vira_contato_direto_do_decisor() -> None:
    context = make_context(suffix="company-contact")
    policy = make_policy(context, slug="company-contact-fixture")

    result = ProviderResult(
        outcome=ProviderCall.Status.SUCCEEDED,
        confirmed_cost_cents=1,
        observations=(
            FieldObservation(
                field_path="company.city",
                value="São Paulo",
                confidence=100,
                evidence_status=EvidenceStatus.CONFIRMED,
                method=CaptureMethod.DATASET,
            ),
        ),
        company_contacts=(
            ContactCandidate(
                kind=ContactPoint.Kind.EMAIL,
                value="contato@empresa.example",
                confidence=100,
                evidence_status=EvidenceStatus.OBSERVED,
            ),
        ),
    )
    execution = execute_provider(
        adapter=FixtureProviderAdapter("company-contact-fixture", lambda _: result),
        policy=policy,
        context=context,
    )

    contact = ContactPoint.objects.get(normalized_value="contato@empresa.example")
    assert contact.owner_id == context.item.entity_id
    assert execution.delivered_blocks == frozenset({DataBlock.COMPANY_REGISTRY})
    assert not BillableEvent.objects.filter(
        batch=context.batch,
        block__in=(DataBlock.DIRECT_EMAIL, DataBlock.DIRECT_PHONE),
    ).exists()


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
                    "email": "contato@empresa.example",
                    "ddd_1": "11",
                    "telefone_1": "33334444",
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
    assert result.people[0].contacts == ()
    assert {candidate.kind for candidate in result.company_contacts} == {
        ContactPoint.Kind.EMAIL,
        ContactPoint.Kind.PHONE,
    }
    assert DataBlock.COMPANY_REGISTRY in result.delivered_blocks
    assert DataBlock.DECISION_MAKER in result.delivered_blocks
    assert DataBlock.DIRECT_EMAIL not in result.delivered_blocks
    assert DataBlock.DIRECT_PHONE not in result.delivered_blocks


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
    APIFY_USD_RATE_CENTS=600,
    APIFY_RUN_TIMEOUT_SECONDS=300,
    APIFY_DATASET_PAGE_SIZE=100,
)
def test_adapter_apify_usa_actor_configurado_e_dataset_limpo() -> None:
    context = make_context(suffix="006")
    call = ProviderCall.objects.create(
        tenant=context.tenant,
        batch=context.batch,
        item=context.item,
        provider="apify-decision-maker",
        operation="enrich",
        block=DataBlock.DECISION_MAKER,
        idempotency_key="apify-test-call-006",
        estimated_cost_cents=100,
        status="REQUESTED",
        execution_token="token-006",
        started_at=timezone.now(),
    )
    context = replace(context, call_id=str(call.pk), execution_token="token-006")

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        assert request.headers["Authorization"] == "Bearer test-token"
        if "/actors/vendor~actor/runs" in url_str:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "id": "run-test-001",
                        "defaultDatasetId": "dataset-test-001",
                        "status": "SUCCEEDED",
                        "usageTotalUsd": "0.0116666",
                    }
                },
            )
        if "/datasets/dataset-test-001/items" in url_str:
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
        raise AssertionError(f"URL inesperada: {url_str}")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = ApifyDecisionMakerAdapter(client=client).enrich(context)
    assert result.people[0].full_name == "Carlos Melo"
    assert result.people[0].socials[0].network == SocialProfile.Network.LINKEDIN
    assert result.confirmed_cost_cents == 7
    assert result.external_request_id == "run-test-001"


@override_settings(
    APIFY_TOKEN="test-token",
    APIFY_DECISION_MAKER_ACTOR_ID="apify/google-search-scraper",
    APIFY_BASE_URL="https://api.apify.com/v2",
    APIFY_USD_RATE_CENTS=600,
    APIFY_COST_CENTS=25,
)
def test_apify_google_search_scraper_resolve_decisor_e_linkedin() -> None:
    context = make_context(suffix="006b")
    call = ProviderCall.objects.create(
        tenant=context.tenant,
        batch=context.batch,
        item=context.item,
        provider="apify-decision-maker",
        operation="enrich",
        block=DataBlock.DECISION_MAKER,
        idempotency_key="apify-test-call-006b",
        estimated_cost_cents=100,
        status="REQUESTED",
        execution_token="token-006b",
        started_at=timezone.now(),
    )
    context = replace(context, call_id=str(call.pk), execution_token="token-006b")

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        assert request.headers["Authorization"] == "Bearer test-token"
        if "/actors/apify~google-search-scraper/runs" in url_str:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "id": "run-google-001",
                        "defaultDatasetId": "dataset-google-001",
                        "status": "SUCCEEDED",
                        "usageTotalUsd": "0.005",
                    }
                },
            )
        if "/datasets/dataset-google-001/items" in url_str:
            return httpx.Response(
                200,
                json=[
                    {
                        "organicResults": [
                            {
                                "title": "Alex Leopoldo Da Silva - Diretor Executivo | LinkedIn",
                                "url": "https://br.linkedin.com/in/alexleop/en",
                                "description": "Alex Leopoldo. Especialista em dados.",
                            }
                        ]
                    }
                ],
            )
        raise AssertionError(f"URL inesperada: {url_str}")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = ApifyDecisionMakerAdapter(client=client).enrich(context)
    assert len(result.people) == 1
    assert result.people[0].full_name == "Alex Leopoldo Da Silva"
    assert result.people[0].socials[0].network == SocialProfile.Network.LINKEDIN
    assert result.people[0].socials[0].profile_url == "https://linkedin.com/in/alexleop"
    assert result.confirmed_cost_cents == 3
    assert result.external_request_id == "run-google-001"


def test_api_expoe_politicas_sem_credenciais_e_inicia_enriquecimento(
    api_client: Any,
    django_capture_on_commit_callbacks: Any,
) -> None:
    response = api_client.get("/api/v1/provedores/")
    assert response.status_code == 200
    assert len(response.json()) == 6
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
    PORTAL_TRANSPARENCIA_TOKEN="test-token",
    PORTAL_TRANSPARENCIA_BASE_URL="https://api.portaldatransparencia.gov.br/api-de-dados",
    PORTAL_TRANSPARENCIA_COST_CENTS=0,
    PORTAL_TRANSPARENCIA_DAY_RPM=400,
    PORTAL_TRANSPARENCIA_NIGHT_RPM=700,
    PORTAL_TRANSPARENCIA_RESTRICTED_RPM=180,
    PORTAL_TRANSPARENCIA_CACHE_SECONDS=60,
    PORTAL_TRANSPARENCIA_MAX_PAGES=3,
    PORTAL_TRANSPARENCIA_MAX_DETAIL_RECORDS=3,
    PORTAL_TRANSPARENCIA_EXPENSE_LOOKBACK_YEARS=2,
)
def test_portal_transparencia_mapeia_risco_e_contratos_sem_expor_token() -> None:
    cache.clear()
    context = replace(
        make_context(suffix="portal-001"),
        missing_blocks=frozenset({DataBlock.GOVERNMENT_RISK, DataBlock.PUBLIC_SECTOR}),
    )
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["chave-api-dados"] == "test-token"
        requests.append(request.url.path)
        if request.url.path.endswith("/pessoa-juridica"):
            assert request.url.params["cnpj"] == context.cnpj
            return httpx.Response(
                200,
                json=[
                    {
                        "cnpj": context.cnpj,
                        "razaoSocial": "Empresa Exemplo",
                        "possuiContratacao": True,
                        "emitiuNFe": False,
                        "favorecidoDespesas": False,
                        "favorecidoTransferencias": False,
                    }
                ],
            )
        if request.url.path.endswith(
            (
                "/contratos/termo-aditivo",
                "/contratos/documentos-relacionados",
                "/contratos/apostilamento",
            )
        ):
            assert request.url.params["id"] == "456"
            return httpx.Response(200, json=[])
        assert request.url.params["pagina"] == "1" or request.url.params["pagina"] == "2"
        if request.url.params["pagina"] == "2":
            return httpx.Response(200, json=[])
        if request.url.path.endswith("/ceis"):
            assert request.url.params["codigoSancionado"] == context.cnpj
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 123,
                        "dataInicioSancao": "01/01/2026",
                        "tipoSancao": {"descricaoPortal": "Suspensão"},
                        "orgaoSancionador": {"nome": "Órgão Exemplo"},
                        "sancionado": {
                            "nome": "Empresa Exemplo",
                            "codigoFormatado": "04.252.011/0001-10",
                        },
                        "linkPublicacao": "https://gov.example/publicacao/123",
                    }
                ],
                headers={"x-request-id": "ceis-123"},
            )
        if request.url.path.endswith("/contratos/cpf-cnpj"):
            assert request.url.params["cpfCnpj"] == context.cnpj
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 456,
                        "numero": "10/2026",
                        "objeto": "Serviços de tecnologia",
                        "situacaoContrato": "ATIVO",
                        "unidadeGestora": {"nome": "Ministério Exemplo"},
                        "fornecedor": {"cnpjFormatado": "04.252.011/0001-10"},
                        "valorFinalCompra": 120000.5,
                    }
                ],
                headers={"x-request-id": "contract-456"},
            )
        return httpx.Response(200, json=[])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        adapter = PortalTransparenciaAdapter(client=client)
        result = adapter.enrich(context)
        policy = make_policy(context, slug=adapter.slug, estimated_cost_cents=0)
        execution = execute_provider(adapter=adapter, policy=policy, context=context)

    assert len(requests) == 12
    assert result.delivered_blocks == frozenset(
        {DataBlock.GOVERNMENT_RISK, DataBlock.PUBLIC_SECTOR}
    )
    risk = result.observations[0].value
    assert risk["has_matches"] is True
    assert risk["records"][0]["sanction_type"] == "Suspensão"
    company = Company.objects.get(entity=context.item.entity)
    assert company.government_risk["match_count"] == 1
    assert company.public_sector_profile["contracts"][0]["number"] == "10/2026"
    assert company.public_sector_profile["indexed_in_portal"] is True
    assert company.public_sector_profile["strategy"] == "PROFILE_GUIDED_WITH_BOUNDED_DETAILS"
    assert "notas-fiscais" not in company.public_sector_profile["executed_endpoints"]
    assert any(
        item["endpoint"] == "notas-fiscais"
        for item in company.public_sector_profile["skipped_endpoints"]
    )
    assert execution.delivered_blocks == frozenset(
        {DataBlock.GOVERNMENT_RISK, DataBlock.PUBLIC_SECTOR}
    )
    assert "test-token" not in str(
        Observation.objects.filter(target=context.item.entity).values_list(
            "value", "source_record__source_url"
        )
    )


@override_settings(
    PORTAL_TRANSPARENCIA_TOKEN="test-token",
    PORTAL_TRANSPARENCIA_BASE_URL="https://api.portaldatransparencia.gov.br/api-de-dados",
    PORTAL_TRANSPARENCIA_DAY_RPM=400,
    PORTAL_TRANSPARENCIA_NIGHT_RPM=700,
    PORTAL_TRANSPARENCIA_RESTRICTED_RPM=180,
    PORTAL_TRANSPARENCIA_CACHE_SECONDS=60,
    PORTAL_TRANSPARENCIA_MAX_PAGES=3,
    PORTAL_TRANSPARENCIA_MAX_DETAIL_RECORDS=3,
    PORTAL_TRANSPARENCIA_EXPENSE_LOOKBACK_YEARS=2,
)
def test_portal_usa_perfil_para_pular_rotas_publicas_sem_sinal() -> None:
    cache.clear()
    context = replace(
        make_context(suffix="portal-profile-guided"),
        missing_blocks=frozenset({DataBlock.PUBLIC_SECTOR}),
    )
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        assert request.url.path.endswith("/pessoa-juridica")
        return httpx.Response(
            200,
            json=[
                {
                    "cnpj": context.cnpj,
                    "razaoSocial": "Empresa sem vínculo público",
                    "possuiContratacao": False,
                    "emitiuNFe": False,
                    "favorecidoDespesas": False,
                    "favorecidoTransferencias": False,
                    "beneficiadoRenunciaFiscal": False,
                    "isentoImuneRenunciaFiscal": False,
                    "habilitadoRenunciaFiscal": False,
                }
            ],
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = PortalTransparenciaAdapter(client=client).enrich(context)

    assert requests == ["/api-de-dados/pessoa-juridica"]
    public_profile = result.observations[0].value
    assert public_profile["executed_endpoints"] == ["pessoa-juridica"]
    assert public_profile["contract_count"] == 0
    assert public_profile["invoice_count"] == 0
    assert len(public_profile["skipped_endpoints"]) == 8


@override_settings(
    PORTAL_TRANSPARENCIA_TOKEN="test-token",
    PORTAL_TRANSPARENCIA_BASE_URL="https://api.portaldatransparencia.gov.br/api-de-dados",
    PORTAL_TRANSPARENCIA_DAY_RPM=400,
    PORTAL_TRANSPARENCIA_NIGHT_RPM=700,
    PORTAL_TRANSPARENCIA_RESTRICTED_RPM=180,
    PORTAL_TRANSPARENCIA_CACHE_SECONDS=60,
    PORTAL_TRANSPARENCIA_MAX_PAGES=3,
    PORTAL_TRANSPARENCIA_EXPENSE_LOOKBACK_YEARS=2,
)
def test_portal_pf_preserva_sinal_social_sem_expor_identificador_auxiliar() -> None:
    cache.clear()
    cpf = "52998224725"
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        assert request.headers["chave-api-dados"] == "test-token"
        if request.url.path.endswith("/pessoa-fisica"):
            assert request.url.params["cpf"] == cpf
            return httpx.Response(
                200,
                json=[
                    {
                        "cpf": cpf,
                        "nome": "PESSOA EXEMPLO",
                        "servidor": False,
                        "servidorInativo": False,
                        "beneficiarioDiarias": False,
                        "permissionario": False,
                        "contratado": False,
                        "sancionadoCEIS": False,
                        "sancionadoCNEP": False,
                        "sancionadoCEAF": False,
                        "portadorCPDC": False,
                        "portadorCPGF": False,
                        "favorecidoDespesas": False,
                        "favorecidoTransferencias": False,
                        "favorecidoCPCC": False,
                        "favorecidoCPDC": False,
                        "favorecidoCPGF": False,
                        "participanteLicitacao": False,
                        "beneficiarioBolsaFamilia": True,
                    }
                ],
            )
        assert request.url.path.endswith("/peps")
        assert request.url.params["cpf"] == cpf
        assert request.url.params["pagina"] == "1"
        return httpx.Response(200, json=[])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = PortalTransparenciaAdapter(client=client).enrich_person(cpf)

    assert requests == ["/api-de-dados/pessoa-fisica", "/api-de-dados/peps"]
    assert result["strategy"] == "PROFILE_GUIDED_COMPLETE"
    assert result["executed_endpoints"] == ["pessoa-fisica", "peps"]
    assert result["profile"]["social_flags"]["bolsa_familia"] is True
    assert result["social_benefits"]["records"] == []
    assert cpf not in str(result)


@override_settings(
    PORTAL_TRANSPARENCIA_TOKEN="test-token",
    PORTAL_TRANSPARENCIA_BASE_URL="https://api.portaldatransparencia.gov.br/api-de-dados",
    PORTAL_TRANSPARENCIA_CACHE_SECONDS=60,
    PORTAL_TRANSPARENCIA_MAX_PAGES=1,
    PORTAL_TRANSPARENCIA_EXPENSE_LOOKBACK_YEARS=1,
    PORTAL_TRANSPARENCIA_REMUNERATION_LOOKBACK_MONTHS=1,
)
def test_portal_pf_consulta_beneficio_remuneracao_e_pensao_sinalizados() -> None:
    cache.clear()
    cpf = "52998224725"
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        path = request.url.path
        if path.endswith("/pessoa-fisica"):
            return httpx.Response(
                200,
                json=[
                    {
                        "cpf": cpf,
                        "nis": "12345678901",
                        "nome": "PESSOA EXEMPLO",
                        "servidor": True,
                        "servidorInativo": False,
                        "pensionistaOuRepresentanteLegal": True,
                        "instituidorPensao": False,
                        "favorecidoBolsaFamilia": True,
                    }
                ],
            )
        if path.endswith("/servidores"):
            return httpx.Response(200, json=[{"nome": "PESSOA EXEMPLO", "cpf": cpf}])
        if path.endswith("/servidores/remuneracao"):
            assert len(request.url.params["mesAno"]) == 6
            return httpx.Response(200, json=[{"valorRemuneracaoAposDeducoes": 5000}])
        if path.endswith("/bolsa-familia-sacado-por-nis"):
            assert request.url.params["nis"] == "12345678901"
            return httpx.Response(200, json=[{"valorSaque": 600, "nis": "12345678901"}])
        if path.endswith("/peps"):
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=[])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = PortalTransparenciaAdapter(client=client).enrich_person(cpf)

    assert any(path.endswith("/bolsa-familia-sacado-por-nis") for path in requests)
    assert any(path.endswith("/servidores/remuneracao") for path in requests)
    assert result["social_benefits"]["records"][0]["program"] == "bolsa_familia"
    assert result["public_sector"]["remuneration_records"]
    assert result["public_sector"]["pension_records"]
    assert cpf not in str(result)
    assert "12345678901" not in str(result)


@override_settings(
    PORTAL_TRANSPARENCIA_DAY_RPM=400,
    PORTAL_TRANSPARENCIA_NIGHT_RPM=700,
    PORTAL_TRANSPARENCIA_RESTRICTED_RPM=180,
)
def test_portal_transparencia_aplica_janelas_oficiais_de_quota() -> None:
    tz = ZoneInfo("America/Sao_Paulo")
    assert portal_requests_per_minute(moment=datetime(2026, 9, 15, 2, tzinfo=tz)) == 700
    assert portal_requests_per_minute(moment=datetime(2026, 9, 15, 10, tzinfo=tz)) == 400
    assert portal_requests_per_minute(
        restricted=True,
        moment=datetime(2026, 9, 15, 2, tzinfo=tz),
    ) == 180


def test_quota_compartilhada_contabiliza_requisicoes_reais() -> None:
    cache.clear()
    context = make_context(suffix="quota-units")
    policy = make_policy(
        context,
        slug="quota-units",
        requests_per_minute=5,
    )
    _rate_limit(
        tenant=context.tenant,
        policy=policy,
        scope="shared-token",
        requests_per_minute=5,
        units=4,
    )
    with pytest.raises(ProviderRateLimited):
        _rate_limit(
            tenant=context.tenant,
            policy=policy,
            scope="shared-token",
            requests_per_minute=5,
            units=2,
        )


def test_adapter_pode_contabilizar_quota_por_requisicao_real() -> None:
    cache.clear()
    context = make_context(suffix="quota-adapter-managed")
    policy = make_policy(context, slug="quota-adapter-managed", requests_per_minute=1)

    _rate_limit(
        tenant=context.tenant,
        policy=policy,
        scope="adapter-managed",
        requests_per_minute=1,
        units=0,
    )
    reserve_shared_rate_limit(scope="adapter-managed", requests_per_minute=1)
    with pytest.raises(ProviderRateLimited):
        reserve_shared_rate_limit(scope="adapter-managed", requests_per_minute=1)


def test_resposta_429_nao_consumira_tentativas_tecnicas_do_provedor() -> None:
    context = make_context(suffix="provider-429")
    policy = make_policy(
        context,
        slug="provider-429",
        max_retries=0,
    )

    def limited(_: ProviderContext) -> ProviderResult:
        raise ProviderRateLimited("Quota externa atingida.", retry_after_seconds=30)

    adapter = FixtureProviderAdapter("provider-429", limited)
    with pytest.raises(ProviderRateLimited):
        execute_provider(adapter=adapter, policy=policy, context=context)
    with pytest.raises(ProviderRateLimited):
        execute_provider(adapter=adapter, policy=policy, context=context)

    calls = ProviderCall.objects.filter(provider="provider-429").order_by("started_at")
    assert calls.count() == 2
    assert set(calls.values_list("error_code", flat=True)) == {"ProviderRateLimited"}
    health = ProviderHealth.objects.get(policy=policy)
    assert health.consecutive_failures == 0
    assert health.circuit_open_until is None


def test_chunk_aguarda_quota_sem_consumir_tentativa_tecnica(monkeypatch: Any) -> None:
    context = make_context(suffix="quota-deferral")
    chunk = BatchChunk.objects.create(
        tenant=context.tenant,
        batch=context.batch,
        stage=BatchChunk.Stage.ENRICHMENT,
        requested_blocks=[DataBlock.GOVERNMENT_RISK],
        sequence=1,
        start_row=context.item.row_number,
        end_row=context.item.row_number,
        checkpoint_row=context.item.row_number - 1,
        max_attempts=5,
    )

    def limited(**_: Any) -> None:
        raise ProviderRateLimited("Aguardar quota.", retry_after_seconds=17)

    monkeypatch.setattr("leadstream.providers.pipeline.run_enrichment_cascade", limited)
    result = process_enrichment_chunk(chunk_id=chunk.pk, worker_id="worker-quota")

    chunk.refresh_from_db()
    attempt = ProcessingAttempt.objects.get(chunk=chunk)
    assert result.status == BatchChunk.Status.PENDING
    assert result.retry_after_seconds == 17
    assert chunk.status == BatchChunk.Status.PENDING
    assert chunk.max_attempts == 6
    assert chunk.attempt_count == 1
    assert attempt.status == ProcessingAttempt.Status.ABANDONED
    assert attempt.error_code == "PROVIDER_RATE_LIMITED"


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
