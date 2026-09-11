from __future__ import annotations

import uuid
from typing import ClassVar

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from leadstream.entities.models import Entity
from leadstream.tenancy.models import TenantOwnedModel


class Batch(TenantOwnedModel):
    class SourceType(models.TextChoices):
        CSV = "CSV", "Arquivo CSV"
        DISCOVERY = "DISCOVERY", "Seleção de descoberta"

    class Status(models.TextChoices):
        RECEIVED = "RECEIVED", "Recebido"
        INGESTING = "INGESTING", "Importando"
        QUEUED = "QUEUED", "Na fila"
        RUNNING = "RUNNING", "Em execução"
        PAUSED = "PAUSED", "Pausado"
        CANCEL_REQUESTED = "CANCEL_REQUESTED", "Cancelamento solicitado"
        CANCELLED = "CANCELLED", "Cancelado"
        COMPLETED = "COMPLETED", "Concluído"
        PARTIAL = "PARTIAL", "Concluído parcialmente"
        FAILED = "FAILED", "Falhou"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    source_type = models.CharField(max_length=16, choices=SourceType.choices)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.RECEIVED)
    idempotency_key = models.CharField(max_length=128, blank=True)
    current_stage = models.CharField(max_length=32, default="INGESTION")
    input_backend = models.CharField(max_length=32, default="LOCAL")
    input_key = models.CharField(max_length=512, blank=True)
    input_original_name = models.CharField(max_length=255, blank=True)
    input_content_type = models.CharField(max_length=128, blank=True)
    input_size_bytes = models.PositiveBigIntegerField(default=0)
    input_sha256 = models.CharField(max_length=64, blank=True)
    chunk_size = models.PositiveIntegerField(default=500)
    total_rows = models.PositiveIntegerField(default=0)
    processed_rows = models.PositiveIntegerField(default=0)
    succeeded_rows = models.PositiveIntegerField(default=0)
    absent_rows = models.PositiveIntegerField(default=0)
    failed_rows = models.PositiveIntegerField(default=0)
    duplicate_rows = models.PositiveIntegerField(default=0)
    corrected_rows = models.PositiveIntegerField(default=0)
    invalid_rows = models.PositiveIntegerField(default=0)
    cost_cents = models.PositiveBigIntegerField(default=0)
    revenue_cents = models.PositiveBigIntegerField(default=0)
    last_error_code = models.CharField(max_length=64, blank=True)
    last_error_message = models.CharField(max_length=500, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leadstream_batch"
        ordering: ClassVar[list[str]] = ["-created_at"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("tenant", "idempotency_key"),
                condition=~Q(idempotency_key=""),
                name="batch_tenant_idempotency_uniq",
            ),
            models.CheckConstraint(
                condition=Q(chunk_size__gte=50) & Q(chunk_size__lte=5000),
                name="batch_chunk_size_range",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("tenant", "status", "created_at"), name="batch_status_time_idx")
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.status})"


class BatchItem(TenantOwnedModel):
    class HygieneState(models.TextChoices):
        UNCHANGED = "UNCHANGED", "Inalterado"
        CORRECTED = "CORRECTED", "Corrigido"
        INVALID = "INVALID", "Inválido"
        DUPLICATE = "DUPLICATE", "Duplicado"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        PROCESSING = "PROCESSING", "Processando"
        SUCCEEDED = "SUCCEEDED", "Concluído"
        ABSENT = "ABSENT", "Sem resultado"
        FAILED = "FAILED", "Falhou"

    class EnrichmentStatus(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        SUCCEEDED = "SUCCEEDED", "Concluído"
        PARTIAL = "PARTIAL", "Parcial"
        FAILED = "FAILED", "Falhou"
        SKIPPED = "SKIPPED", "Ignorado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(Batch, on_delete=models.PROTECT, related_name="items")
    row_number = models.PositiveIntegerField()
    original_data = models.JSONField(default=dict)
    normalized_data = models.JSONField(default=dict)
    hygiene_state = models.CharField(max_length=16, choices=HygieneState.choices)
    applied_rules = models.JSONField(default=list)
    issues = models.JSONField(default=list)
    fingerprint = models.CharField(max_length=64, blank=True)
    duplicate_of = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="duplicates"
    )
    entity = models.ForeignKey(
        Entity, on_delete=models.PROTECT, null=True, blank=True, related_name="batch_items"
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    error_code = models.CharField(max_length=64, blank=True)
    error_message = models.CharField(max_length=500, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    enrichment_status = models.CharField(
        max_length=16, choices=EnrichmentStatus.choices, default=EnrichmentStatus.PENDING
    )
    delivered_blocks = models.JSONField(default=list)
    missing_blocks = models.JSONField(default=list)
    enrichment_errors = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leadstream_batch_item"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=("batch", "row_number"), name="batch_item_row_uniq")
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("tenant", "batch", "status"), name="batch_item_status_idx"),
            models.Index(fields=("tenant", "fingerprint"), name="batch_item_fingerprint_idx"),
        ]

    def clean(self) -> None:
        errors: dict[str, str] = {}
        if self.batch.tenant_id != self.tenant_id:
            errors["batch"] = "Item e lote devem pertencer ao mesmo tenant."
        if self.entity_id and self.entity and self.entity.tenant_id != self.tenant_id:
            errors["entity"] = "Entidade e item devem pertencer ao mesmo tenant."
        if (
            self.duplicate_of_id
            and self.duplicate_of
            and self.duplicate_of.batch_id != self.batch_id
        ):
            errors["duplicate_of"] = "Duplicidade deve apontar para o mesmo lote."
        if errors:
            raise ValidationError(errors)


