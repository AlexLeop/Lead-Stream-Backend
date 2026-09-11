from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.test import override_settings
from django.utils import timezone

from leadstream.entities.models import ContactPoint
from leadstream.entities.services import create_company, create_contact_point, create_person
from leadstream.evidence.models import (
    CaptureMethod,
    EvidenceStatus,
    ProcessingPurpose,
    RetentionPolicy,
    Source,
    SourceRecord,
)
from leadstream.evidence.services import append_observation, canonicalize
from leadstream.governance.models import Suppression
from leadstream.governance.services import (
    apply_retention,
    create_suppression,
    is_suppressed,
)
from leadstream.tenancy.models import Tenant
from leadstream.tenancy.services import get_internal_tenant

pytestmark = pytest.mark.django_db


@override_settings(DATA_HASH_KEY="test-hmac-current", DATA_HASH_KEY_VERSION="v2")
def test_supressao_e_hmac_idempotente_sem_valor_bruto() -> None:
    tenant = get_internal_tenant()
    person = create_person(tenant=tenant, full_name="Decisor", external_key="d1")
    contact = create_contact_point(
        tenant=tenant,
        owner=person.entity,
        kind=ContactPoint.Kind.EMAIL,
        value="Decisor@Example.com",
    )
    first = create_suppression(
        tenant=tenant,
        scope=Suppression.Scope.EMAIL,
        value="decisor@example.com",
        reason="Solicitação do titular",
    )
    second = create_suppression(
        tenant=tenant,
        scope=Suppression.Scope.EMAIL,
        value="DECISOR@EXAMPLE.COM",
        reason="Repetição idempotente",
    )
    contact.refresh_from_db()

    assert first.pk == second.pk
    assert first.value_digest != "decisor@example.com"
    assert not hasattr(first, "raw_value")
    assert contact.status == ContactPoint.Status.SUPPRESSED
    assert is_suppressed(tenant=tenant, scope=Suppression.Scope.EMAIL, value="decisor@example.com")


@override_settings(
    DATA_HASH_KEY="current-secret",
    DATA_HASH_KEY_VERSION="v2",
    DATA_HASH_PREVIOUS_KEYS=["v1:previous-secret"],
)
def test_consulta_chave_anterior_e_isolamento_por_tenant() -> None:
    internal = get_internal_tenant()
    other = Tenant.objects.create(slug="other", name="Outro")
    with override_settings(DATA_HASH_KEY="previous-secret", DATA_HASH_KEY_VERSION="v1"):
        create_suppression(
            tenant=internal,
            scope=Suppression.Scope.DOMAIN,
            value="example.com",
            reason="Bloqueio anterior",
        )
    assert is_suppressed(
        tenant=internal, scope=Suppression.Scope.DOMAIN, value="https://www.example.com"
    )
    assert not is_suppressed(tenant=other, scope=Suppression.Scope.DOMAIN, value="example.com")


@override_settings(DATA_HASH_KEY="test-hmac", DATA_HASH_KEY_VERSION="v1")
def test_supressao_prevalece_na_canonizacao() -> None:
    tenant = get_internal_tenant()
    person = create_person(tenant=tenant, full_name="Decisor", external_key="d2")
    purpose = ProcessingPurpose.objects.create(
        tenant=tenant,
        code="prospeccao",
        name="Prospecção",
        description="Contato profissional.",
        operational_basis="Legítimo interesse documentado.",
    )
    retention = RetentionPolicy.objects.create(
        tenant=tenant,
        code="padrao",
        name="Padrão",
        stale_after_days=90,
        retention_days=365,
    )
    source = Source.objects.create(
        tenant=tenant,
        slug="fixture",
        name="Fixture",
        category=Source.Category.PUBLIC_WEB,
        priority=50,
    )
    record = SourceRecord.objects.create(
        tenant=tenant,
        source=source,
        purpose=purpose,
        retention_policy=retention,
        external_id="r1",
        captured_at=timezone.now(),
    )
    observation = append_observation(
        tenant=tenant,
        target=person.entity,
        source_record=record,
        field_path="person.email",
        value="decisor@example.com",
        status=EvidenceStatus.CONFIRMED,
        confidence=100,
        method=CaptureMethod.API,
    )
    create_suppression(
        tenant=tenant,
        scope=Suppression.Scope.EMAIL,
        value="decisor@example.com",
        reason="Opt-out",
    )
    decision = canonicalize(tenant=tenant, target=person.entity, field_path="person.email")
    assert decision.selected_observation is None
    assert decision.decision_status == EvidenceStatus.ABSENT
    assert observation.pk is not None


@override_settings(DATA_HASH_KEY="test-hmac", DATA_HASH_KEY_VERSION="v1")
def test_retencao_marca_contato_sem_apagar_auditoria() -> None:
    tenant = get_internal_tenant()
    identity = create_company(
        tenant=tenant,
        cnpj="04.252.011/0001-10",
        legal_name="Empresa Exemplo S.A.",
    )
    now = timezone.now()
    contact = create_contact_point(
        tenant=tenant,
        owner=identity.company.entity,
        kind=ContactPoint.Kind.PHONE,
        value="1134567890",
    )
    ContactPoint.objects.filter(pk=contact.pk).update(
        stale_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=1),
    )
    policy = RetentionPolicy.objects.create(
        tenant=tenant,
        code="curta",
        name="Curta",
        stale_after_days=1,
        retention_days=2,
    )
    run = apply_retention(tenant=tenant, policy=policy, now=now)
    contact.refresh_from_db()
    assert contact.status == ContactPoint.Status.STALE
    assert run.stale_marked == 1
    assert run.expired_marked == 0

    other = Tenant.objects.create(slug="outside", name="Outside")
    with pytest.raises(ValidationError, match="outro tenant"):
        apply_retention(tenant=other, policy=policy)
