from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from leadstream.entities.services import create_company
from leadstream.evidence.models import (
    CaptureMethod,
    EvidenceStatus,
    ProcessingPurpose,
    RetentionPolicy,
    Source,
    SourceRecord,
)
from leadstream.evidence.services import append_observation, canonicalize, open_conflict
from leadstream.tenancy.services import get_internal_tenant

pytestmark = pytest.mark.django_db


def setup_records() -> tuple[object, object, SourceRecord, SourceRecord]:
    tenant = get_internal_tenant()
    target = create_company(
        tenant=tenant,
        cnpj="04.252.011/0001-10",
        legal_name="Empresa Exemplo S.A.",
    ).company.entity
    purpose = ProcessingPurpose.objects.create(
        tenant=tenant,
        code="prospeccao",
        name="Prospecção",
        description="Prospecção profissional.",
        operational_basis="Legítimo interesse documentado.",
    )
    retention = RetentionPolicy.objects.create(
        tenant=tenant,
        code="padrao",
        name="Padrão",
        stale_after_days=90,
        retention_days=365,
    )
    now = timezone.now()
    high = Source.objects.create(
        tenant=tenant,
        slug="high",
        name="Alta prioridade",
        category=Source.Category.GOVERNMENT,
        priority=100,
    )
    low = Source.objects.create(
        tenant=tenant,
        slug="low",
        name="Baixa prioridade",
        category=Source.Category.PUBLIC_WEB,
        priority=10,
    )
    high_record = SourceRecord.objects.create(
        tenant=tenant,
        source=high,
        purpose=purpose,
        retention_policy=retention,
        external_id="high-1",
        captured_at=now,
    )
    low_record = SourceRecord.objects.create(
        tenant=tenant,
        source=low,
        purpose=purpose,
        retention_policy=retention,
        external_id="low-1",
        captured_at=now,
    )
    return tenant, target, high_record, low_record


def test_canonizacao_prioriza_estado_antes_da_fonte_e_preserva_rotulo() -> None:
    tenant, target, high_record, low_record = setup_records()
    observed = append_observation(
        tenant=tenant,  # type: ignore[arg-type]
        target=target,  # type: ignore[arg-type]
        source_record=high_record,
        field_path="person.email",
        value="observado@example.test",
        status=EvidenceStatus.OBSERVED,
        confidence=99,
        method=CaptureMethod.DATASET,
    )
    confirmed = append_observation(
        tenant=tenant,  # type: ignore[arg-type]
        target=target,  # type: ignore[arg-type]
        source_record=low_record,
        field_path="person.email",
        value="confirmado@example.test",
        status=EvidenceStatus.CONFIRMED,
        confidence=80,
        method=CaptureMethod.API,
    )
    decision = canonicalize(
        tenant=tenant,
        target=target,
        field_path="person.email",  # type: ignore[arg-type]
    )
    assert decision.selected_observation == confirmed
    assert decision.decision_status == EvidenceStatus.CONFIRMED
    assert decision.selected_observation != observed

    inferred = append_observation(
        tenant=tenant,  # type: ignore[arg-type]
        target=target,  # type: ignore[arg-type]
        source_record=high_record,
        field_path="person.buying_role",
        value="Decisor",
        status=EvidenceStatus.INFERRED,
        confidence=90,
        method=CaptureMethod.INFERENCE,
    )
    inferred_decision = canonicalize(
        tenant=tenant,
        target=target,
        field_path="person.buying_role",  # type: ignore[arg-type]
    )
    assert inferred_decision.selected_observation == inferred
    assert inferred_decision.decision_status == EvidenceStatus.INFERRED


def test_exclui_estado_inelegivel_expirado_e_suprimido_por_predicado() -> None:
    tenant, target, high_record, _ = setup_records()
    now = timezone.now()
    expired = append_observation(
        tenant=tenant,  # type: ignore[arg-type]
        target=target,  # type: ignore[arg-type]
        source_record=high_record,
        field_path="person.phone",
        value="+5511999999999",
        status=EvidenceStatus.CONFIRMED,
        confidence=100,
        method=CaptureMethod.API,
        expires_at=now - timedelta(seconds=1),
    )
    rejected = append_observation(
        tenant=tenant,  # type: ignore[arg-type]
        target=target,  # type: ignore[arg-type]
        source_record=high_record,
        field_path="person.phone",
        value="+5511888888888",
        status=EvidenceStatus.REJECTED,
        confidence=100,
        method=CaptureMethod.API,
    )
    eligible_but_suppressed = append_observation(
        tenant=tenant,  # type: ignore[arg-type]
        target=target,  # type: ignore[arg-type]
        source_record=high_record,
        field_path="person.phone",
        value="+5511777777777",
        status=EvidenceStatus.OBSERVED,
        confidence=80,
        method=CaptureMethod.API,
    )
    decision = canonicalize(
        tenant=tenant,  # type: ignore[arg-type]
        target=target,  # type: ignore[arg-type]
        field_path="person.phone",
        suppression_check=lambda item: item.pk == eligible_but_suppressed.pk,
        now=now,
    )
    assert decision.selected_observation is None
    assert decision.decision_status == EvidenceStatus.ABSENT
    assert {expired.status, rejected.status} == {
        EvidenceStatus.CONFIRMED,
        EvidenceStatus.REJECTED,
    }


def test_conflito_e_recanonizacao_preservam_historico() -> None:
    tenant, target, high_record, low_record = setup_records()
    first = append_observation(
        tenant=tenant,  # type: ignore[arg-type]
        target=target,  # type: ignore[arg-type]
        source_record=high_record,
        field_path="company.trade_name",
        value="Marca A",
        status=EvidenceStatus.OBSERVED,
        confidence=70,
        method=CaptureMethod.DATASET,
    )
    second = append_observation(
        tenant=tenant,  # type: ignore[arg-type]
        target=target,  # type: ignore[arg-type]
        source_record=low_record,
        field_path="company.trade_name",
        value="Marca B",
        status=EvidenceStatus.OBSERVED,
        confidence=90,
        method=CaptureMethod.WEB_PAGE,
    )
    conflict = open_conflict(
        tenant=tenant,  # type: ignore[arg-type]
        target=target,  # type: ignore[arg-type]
        field_path="company.trade_name",
        observations=[first, second],
    )
    before = canonicalize(
        tenant=tenant,
        target=target,
        field_path="company.trade_name",  # type: ignore[arg-type]
    )
    after = canonicalize(
        tenant=tenant,
        target=target,
        field_path="company.trade_name",  # type: ignore[arg-type]
    )
    assert set(conflict.observations.values_list("pk", flat=True)) == {first.pk, second.pk}
    assert before.version == 1
    assert after.version == 2
    assert before.pk != after.pk
    before.reason = "tentativa de alteração"
    with pytest.raises(ValidationError, match="append-only"):
        before.save()
