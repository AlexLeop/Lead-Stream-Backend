from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from leadstream.entities.models import ContactPoint, Entity
from leadstream.entities.normalization import (
    normalize_domain,
    normalize_email,
    normalize_phone_br,
)
from leadstream.evidence.models import Observation, RetentionPolicy
from leadstream.tenancy.models import Tenant

from .models import RetentionRun, Suppression


@dataclass(frozen=True)
class HashKey:
    version: str
    secret: str


def _hash_keys() -> tuple[HashKey, ...]:
    current = getattr(settings, "DATA_HASH_KEY", "")
    version = getattr(settings, "DATA_HASH_KEY_VERSION", "v1")
    if not current:
        raise ImproperlyConfigured("DATA_HASH_KEY é obrigatória para operações de supressão.")
    keys = [HashKey(version=version, secret=current)]
    for item in getattr(settings, "DATA_HASH_PREVIOUS_KEYS", []):
        previous_version, separator, secret = item.partition(":")
        if separator and previous_version and secret:
            keys.append(HashKey(version=previous_version, secret=secret))
    return tuple(keys)


def normalize_suppression_value(scope: str, value: str) -> str:
    if scope == Suppression.Scope.EMAIL:
        return normalize_email(value)
    if scope == Suppression.Scope.PHONE:
        return normalize_phone_br(value)
    if scope == Suppression.Scope.DOMAIN:
        return normalize_domain(value)
    if scope == Suppression.Scope.PERSON:
        candidate = value.strip().casefold()
        if not candidate:
            raise ValidationError("Identificador de pessoa é obrigatório.")
        return candidate
    raise ValidationError("Escopo de supressão inválido.")


def _digest(*, tenant: Tenant, scope: str, normalized_value: str, key: HashKey) -> str:
    material = f"{tenant.pk}:{scope}:{normalized_value}".encode()
    return hmac.new(key.secret.encode(), material, hashlib.sha256).hexdigest()


def _active_query(now: datetime) -> Q:
    return Q(effective_at__lte=now) & (Q(expires_at__isnull=True) | Q(expires_at__gt=now))


@transaction.atomic
def create_suppression(
    *,
    tenant: Tenant,
    scope: str,
    value: str,
    reason: str,
    effective_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> Suppression:
    normalized = normalize_suppression_value(scope, value)
    key = _hash_keys()[0]
    effective = effective_at or timezone.now()
    suppression, _ = Suppression.objects.get_or_create(
        tenant=tenant,
        scope=scope,
        value_digest=_digest(
            tenant=tenant,
            scope=scope,
            normalized_value=normalized,
            key=key,
        ),
        key_version=key.version,
        defaults={"reason": reason, "effective_at": effective, "expires_at": expires_at},
    )
    if scope in {Suppression.Scope.EMAIL, Suppression.Scope.PHONE}:
        ContactPoint.objects.filter(
            tenant=tenant,
            normalized_value=normalized,
        ).update(status=ContactPoint.Status.SUPPRESSED)
    elif scope == Suppression.Scope.DOMAIN:
        ContactPoint.objects.filter(
            tenant=tenant,
            kind=ContactPoint.Kind.EMAIL,
            normalized_value__iendswith=f"@{normalized}",
        ).update(status=ContactPoint.Status.SUPPRESSED)
    elif scope == Suppression.Scope.PERSON:
        try:
            owner_id = UUID(normalized)
        except ValueError:
            owner_id = None
        if owner_id is not None:
            ContactPoint.objects.filter(
                tenant=tenant,
                owner_id=owner_id,
            ).update(status=ContactPoint.Status.SUPPRESSED)
    return suppression


def is_suppressed(*, tenant: Tenant, scope: str, value: str, now: datetime | None = None) -> bool:
    normalized = normalize_suppression_value(scope, value)
    check_time = now or timezone.now()
    pairs = [
        (
            key.version,
            _digest(tenant=tenant, scope=scope, normalized_value=normalized, key=key),
        )
        for key in _hash_keys()
    ]
    query = Q()
    for version, digest in pairs:
        query |= Q(key_version=version, value_digest=digest)
    return (
        Suppression.objects.filter(tenant=tenant, scope=scope)
        .filter(query)
        .filter(_active_query(check_time))
        .exists()
    )


def is_observation_suppressed(observation: Observation) -> bool:
    tenant = observation.tenant
    if observation.target.kind == Entity.Kind.PERSON and is_suppressed(
        tenant=tenant,
        scope=Suppression.Scope.PERSON,
        value=str(observation.target_id),
    ):
        return True
    if not isinstance(observation.value, str):
        return False
    field = observation.field_path.casefold()
    if "email" in field:
        email = normalize_email(observation.value)
        domain = email.rsplit("@", 1)[1]
        email_suppressed = is_suppressed(tenant=tenant, scope=Suppression.Scope.EMAIL, value=email)
        domain_suppressed = is_suppressed(
            tenant=tenant, scope=Suppression.Scope.DOMAIN, value=domain
        )
        return email_suppressed or domain_suppressed
    if "phone" in field or "telefone" in field or "whatsapp" in field:
        return is_suppressed(tenant=tenant, scope=Suppression.Scope.PHONE, value=observation.value)
    return False


@transaction.atomic
def apply_retention(
    *, tenant: Tenant, policy: RetentionPolicy, now: datetime | None = None
) -> RetentionRun:
    if policy.tenant_id != tenant.pk:
        raise ValidationError("Política de retenção pertence a outro tenant.")
    check_time = now or timezone.now()
    run = RetentionRun.objects.create(
        tenant=tenant,
        policy=policy,
        status=RetentionRun.Status.RUNNING,
        started_at=check_time,
    )
    expired = (
        ContactPoint.objects.filter(
            tenant=tenant,
            expires_at__isnull=False,
            expires_at__lte=check_time,
        )
        .exclude(status=ContactPoint.Status.SUPPRESSED)
        .update(status=ContactPoint.Status.EXPIRED)
    )
    stale = (
        ContactPoint.objects.filter(
            tenant=tenant,
            stale_at__isnull=False,
            stale_at__lte=check_time,
        )
        .exclude(status__in=(ContactPoint.Status.SUPPRESSED, ContactPoint.Status.EXPIRED))
        .update(status=ContactPoint.Status.STALE)
    )
    run.status = RetentionRun.Status.COMPLETED
    run.expired_marked = expired
    run.stale_marked = stale
    run.completed_at = timezone.now()
    run.save(update_fields=("status", "expired_marked", "stale_marked", "completed_at"))
    return run
