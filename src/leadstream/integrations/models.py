from __future__ import annotations

import uuid
from typing import ClassVar

from django.db import models
from django.utils import timezone

from leadstream.tenancy.models import TenantOwnedModel


class CRMConnectorType(models.TextChoices):
    HUBSPOT = "HUBSPOT", "HubSpot"
    PIPEDRIVE = "PIPEDRIVE", "Pipedrive"
    RD_STATION = "RD_STATION", "RD Station CRM"
    SALESFORCE = "SALESFORCE", "Salesforce"
    PLOOMES = "PLOOMES", "Ploomes"
    ZOHO = "ZOHO", "Zoho CRM"
    AGENDOR = "AGENDOR", "Agendor"
    KOMMO = "KOMMO", "Kommo (amoCRM)"
    WEBHOOK_CUSTOM = "WEBHOOK_CUSTOM", "Webhook Universal (HMAC)"
    WEBHOOK_N8N = "WEBHOOK_N8N", "Webhook n8n"
    WEBHOOK_ZAPIER = "WEBHOOK_ZAPIER", "Webhook Zapier"
    WEBHOOK_MAKE = "WEBHOOK_MAKE", "Webhook Make"


class CRMConnectionStatus(models.TextChoices):
    UNTESTED = "UNTESTED", "Não testado"
    HEALTHY = "HEALTHY", "Operacional"
    DEGRADED = "DEGRADED", "Degradado"
    FAILED = "FAILED", "Falha de autenticação/conexão"


class CRMConnection(TenantOwnedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    connector_type = models.CharField(max_length=32, choices=CRMConnectorType.choices)
    is_active = models.BooleanField(default=True)
    credentials = models.JSONField(default=dict, blank=True)
    settings = models.JSONField(default=dict, blank=True)
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_status = models.CharField(
        max_length=16,
        choices=CRMConnectionStatus.choices,
        default=CRMConnectionStatus.UNTESTED,
    )
    last_error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leadstream_crm_connection"
        ordering: ClassVar[list[str]] = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_connector_type_display()})"


class CRMFieldEntityType(models.TextChoices):
    COMPANY = "COMPANY", "Empresa"
    CONTACT = "CONTACT", "Contato / Decisor"
    DEAL = "DEAL", "Oportunidade / Negócio"


class CRMFieldTransformation(models.TextChoices):
    RAW = "RAW", "Sem transformação (direto)"
    LOWER = "LOWER", "Minúsculo"
    UPPER = "UPPER", "Maiúsculo"
    DIGITS_ONLY = "DIGITS_ONLY", "Apenas dígitos (números)"
    FIRST_NAME = "FIRST_NAME", "Primeiro nome"
    LAST_NAME = "LAST_NAME", "Sobrenome"


class CRMFieldMapping(TenantOwnedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connection = models.ForeignKey(
        CRMConnection,
        on_delete=models.CASCADE,
        related_name="field_mappings",
    )
    entity_type = models.CharField(
        max_length=16,
        choices=CRMFieldEntityType.choices,
        default=CRMFieldEntityType.COMPANY,
    )
    source_field = models.CharField(max_length=100)
    target_field = models.CharField(max_length=100)
    transformation = models.CharField(
        max_length=16,
        choices=CRMFieldTransformation.choices,
        default=CRMFieldTransformation.RAW,
    )
    is_required = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leadstream_crm_field_mapping"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["connection", "entity_type", "source_field"],
                name="unique_crm_field_mapping_per_connection_source",
            )
        ]

    def __str__(self) -> str:
        return f"{self.source_field} -> {self.target_field} ({self.entity_type})"


class OutboxStatus(models.TextChoices):
    PENDING = "PENDING", "Pendente"
    PROCESSING = "PROCESSING", "Em processamento"
    DELIVERED = "DELIVERED", "Entregue"
    FAILED = "FAILED", "Falha temporária (aguardando retry)"
    DEAD_LETTER = "DEAD_LETTER", "Falha definitiva (Dead Letter)"


class CRMOutboxMessage(TenantOwnedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connection = models.ForeignKey(
        CRMConnection,
        on_delete=models.CASCADE,
        related_name="outbox_messages",
    )
    batch = models.ForeignKey(
        "batches.Batch",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="crm_outbox_messages",
    )
    batch_item = models.ForeignKey(
        "batches.BatchItem",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="crm_outbox_messages",
    )
    entity_type = models.CharField(max_length=16, choices=CRMFieldEntityType.choices)
    idempotency_key = models.CharField(max_length=255, db_index=True)
    canonical_payload = models.JSONField(default=dict)
    status = models.CharField(
        max_length=16,
        choices=OutboxStatus.choices,
        default=OutboxStatus.PENDING,
        db_index=True,
    )
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=5)
    next_retry_at = models.DateTimeField(default=timezone.now, db_index=True)
    last_attempted_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    remote_id = models.CharField(max_length=255, blank=True)
    error_code = models.CharField(max_length=64, blank=True)
    error_message = models.TextField(blank=True)
    execution_log = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leadstream_crm_outbox_message"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["connection", "idempotency_key"],
                name="unique_crm_outbox_per_connection_key",
            )
        ]
        ordering: ClassVar[list[str]] = ["created_at"]

    def __str__(self) -> str:
        return f"Outbox {self.idempotency_key} ({self.status})"


class CRMSyncEvent(TenantOwnedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connection = models.ForeignKey(
        CRMConnection,
        on_delete=models.CASCADE,
        related_name="sync_events",
    )
    batch = models.ForeignKey(
        "batches.Batch",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="crm_sync_events",
    )
    total_enqueued = models.PositiveIntegerField(default=0)
    total_delivered = models.PositiveIntegerField(default=0)
    total_failed = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=16, default="PROCESSING")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leadstream_crm_sync_event"
        ordering: ClassVar[list[str]] = ["-created_at"]
