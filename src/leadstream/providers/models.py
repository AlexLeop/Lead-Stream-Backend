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
    policy = models.OneToOneField(ProviderPolicy, on_delete=models.PROTECT, related_name="health")
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


class DiscoverySearch(TenantOwnedModel):
    class Status(models.TextChoices):
        QUEUED = "QUEUED", "Na fila"
        RUNNING = "RUNNING", "Em execução"
        COMPLETED = "COMPLETED", "Concluída"
        FAILED = "FAILED", "Falhou"
        CANCELLED = "CANCELLED", "Cancelada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    idempotency_key = models.CharField(max_length=128)
    filters = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    max_results = models.PositiveIntegerField(default=10_000)
    query_page_size = models.PositiveIntegerField(default=1_000)
    checkpoint_offset = models.PositiveIntegerField(default=0)
    total_results = models.PositiveIntegerField(default=0)
    billed_bytes = models.PositiveBigIntegerField(default=0)
    estimated_cost_cents = models.PositiveIntegerField(default=0)
    lease_owner = models.CharField(max_length=255, blank=True)
    leased_until = models.DateTimeField(null=True, blank=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=5)
    last_error_code = models.CharField(max_length=64, blank=True)
    last_error_message = models.CharField(max_length=500, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leadstream_discovery_search"
        ordering: ClassVar[list[str]] = ["-created_at"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("tenant", "idempotency_key"), name="discovery_tenant_idempotency_uniq"
            ),
            models.CheckConstraint(
                condition=Q(max_results__gte=1) & Q(max_results__lte=100_000),
                name="discovery_max_results_range",
            ),
            models.CheckConstraint(
                condition=Q(query_page_size__gte=100) & Q(query_page_size__lte=10_000),
                name="discovery_page_size_range",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("tenant", "status", "created_at"), name="discovery_status_idx"),
            models.Index(fields=("status", "leased_until"), name="discovery_lease_idx"),
        ]


class DiscoveryResult(TenantOwnedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    search = models.ForeignKey(DiscoverySearch, on_delete=models.PROTECT, related_name="results")
    rank = models.PositiveIntegerField()
    cnpj = models.CharField(max_length=14)
    legal_name = models.CharField(max_length=255, blank=True)
    trade_name = models.CharField(max_length=255, blank=True)
    registration_status = models.CharField(max_length=64, blank=True)
    primary_cnae = models.CharField(max_length=16, blank=True)
    company_size = models.CharField(max_length=80, blank=True)
    state = models.CharField(max_length=2, blank=True)
    city = models.CharField(max_length=160, blank=True)
    source_data = models.JSONField(default=dict)
    source_fingerprint = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "leadstream_discovery_result"
        ordering: ClassVar[list[str]] = ["rank", "id"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=("search", "cnpj"), name="discovery_result_cnpj_uniq"),
            models.UniqueConstraint(fields=("search", "rank"), name="discovery_result_rank_uniq"),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("tenant", "search", "rank"), name="discovery_result_rank_idx"),
            models.Index(fields=("tenant", "cnpj"), name="discovery_result_cnpj_idx"),
        ]

    def clean(self) -> None:
        if self.search.tenant_id != self.tenant_id:
            raise ValidationError({"search": "Resultado e busca devem pertencer ao mesmo tenant."})
