from __future__ import annotations

from typing import Any

from rest_framework import serializers

from leadstream.billing.models import DataBlock

from .models import ProviderPolicy


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
            "id", "provider", "display_name", "enabled", "configured", "priority",
            "timeout_seconds", "max_retries", "requests_per_minute", "estimated_cost_cents",
            "daily_budget_cents", "batch_budget_cents", "failure_threshold", "recovery_seconds",
            "allowed_blocks", "config", "consecutive_failures", "circuit_open_until",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "provider", "display_name", "configured", "created_at", "updated_at",
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
