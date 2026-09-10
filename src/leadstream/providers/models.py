from __future__ import annotations

import uuid
from typing import ClassVar

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from leadstream.tenancy.models import TenantOwnedModel


class ProviderPolicy(TenantOwnedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.SlugField(max_length=80)
    display_name = models.CharField(max_length=160)
    enabled = models.BooleanField(default=False)
    priority = models.PositiveSmallIntegerField(default=100)
    timeout_seconds = models.PositiveSmallIntegerField(default=30)
    max_retries = models.PositiveSmallIntegerField(default=3)
    requests_per_minute = models.PositiveIntegerField(default=60)
    estimated_cost_cents = models.PositiveIntegerField(default=0)
    daily_budget_cents = models.PositiveIntegerField(default=0)
    batch_budget_cents = models.PositiveIntegerField(default=0)
    failure_threshold = models.PositiveSmallIntegerField(default=5)
    recovery_seconds = models.PositiveIntegerField(default=300)
    allowed_blocks = models.JSONField(default=list)
    config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leadstream_provider_policy"
        ordering: ClassVar[list[str]] = ["priority", "provider"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("tenant", "provider"), name="provider_policy_tenant_uniq"
            ),
            models.CheckConstraint(
                condition=Q(timeout_seconds__gte=1) & Q(timeout_seconds__lte=600),
                name="provider_timeout_range",
            ),
            models.CheckConstraint(
                condition=Q(failure_threshold__gte=1), name="provider_failure_threshold_positive"
            ),
        ]

    def clean(self) -> None:
        if not isinstance(self.config, dict) or any(
            "token" in str(key).casefold()
            or "secret" in str(key).casefold()
            or "password" in str(key).casefold()
            or "credential" in str(key).casefold()
            for key in self.config
        ):
            raise ValidationError({"config": "Configuração não pode armazenar credenciais."})


class ProviderHealth(TenantOwnedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    policy = models.OneToOneField(
        ProviderPolicy, on_delete=models.PROTECT, related_name="health"
    )
    consecutive_failures = models.PositiveIntegerField(default=0)
    circuit_open_until = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_failure_at = models.DateTimeField(null=True, blank=True)
    last_error_code = models.CharField(max_length=64, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leadstream_provider_health"
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("tenant", "circuit_open_until"), name="provider_circuit_idx")
        ]

    def clean(self) -> None:
        if self.policy.tenant_id != self.tenant_id:
            raise ValidationError({"policy": "Saúde e política devem pertencer ao mesmo tenant."})
