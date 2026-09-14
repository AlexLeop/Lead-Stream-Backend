from __future__ import annotations

from typing import Any

from rest_framework import serializers

from leadstream.billing.models import DataBlock

from .discovery import normalize_discovery_filters
from .models import DiscoveryResult, DiscoverySearch, EnrichmentJob, ProviderPolicy


class ProviderPolicySerializer(serializers.ModelSerializer[ProviderPolicy]):
    consecutive_failures = serializers.IntegerField(
        source="health.consecutive_failures", read_only=True, default=0
    )
    circuit_open_until = serializers.DateTimeField(
        source="health.circuit_open_until", read_only=True, allow_null=True
    )
    configured = serializers.SerializerMethodField()

    class Meta:
        model = ProviderPolicy
        fields = (
            "id",
            "provider",
            "display_name",
            "enabled",
            "configured",
            "priority",
            "timeout_seconds",
            "max_retries",
            "requests_per_minute",
            "estimated_cost_cents",
            "daily_budget_cents",
            "batch_budget_cents",
            "failure_threshold",
            "recovery_seconds",
            "allowed_blocks",
            "config",
            "consecutive_failures",
            "circuit_open_until",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "provider",
            "display_name",
            "configured",
            "created_at",
            "updated_at",
        )

    def get_configured(self, obj: ProviderPolicy) -> bool:
        adapters: dict[str, Any] = self.context.get("adapters", {})
        adapter = adapters.get(obj.provider)
        return bool(adapter and adapter.is_configured())

    def validate_allowed_blocks(self, value: list[str]) -> list[str]:
        allowed = {choice for choice, _ in DataBlock.choices}
        invalid = set(value).difference(allowed)
        if invalid:
            raise serializers.ValidationError(f"Blocos inválidos: {', '.join(sorted(invalid))}.")
        return sorted(set(value))

    def update(self, instance: ProviderPolicy, validated_data: dict[str, Any]) -> ProviderPolicy:
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.full_clean()
        instance.save()
        return instance


class EnrichmentStartSerializer(serializers.Serializer[object]):
    blocks = serializers.ListField(
        child=serializers.ChoiceField(choices=DataBlock.choices),
        required=False,
        allow_empty=False,
    )


class ProviderMetricSerializer(serializers.Serializer[object]):
    provider = serializers.CharField()
    provider_status = serializers.CharField()
    calls = serializers.IntegerField()
    average_latency_ms = serializers.FloatField(allow_null=True)
    confirmed_cost_cents = serializers.IntegerField()


class DiscoveryFiltersSerializer(serializers.Serializer[object]):
    cnaes = serializers.ListField(
        child=serializers.CharField(max_length=16), required=False, allow_empty=False
    )
    ufs = serializers.ListField(
        child=serializers.CharField(min_length=2, max_length=2),
        required=False,
        allow_empty=False,
    )
    municipios = serializers.ListField(
        child=serializers.CharField(max_length=160), required=False, allow_empty=False
    )
    situacoes_cadastrais = serializers.ListField(
        child=serializers.CharField(max_length=80), required=False, allow_empty=False
    )
    portes = serializers.ListField(
        child=serializers.CharField(max_length=80), required=False, allow_empty=False
    )
    naturezas_juridicas = serializers.ListField(
        child=serializers.CharField(max_length=120), required=False, allow_empty=False
    )
    matriz = serializers.BooleanField(required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        return normalize_discovery_filters(attrs)


class DiscoveryCreateSerializer(serializers.Serializer[object]):
    name = serializers.CharField(max_length=160, required=False, allow_blank=True)
    filters = DiscoveryFiltersSerializer()
    max_results = serializers.IntegerField(min_value=1, max_value=100_000, default=10_000)
    query_page_size = serializers.IntegerField(min_value=100, max_value=10_000, default=1_000)


class DiscoverySearchSerializer(serializers.ModelSerializer[DiscoverySearch]):
    class Meta:
        model = DiscoverySearch
        fields = (
            "id",
            "name",
            "filters",
            "status",
            "max_results",
            "query_page_size",
            "checkpoint_offset",
            "total_results",
            "billed_bytes",
            "estimated_cost_cents",
            "attempt_count",
            "last_error_code",
            "last_error_message",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class DiscoveryResultSerializer(serializers.ModelSerializer[DiscoveryResult]):
    class Meta:
        model = DiscoveryResult
        fields = (
            "id",
            "rank",
            "cnpj",
            "legal_name",
            "trade_name",
            "registration_status",
            "primary_cnae",
            "company_size",
            "state",
            "city",
            "created_at",
        )
        read_only_fields = fields


class DiscoveryMaterializeSerializer(serializers.Serializer[object]):
    name = serializers.CharField(max_length=160, required=False, allow_blank=True)
    chunk_size = serializers.IntegerField(min_value=50, max_value=5_000, default=500)
    result_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=False, max_length=100_000
    )


class IndividualEnrichmentRequestSerializer(serializers.Serializer[object]):
    query = serializers.CharField(max_length=32)
    capabilities = serializers.ListField(
        child=serializers.CharField(max_length=64),
        required=False,
        default=list,
        max_length=30,
    )


class EnrichmentJobSerializer(serializers.ModelSerializer[EnrichmentJob]):
    entityType = serializers.CharField(source="entity_type", read_only=True)
    query = serializers.CharField(source="query_label", read_only=True)
    matchedEntityId = serializers.CharField(source="matched_entity_id", read_only=True)
    costCredits = serializers.IntegerField(source="cost_credits", read_only=True)
    errorCode = serializers.CharField(source="last_error_code", read_only=True)
    errorMessage = serializers.CharField(source="last_error_message", read_only=True)
    attemptCount = serializers.IntegerField(source="attempt_count", read_only=True)
    startedAt = serializers.DateTimeField(source="started_at", read_only=True)
    completedAt = serializers.DateTimeField(source="completed_at", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    purgeAfter = serializers.DateTimeField(source="purge_after", read_only=True)
    purgedAt = serializers.DateTimeField(source="purged_at", read_only=True)
    result = serializers.SerializerMethodField()

    class Meta:
        model = EnrichmentJob
        fields = (
            "id",
            "entityType",
            "query",
            "capabilities",
            "status",
            "matchedEntityId",
            "costCredits",
            "errorCode",
            "errorMessage",
            "attemptCount",
            "startedAt",
            "completedAt",
            "createdAt",
            "updatedAt",
            "purgeAfter",
            "purgedAt",
            "result",
        )
        read_only_fields = fields

    def get_result(self, obj: EnrichmentJob) -> dict[str, Any] | None:
        if not self.context.get("include_result"):
            return None
        return obj.result_payload or None
