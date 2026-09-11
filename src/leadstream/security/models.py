from __future__ import annotations

import uuid
from typing import ClassVar

from django.conf import settings
from django.db import models
from django.utils import timezone


class WorkspaceRole(models.TextChoices):
    ADMIN = "ADMIN", "Administrador"
    OPERATOR = "OPERATOR", "Operador"
    READ_ONLY = "READ_ONLY", "Somente Leitura"


class WorkspaceMembership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workspace_memberships",
    )
    tenant = models.ForeignKey(
        "tenancy.Tenant",
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(
        max_length=20,
        choices=WorkspaceRole.choices,
        default=WorkspaceRole.OPERATOR,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "security_workspace_memberships"
        verbose_name = "Vínculo de Workspace"
        verbose_name_plural = "Vínculos de Workspace"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["user", "tenant"],
                name="unique_user_tenant_membership",
            )
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["user", "tenant", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.get_username()} -> {self.tenant.slug} ({self.role})"


class APIKey(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenancy.Tenant",
        on_delete=models.CASCADE,
        related_name="api_keys",
    )
    name = models.CharField(max_length=120)
    prefix = models.CharField(max_length=16, db_index=True)
    hashed_key = models.CharField(max_length=64, unique=True, db_index=True)
    role = models.CharField(
        max_length=20,
        choices=WorkspaceRole.choices,
        default=WorkspaceRole.OPERATOR,
    )
    scopes = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "security_api_keys"
        verbose_name = "Chave de API"
        verbose_name_plural = "Chaves de API"
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["prefix", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.prefix}...) [{self.tenant.slug}]"

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_at and self.expires_at <= timezone.now())


class SecurityAuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    tenant = models.ForeignKey(
        "tenancy.Tenant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    actor_type = models.CharField(max_length=20)  # USER / API_KEY / ANONYMOUS / SUPERADMIN
    actor_id = models.CharField(max_length=64, blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True, default="")
    action = models.CharField(max_length=64, db_index=True)
    resource_accessed = models.CharField(max_length=255, blank=True, default="")
    status_code = models.IntegerField(default=200)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "security_audit_logs"
        verbose_name = "Log de Auditoria de Segurança"
        verbose_name_plural = "Logs de Auditoria de Segurança"
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["tenant", "timestamp"]),
            models.Index(fields=["action", "timestamp"]),
        ]

    def __str__(self) -> str:
        actor = f"{self.actor_type}:{self.actor_id}"
        return f"[{self.timestamp.isoformat()}] {self.action} by {actor} -> {self.status_code}"
