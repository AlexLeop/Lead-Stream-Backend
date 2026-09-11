from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from leadstream.entities.models import Entity
from leadstream.entities.normalization import fingerprint_value
from leadstream.tenancy.models import Tenant

from .models import (
    CanonicalDecision,
    Conflict,
    ConflictParticipant,
    Evidence,
    EvidenceStatus,
    Observation,
    ObservationEvidence,
    SourceRecord,
)


@dataclass(frozen=True)
class CanonicalPolicy:
    version: str = "canonical-v1"


STATE_WEIGHT: dict[str, int] = {
    EvidenceStatus.INFERRED: 10,
    EvidenceStatus.OBSERVED: 20,
    EvidenceStatus.TECHNICALLY_VALIDATED: 30,
    EvidenceStatus.CONFIRMED: 40,
}


def _ensure_same_tenant(tenant: Tenant, *tenant_ids: object) -> None:
    if any(tenant_id != tenant.pk for tenant_id in tenant_ids):
        raise ValidationError("Todas as referências devem pertencer ao mesmo tenant.")


@transaction.atomic
def append_observation(
    *,
    tenant: Tenant,
    target: Entity,
    source_record: SourceRecord,
    field_path: str,
    value: Any,
    status: str,
    confidence: int,
    method: str,
    observed_at: datetime | None = None,
    captured_at: datetime | None = None,
    expires_at: datetime | None = None,
    supersedes: Observation | None = None,
    evidence_items: Iterable[Evidence] = (),
) -> Observation:
    _ensure_same_tenant(tenant, target.tenant_id, source_record.tenant_id)
    if supersedes is not None:
        _ensure_same_tenant(tenant, supersedes.tenant_id)
    evidence_list = list(evidence_items)
    _ensure_same_tenant(tenant, *(item.tenant_id for item in evidence_list))
    now = timezone.now()
    observation = Observation(
        tenant=tenant,
        target=target,
        source_record=source_record,
        field_path=field_path.strip(),
        value=value,
        value_fingerprint=fingerprint_value(value),
        status=status,
        confidence=confidence,
        method=method,
        observed_at=observed_at or now,
        captured_at=captured_at or source_record.captured_at,
        expires_at=expires_at,
        supersedes=supersedes,
    )
    observation.full_clean()
    observation.save(force_insert=True)
    ObservationEvidence.objects.bulk_create(
        [ObservationEvidence(observation=observation, evidence=item) for item in evidence_list]
    )
    return observation


@transaction.atomic
def open_conflict(
    *,
    tenant: Tenant,
    target: Entity,
    field_path: str,
    observations: Iterable[Observation],
    reason: str = "Valores divergentes entre fontes.",
) -> Conflict:
    items = list(observations)
    if len(items) < 2:
        raise ValidationError("Um conflito exige ao menos duas observações.")
    _ensure_same_tenant(tenant, target.tenant_id, *(item.tenant_id for item in items))
    if any(item.target_id != target.pk or item.field_path != field_path for item in items):
        raise ValidationError("Observações do conflito devem tratar a mesma entidade e campo.")
    if len({item.value_fingerprint for item in items}) < 2:
        raise ValidationError("Observações idênticas não formam conflito.")
    conflict, _ = Conflict.objects.get_or_create(
        tenant=tenant,
        target=target,
        field_path=field_path,
        status=Conflict.Status.OPEN,
        defaults={"reason": reason},
    )
    ConflictParticipant.objects.bulk_create(
        [ConflictParticipant(conflict=conflict, observation=item) for item in items],
        ignore_conflicts=True,
    )
    return conflict


def _rank(observation: Observation) -> tuple[int, int, int, float, str]:
    return (
        STATE_WEIGHT[observation.status],
        observation.source_record.source.priority,
        observation.confidence,
        observation.observed_at.timestamp(),
        str(observation.pk),
    )


@transaction.atomic
def canonicalize(
    *,
    tenant: Tenant,
    target: Entity,
    field_path: str,
    policy: CanonicalPolicy | None = None,
    suppression_check: Callable[[Observation], bool] | None = None,
    now: datetime | None = None,
) -> CanonicalDecision:
    _ensure_same_tenant(tenant, target.tenant_id)
    policy = policy or CanonicalPolicy()
    decision_time = now or timezone.now()
    Entity.objects.select_for_update().get(pk=target.pk, tenant=tenant)
    eligible = list(
        Observation.objects.select_related("source_record__source")
        .filter(
            tenant=tenant,
            target=target,
            field_path=field_path,
            status__in=STATE_WEIGHT,
        )
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=decision_time))
    )
    if suppression_check is None:
        from leadstream.governance.services import is_observation_suppressed

        suppression_check = is_observation_suppressed
    eligible = [item for item in eligible if not suppression_check(item)]
    selected = max(eligible, key=_rank) if eligible else None
    current_version = (
        CanonicalDecision.objects.filter(
            tenant=tenant, target=target, field_path=field_path
        ).aggregate(max_version=Max("version"))["max_version"]
        or 0
    )
    status = selected.status if selected is not None else EvidenceStatus.ABSENT
    decision = CanonicalDecision(
        tenant=tenant,
        target=target,
        field_path=field_path,
        version=current_version + 1,
        policy_version=policy.version,
        selected_observation=selected,
        decision_status=status,
        reason=(
            "Observação elegível selecionada pela política determinística."
            if selected
            else "Nenhuma observação elegível; ausência registrada explicitamente."
        ),
        decided_at=decision_time,
    )
    decision.full_clean()
    decision.save(force_insert=True)
    return decision
