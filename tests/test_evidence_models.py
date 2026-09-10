from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from leadstream.entities.models import Entity
from leadstream.entities.services import create_company
from leadstream.evidence.models import (
    CaptureMethod,
    Evidence,
    EvidenceStatus,
    Observation,
    ProcessingPurpose,
    RetentionPolicy,
    Source,
    SourceRecord,
)
from leadstream.evidence.services import append_observation
from leadstream.tenancy.models import Tenant
from leadstream.tenancy.services import get_internal_tenant

pytestmark = pytest.mark.django_db


def build_context() -> tuple[Tenant, Entity, SourceRecord, Evidence]:
    tenant = get_internal_tenant()
    target = create_company(
        tenant=tenant,
        cnpj="04.252.011/0001-10",
        legal_name="Empresa Exemplo S.A.",
    ).company.entity
    purpose = ProcessingPurpose.objects.create(
        tenant=tenant,
        code="prospeccao-b2b",
        name="Prospecção B2B",
        description="Identificar decisores para relacionamento comercial profissional.",
        operational_basis="Legítimo interesse documentado e teste de balanceamento.",
    )
    retention = RetentionPolicy.objects.create(
        tenant=tenant,
        code="contato-profissional",
        name="Contato profissional",
        stale_after_days=90,
        retention_days=365,
    )
    source = Source.objects.create(
        tenant=tenant,
        slug="fixture-publica",
        name="Fixture pública",
        category=Source.Category.PUBLIC_WEB,
        priority=50,
    )
    captured = timezone.now()
    record = SourceRecord.objects.create(
        tenant=tenant,
        source=source,
        purpose=purpose,
        retention_policy=retention,
        external_id="record-1",
        source_url="https://example.test/registro/1",
        captured_at=captured,
    )
    evidence = Evidence.objects.create(
        tenant=tenant,
        source_record=record,
        url="https://example.test/perfil",
        captured_at=captured,
        observed_at=captured,
        method=CaptureMethod.WEB_PAGE,
        excerpt_hash="a" * 64,
        content_hash="b" * 64,
    )
    return tenant, target, record, evidence


def test_observacao_exige_proveniencia_e_confianca_valida() -> None:
    tenant, target, record, evidence = build_context()
    observation = append_observation(
        tenant=tenant,
        target=target,
        source_record=record,
        field_path="company.trade_name",
        value="Empresa Exemplo",
        status=EvidenceStatus.OBSERVED,
        confidence=85,
        method=CaptureMethod.WEB_PAGE,
        evidence_items=[evidence],
    )
    assert observation.evidence.get() == evidence
    assert observation.source_record.purpose.code == "prospeccao-b2b"

    invalid = Observation(
        tenant=tenant,
        target=target,
        source_record=record,
        field_path="company.trade_name",
        value="X",
        value_fingerprint="c" * 64,
        status=EvidenceStatus.OBSERVED,
        confidence=101,
        method=CaptureMethod.API,
        observed_at=timezone.now(),
        captured_at=timezone.now(),
    )
    with pytest.raises(ValidationError):
        invalid.full_clean()


def test_observacao_e_append_only_e_pode_ser_supersedida() -> None:
    tenant, target, record, _ = build_context()
    first = append_observation(
        tenant=tenant,
        target=target,
        source_record=record,
        field_path="company.trade_name",
        value="Nome anterior",
        status=EvidenceStatus.OBSERVED,
        confidence=60,
        method=CaptureMethod.API,
    )
    first.confidence = 99
    with pytest.raises(ValidationError, match="append-only"):
        first.save()
    with pytest.raises(ValidationError, match="append-only"):
        Observation.objects.filter(pk=first.pk).update(confidence=99)
    with pytest.raises(ValidationError, match="append-only"):
        first.delete()

    second = append_observation(
        tenant=tenant,
        target=target,
        source_record=record,
        field_path="company.trade_name",
        value="Nome atual",
        status=EvidenceStatus.CONFIRMED,
        confidence=95,
        method=CaptureMethod.API,
        supersedes=first,
        expires_at=timezone.now() + timedelta(days=90),
    )
    assert second.supersedes_id == first.pk
    assert Observation.objects.count() == 2


def test_rejeita_source_record_entre_tenants() -> None:
    tenant, _, record, _ = build_context()
    other = Tenant.objects.create(slug="other", name="Outro")
    record.tenant = other
    with pytest.raises(ValidationError, match="mesmo tenant"):
        record.full_clean()
    assert tenant.pk != other.pk


@pytest.mark.skipif(connection.vendor != "postgresql", reason="Trigger específico do PostgreSQL")
@pytest.mark.django_db(transaction=True)
def test_trigger_postgresql_bloqueia_sql_direto() -> None:
    tenant, target, record, _ = build_context()
    observation = append_observation(
        tenant=tenant,
        target=target,
        source_record=record,
        field_path="company.trade_name",
        value="Imutável",
        status=EvidenceStatus.OBSERVED,
        confidence=80,
        method=CaptureMethod.API,
    )
    with pytest.raises(DatabaseError, match="append-only"), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE leadstream_observation SET confidence = 81 WHERE id = %s",
                [observation.pk],
            )
