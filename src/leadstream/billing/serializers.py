from __future__ import annotations

from typing import Any

from rest_framework import serializers

from .models import (
    CreditReservation,
    CreditTransaction,
    CreditWallet,
    DataBlock,
    PriceBook,
    PriceRule,
)


class PriceRuleSerializer(serializers.ModelSerializer[PriceRule]):
    block_label = serializers.CharField(source="get_block_display", read_only=True)

    class Meta:
        model = PriceRule
        fields = (
            "id",
            "block",
            "block_label",
            "unit_price_cents",
            "minimum_confidence",
            "refresh_window_days",
        )
        read_only_fields = fields


class PriceBookSerializer(serializers.ModelSerializer[PriceBook]):
    rules = PriceRuleSerializer(many=True, read_only=True)
    total_unit_price_cents = serializers.SerializerMethodField()

    class Meta:
        model = PriceBook
        fields = (
            "id",
            "version",
            "name",
            "currency",
            "effective_at",
            "retired_at",
            "total_unit_price_cents",
            "rules",
            "created_at",
        )
        read_only_fields = fields

    def get_total_unit_price_cents(self, obj: PriceBook) -> int:
        return sum(rule.unit_price_cents for rule in obj.rules.all())


class PriceRuleInputSerializer(serializers.Serializer[PriceRule]):
    block = serializers.ChoiceField(choices=DataBlock.choices)
    unit_price_cents = serializers.IntegerField(min_value=0, max_value=1_000_000)
    minimum_confidence = serializers.IntegerField(min_value=0, max_value=100, default=80)
    refresh_window_days = serializers.IntegerField(min_value=1, max_value=3650, default=30)

    def create(self, validated_data: dict[str, Any]) -> PriceRule:
        del validated_data
        raise NotImplementedError

    def update(self, instance: PriceRule, validated_data: dict[str, Any]) -> PriceRule:
        del instance, validated_data
        raise NotImplementedError


class PriceBookInputSerializer(serializers.Serializer[PriceBook]):
    name = serializers.CharField(max_length=160)
    effective_at = serializers.DateTimeField(required=False)
    rules = PriceRuleInputSerializer(many=True)

    def create(self, validated_data: dict[str, Any]) -> PriceBook:
        del validated_data
        raise NotImplementedError

    def update(self, instance: PriceBook, validated_data: dict[str, Any]) -> PriceBook:
        del instance, validated_data
        raise NotImplementedError


class FinancialBlockSerializer(serializers.Serializer[object]):
    block = serializers.CharField()
    block_label = serializers.CharField()
    delivered = serializers.IntegerField()
    calls = serializers.IntegerField()
    revenue_cents = serializers.IntegerField()
    cost_cents = serializers.IntegerField()


class FinancialProviderSerializer(serializers.Serializer[object]):
    provider = serializers.CharField()
    provider_status = serializers.CharField()
    calls = serializers.IntegerField()
    cost_cents = serializers.IntegerField()


class FinancialSummarySerializer(serializers.Serializer[object]):
    batch_id = serializers.UUIDField()
    currency = serializers.CharField()
    cost_cents = serializers.IntegerField()
    revenue_cents = serializers.IntegerField()
    gross_profit_cents = serializers.IntegerField()
    gross_margin_percent = serializers.FloatField()
    billable_deliveries = serializers.IntegerField()
    coverage_percent = serializers.FloatField()
    by_block = FinancialBlockSerializer(many=True)
    by_provider = FinancialProviderSerializer(many=True)


class CreditTransactionSerializer(serializers.ModelSerializer[CreditTransaction]):
    class Meta:
        model = CreditTransaction
        fields = (
            "id",
            "transaction_type",
            "amount",
            "balance_after",
            "reference_id",
            "metadata",
            "created_at",
        )
        read_only_fields = fields


class CreditReservationSerializer(serializers.ModelSerializer[CreditReservation]):
    class Meta:
        model = CreditReservation
        fields = (
            "id",
            "batch",
            "amount",
            "captured_amount",
            "released_amount",
            "status",
            "description",
            "expires_at",
            "created_at",
        )
        read_only_fields = fields


class CreditWalletSerializer(serializers.ModelSerializer[CreditWallet]):
    available_balance = serializers.IntegerField(read_only=True)

    class Meta:
        model = CreditWallet
        fields = (
            "id",
            "balance",
            "reserved_balance",
            "available_balance",
            "is_unlimited",
            "auto_recharge",
            "recharge_threshold",
            "updated_at",
        )
        read_only_fields = fields


class CreditDepositRequestSerializer(serializers.Serializer[object]):
    amount = serializers.IntegerField(min_value=1, max_value=10_000_000)
    reference_id = serializers.CharField(
        max_length=160, required=False, default="", allow_blank=True
    )
    metadata = serializers.JSONField(required=False, default=dict)


class CreditDepositResponseSerializer(serializers.Serializer[object]):
    message = serializers.CharField()
    balance = serializers.IntegerField()
    transaction = CreditTransactionSerializer()

