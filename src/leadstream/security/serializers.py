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


class UserProfileSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.CharField()
    username = serializers.CharField()
    email = serializers.EmailField(allow_blank=True, allow_null=True)
    first_name = serializers.CharField(allow_blank=True)
    last_name = serializers.CharField(allow_blank=True)
    is_superuser = serializers.BooleanField()
    is_staff = serializers.BooleanField()


class WorkspaceSummarySerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    slug = serializers.CharField()
    role = serializers.CharField()
    is_active = serializers.BooleanField()
    is_current = serializers.BooleanField(default=False)


class ActiveWorkspaceDetailSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    slug = serializers.CharField()
    role = serializers.CharField()
    is_owner = serializers.BooleanField(default=False)
    stats = serializers.DictField(required=False, default=dict)


class AuthMeResponseSerializer(serializers.Serializer[dict[str, Any]]):
    user = UserProfileSerializer()
    auth_type = serializers.CharField()
    active_workspace = ActiveWorkspaceDetailSerializer()
    workspaces = serializers.ListField(child=WorkspaceSummarySerializer())
    permissions = serializers.ListField(child=serializers.CharField())


class SwitchWorkspaceSerializer(serializers.Serializer[dict[str, Any]]):
    workspace_id = serializers.UUIDField(required=False, allow_null=True)
    slug = serializers.CharField(required=False, allow_blank=True, max_length=63)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not attrs.get("workspace_id") and not attrs.get("slug"):
            raise serializers.ValidationError(
                {"detail": "Informe 'workspace_id' ou 'slug' do workspace."}
            )
        return attrs