class BatchChunk(TenantOwnedModel):
    class Stage(models.TextChoices):
        HYGIENE = "HYGIENE", "Higienização"
        ENRICHMENT = "ENRICHMENT", "Enriquecimento"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        LEASED = "LEASED", "Reservado"
        RUNNING = "RUNNING", "Em execução"
        PAUSED = "PAUSED", "Pausado"
        COMPLETED = "COMPLETED", "Concluído"
        FAILED = "FAILED", "Falhou"
        CANCELLED = "CANCELLED", "Cancelado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(Batch, on_delete=models.PROTECT, related_name="chunks")
    stage = models.CharField(max_length=16, choices=Stage.choices, default=Stage.HYGIENE)
    requested_blocks = models.JSONField(default=list)
    sequence = models.PositiveIntegerField()
    start_row = models.PositiveIntegerField()
    end_row = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    checkpoint_row = models.PositiveIntegerField(default=0)
    lease_owner = models.CharField(max_length=255, blank=True)
    leased_until = models.DateTimeField(null=True, blank=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    attempt_count = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=5)
    last_error_code = models.CharField(max_length=64, blank=True)
    last_error_message = models.CharField(max_length=500, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leadstream_batch_chunk"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("batch", "stage", "sequence"), name="batch_chunk_stage_seq_uniq"
            ),
            models.CheckConstraint(
                condition=Q(end_row__gte=models.F("start_row")), name="batch_chunk_rows_order"
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("tenant", "status", "leased_until"), name="chunk_lease_idx"),
            models.Index(fields=("status", "dispatched_at"), name="chunk_dispatch_idx"),
        ]

    def clean(self) -> None:
        if self.batch.tenant_id != self.tenant_id:
            raise ValidationError({"batch": "Chunk e lote devem pertencer ao mesmo tenant."})


class ProcessingAttempt(TenantOwnedModel):
    class Status(models.TextChoices):
        STARTED = "STARTED", "Iniciada"
        SUCCEEDED = "SUCCEEDED", "Concluída"
        RETRYABLE_FAILURE = "RETRYABLE_FAILURE", "Falha recuperável"
        PERMANENT_FAILURE = "PERMANENT_FAILURE", "Falha permanente"
        ABANDONED = "ABANDONED", "Abandonada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chunk = models.ForeignKey(BatchChunk, on_delete=models.PROTECT, related_name="attempts")
    attempt_number = models.PositiveIntegerField()
    worker_id = models.CharField(max_length=255)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.STARTED)
    error_code = models.CharField(max_length=64, blank=True)
    error_message = models.CharField(max_length=500, blank=True)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "leadstream_processing_attempt"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("chunk", "attempt_number"), name="chunk_attempt_number_uniq"
            )
        ]

    def clean(self) -> None:
        if self.chunk.tenant_id != self.tenant_id:
            raise ValidationError({"chunk": "Tentativa e chunk devem pertencer ao mesmo tenant."})


class BatchExport(TenantOwnedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        PROCESSING = "PROCESSING", "Processando"
        COMPLETED = "COMPLETED", "Concluído"
        FAILED = "FAILED", "Falhou"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="exports")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING)

    file_backend = models.CharField(max_length=32, default="LOCAL")
    file_key = models.CharField(max_length=512, blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=128, default="text/csv; charset=utf-8")
    size_bytes = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)

    selected_columns = models.JSONField(default=list, blank=True)
    selected_statuses = models.JSONField(default=list, blank=True)
    lead_level = models.CharField(max_length=32, default="DECISION_MAKER")

    total_rows = models.PositiveIntegerField(default=0)
    total_companies = models.PositiveIntegerField(default=0)
    total_decision_makers = models.PositiveIntegerField(default=0)
    total_direct_contacts = models.PositiveIntegerField(default=0)

    manifest_data = models.JSONField(default=dict, blank=True)
    export_hash = models.CharField(max_length=64, blank=True)

    last_error_code = models.CharField(max_length=64, blank=True)
    last_error_message = models.CharField(max_length=500, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leadstream_batch_export"
        ordering: ClassVar[list[str]] = ["-created_at"]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("tenant", "batch", "status"), name="batch_export_status_idx"),
            models.Index(fields=("tenant", "export_hash"), name="batch_export_hash_idx"),
        ]

    def clean(self) -> None:
        if self.batch.tenant_id != self.tenant_id:
            raise ValidationError({"batch": "Exportação e lote devem pertencer ao mesmo tenant."})
