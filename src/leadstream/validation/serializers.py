from __future__ import annotations

from rest_framework import serializers


class EmailValidationRequestSerializer(serializers.Serializer[object]):
    email = serializers.CharField(required=False, allow_blank=True, default="")
    emails = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    deep_smtp = serializers.BooleanField(default=True)

    def validate(self, attrs: dict) -> dict:
        if not attrs.get("email") and not attrs.get("emails"):
            raise serializers.ValidationError("Informe 'email' ou uma lista em 'emails'.")
        return attrs


class EmailValidationResultSerializer(serializers.Serializer[object]):
    endereco = serializers.CharField()
    status = serializers.CharField()
    is_deliverable = serializers.BooleanField()
    is_catch_all = serializers.BooleanField()
    is_disposable = serializers.BooleanField()
    mx_server = serializers.CharField(allow_null=True)
    score_confiabilidade = serializers.FloatField()
    details = serializers.CharField()
