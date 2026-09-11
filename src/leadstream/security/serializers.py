from __future__ import annotations

from typing import Any

from rest_framework import serializers

from leadstream.security.models import APIKey, SecurityAuditLog, WorkspaceRole


class APIKeyCreateSerializer(serializers.Serializer[dict[str, Any]]):
    name = serializers.CharField(
        max_length=120,
        help_text="Nome identificador da chave (ex: CRM HubSpot Produção)",
    )
    role = serializers.ChoiceField(
        choices=WorkspaceRole.choices,
        default=WorkspaceRole.OPERATOR,
        help_text="Nível de autorização concedido à chave",
    )
    env = serializers.ChoiceField(
        choices=["live", "test"],
        default="live",
        help_text="Ambiente de execução (live gera prefixo ls_live_, test gera ls_test_)",
    )
    scopes = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        default=list,
        help_text="Lista de escopos específicos concedidos à chave",
    )
    expires_at = serializers.DateTimeField(
        required=False,
        allow_null=True,
        default=None,
        help_text="Data de expiração opcional da chave",
    )


class APIKeyReadSerializer(serializers.ModelSerializer[APIKey]):
    class Meta:  # type: ignore[override]
        model = APIKey
        fields = (
            "id",
            "name",
            "prefix",
            "role",
            "scopes",
            "is_active",
            "expires_at",
            "last_used_at",
            "created_at",
        )
        read_only_fields = fields


class APIKeyCreatedResponseSerializer(APIKeyReadSerializer):
    raw_key = serializers.CharField(
        help_text="Chave secreta completa exibida uma única vez. Guarde-a em local seguro."
    )
    notice = serializers.CharField(
        default="Guarde esta chave em local seguro. Ela não poderá ser visualizada novamente.",
        read_only=True,
    )

    class Meta(APIKeyReadSerializer.Meta):
        fields = (
            *APIKeyReadSerializer.Meta.fields,
            "raw_key",
            "notice",
        )
        read_only_fields = fields


class TokenRevokeSerializer(serializers.Serializer[dict[str, Any]]):
    refresh = serializers.CharField(
        required=True,
        help_text="Refresh token a ser revogado/invalidado na blacklist.",
    )


class SecurityAuditLogSerializer(serializers.ModelSerializer[SecurityAuditLog]):
    class Meta:  # type: ignore[override]
        model = SecurityAuditLog
        fields = (
            "id",
            "timestamp",
            "actor_type",
            "actor_id",
            "ip_address",
            "user_agent",
            "action",
            "resource_accessed",
            "status_code",
            "details",
        )
        read_only_fields = fields
