# pyrefly: ignore-errors[bad-override]
from __future__ import annotations

from typing import Any

from rest_framework import serializers

from .models import CRMConnection, CRMFieldMapping, CRMOutboxMessage, CRMSyncEvent


class CRMConnectionSerializer(serializers.ModelSerializer[CRMConnection]):
    credentials = serializers.JSONField(write_only=True, required=False, default=dict)
    has_credentials = serializers.SerializerMethodField()

    class Meta:  # pyrefly: ignore[bad-override]
        model = CRMConnection
        fields = (
            "id",
            "name",
            "connector_type",
            "is_active",
            "credentials",
            "has_credentials",
            "settings",
            "last_tested_at",
            "last_status",
            "last_error_message",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "has_credentials",
            "last_tested_at",
            "last_status",
            "last_error_message",
            "created_at",
            "updated_at",
        )

    def get_has_credentials(self, obj: CRMConnection) -> bool:
        return bool(obj.credentials)


class CRMFieldMappingSerializer(serializers.ModelSerializer[CRMFieldMapping]):
    class Meta:  # pyrefly: ignore[bad-override]
        model = CRMFieldMapping
        fields = (
            "id",
            "connection",
            "entity_type",
            "source_field",
            "target_field",
            "transformation",
            "is_required",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class CRMOutboxMessageSerializer(serializers.ModelSerializer[CRMOutboxMessage]):
    class Meta:  # pyrefly: ignore[bad-override]
        model = CRMOutboxMessage
        fields = (
            "id",
            "connection",
            "batch",
            "batch_item",
            "entity_type",
            "idempotency_key",
            "canonical_payload",
            "status",
            "retry_count",
            "max_retries",
            "next_retry_at",
            "last_attempted_at",
            "delivered_at",
            "remote_id",
            "error_code",
            "error_message",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class CRMSyncEventSerializer(serializers.ModelSerializer[CRMSyncEvent]):
    class Meta:  # pyrefly: ignore[bad-override]
        model = CRMSyncEvent
        fields = (
            "id",
            "connection",
            "batch",
            "total_enqueued",
            "total_delivered",
            "total_failed",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class CRMSyncRequestSerializer(serializers.Serializer[object]):
    connection_id = serializers.UUIDField(help_text="ID da conexão de CRM de destino.")
    statuses = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
        help_text=(
            "Lista de status de itens a enviar (ex: ['PROCESSED', 'COMPLETED']). "
            "Se omitido, envia todos não-falhos."
        ),
    )
    lead_level = serializers.ChoiceField(
        choices=["DECISION_MAKER", "COMPANY"],
        default="DECISION_MAKER",
        help_text="Nível do lead: DECISION_MAKER (por decisor) ou COMPANY (por empresa).",
    )


class CRMTestConnectionResponseSerializer(serializers.Serializer[object]):
    success = serializers.BooleanField()
    message = serializers.CharField()
    latency_ms = serializers.FloatField()
    remote_account_info = serializers.DictField(required=False)


class AdminCRMOverviewResponseSerializer(serializers.Serializer[object]):
    outbox_status_summary = serializers.DictField(child=serializers.IntegerField())
    active_connectors_summary = serializers.DictField(child=serializers.IntegerField())
    total_messages = serializers.IntegerField()
    total_delivered = serializers.IntegerField()
    total_failed = serializers.IntegerField()
    global_success_rate_percent = serializers.FloatField()


class CRMOutboxStatusCountsSerializer(serializers.Serializer[dict[str, Any]]):
    pending = serializers.IntegerField(default=0)
    processing = serializers.IntegerField(default=0)
    delivered = serializers.IntegerField(default=0)
    failed = serializers.IntegerField(default=0)
    dead_letter = serializers.IntegerField(default=0)


class CRMOutboxStatusResponseSerializer(serializers.Serializer[dict[str, Any]]):
    tenant_id = serializers.CharField()
    counts = CRMOutboxStatusCountsSerializer()
    oldest_pending_seconds = serializers.IntegerField(allow_null=True)
    is_healthy = serializers.BooleanField()


class CRMOutboxRetryDeadLetterRequestSerializer(serializers.Serializer[dict[str, Any]]):
    message_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
        help_text="Lista opcional de IDs de mensagens em dead-letter a reprocessar.",
    )


class CRMOutboxRetryDeadLetterResponseSerializer(serializers.Serializer[dict[str, Any]]):
    retried_count = serializers.IntegerField()
    message = serializers.CharField()
