# pyrefly: ignore-errors[bad-override]
from __future__ import annotations

from typing import Any

from rest_framework import serializers

from .models import Batch, BatchChunk, BatchExport, BatchItem, ProcessingAttempt
from .services import batch_eta_seconds


class BatchUploadSerializer(serializers.Serializer[Batch]):
    name = serializers.CharField(max_length=160, required=False, allow_blank=True)
    arquivo = serializers.FileField(write_only=True)
    chunk_size = serializers.IntegerField(min_value=50, max_value=5000, default=500)

    def create(self, validated_data: dict[str, Any]) -> Batch:
        del validated_data
        raise NotImplementedError

    def update(self, instance: Batch, validated_data: dict[str, Any]) -> Batch:
        del instance, validated_data
        raise NotImplementedError


class BatchSerializer(serializers.ModelSerializer[Batch]):
    progress_percent = serializers.SerializerMethodField()
    eta_seconds = serializers.SerializerMethodField()
    gross_profit_cents = serializers.SerializerMethodField()

    class Meta:  # pyrefly: ignore[bad-override]
        model = Batch
        fields = (
            "id",
            "name",
            "source_type",
            "status",
            "current_stage",
            "input_original_name",
            "input_size_bytes",
            "input_sha256",
            "chunk_size",
            "total_rows",
            "processed_rows",
            "succeeded_rows",
            "absent_rows",
            "failed_rows",
            "duplicate_rows",
            "corrected_rows",
            "invalid_rows",
            "progress_percent",
            "eta_seconds",
            "cost_cents",
            "revenue_cents",
            "gross_profit_cents",
            "last_error_code",
            "last_error_message",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_progress_percent(self, obj: Batch) -> float:
        if obj.total_rows == 0:
            return 0.0
        return round((obj.processed_rows / obj.total_rows) * 100, 2)

    def get_eta_seconds(self, obj: Batch) -> int | None:
        return batch_eta_seconds(obj)

    def get_gross_profit_cents(self, obj: Batch) -> int:
        return obj.revenue_cents - obj.cost_cents


class BatchItemSerializer(serializers.ModelSerializer[BatchItem]):
    class Meta:  # pyrefly: ignore[bad-override]
        model = BatchItem
        fields = (
            "id",
            "batch",
            "row_number",
            "original_data",
            "normalized_data",
            "hygiene_state",
            "applied_rules",
            "issues",
            "fingerprint",
            "duplicate_of",
            "entity",
            "status",
            "error_code",
            "error_message",
            "processed_at",
            "created_at",
            "enrichment_status",
            "delivered_blocks",
            "missing_blocks",
            "enrichment_errors",
        )
        read_only_fields = fields


class ProcessingAttemptSerializer(serializers.ModelSerializer[ProcessingAttempt]):
    class Meta:  # pyrefly: ignore[bad-override]
        model = ProcessingAttempt
        fields = (
            "id",
            "attempt_number",
            "worker_id",
            "status",
            "error_code",
            "error_message",
            "started_at",
            "finished_at",
        )
        read_only_fields = fields


class BatchChunkSerializer(serializers.ModelSerializer[BatchChunk]):
    attempts = ProcessingAttemptSerializer(many=True, read_only=True)

    class Meta:  # pyrefly: ignore[bad-override]
        model = BatchChunk
        fields = (
            "id",
            "batch",
            "stage",
            "requested_blocks",
            "sequence",
            "start_row",
            "end_row",
            "status",
            "checkpoint_row",
            "attempt_count",
            "max_attempts",
            "last_error_code",
            "last_error_message",
            "dispatched_at",
            "started_at",
            "completed_at",
            "attempts",
        )
        read_only_fields = fields


class BatchExportRequestSerializer(serializers.Serializer[object]):
    columns = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
        help_text="Colunas personalizadas. Se omitido, exporta todas as colunas padrão.",
    )
    statuses = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
        help_text="Status dos itens a incluir. Se omitido, exporta todos os registros.",
    )
    lead_level = serializers.ChoiceField(
        choices=["DECISION_MAKER", "COMPANY"],
        default="DECISION_MAKER",
        help_text="Nível de agregação: DECISION_MAKER (por decisor) ou COMPANY (por empresa).",
    )


class BatchExportSerializer(serializers.ModelSerializer[BatchExport]):
    download_url = serializers.SerializerMethodField()

    class Meta:  # pyrefly: ignore[bad-override]
        model = BatchExport
        fields = (
            "id",
            "batch",
            "status",
            "file_backend",
            "file_key",
            "file_name",
            "content_type",
            "size_bytes",
            "sha256",
            "selected_columns",
            "selected_statuses",
            "lead_level",
            "total_rows",
            "total_companies",
            "total_decision_makers",
            "total_direct_contacts",
            "manifest_data",
            "last_error_code",
            "last_error_message",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
            "download_url",
        )
        read_only_fields = fields

    def get_download_url(self, obj: BatchExport) -> str | None:
        if obj.status == BatchExport.Status.COMPLETED:
            return f"/api/v1/exportacoes/{obj.id}/download/"
        return None
