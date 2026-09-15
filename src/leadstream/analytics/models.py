from __future__ import annotations

import uuid
from typing import ClassVar

from django.core.exceptions import ValidationError
from django.db import models

from leadstream.entities.models import Entity
from leadstream.tenancy.models import TenantOwnedModel


class ActivationList(TenantOwnedModel):
    """Seleção persistente de entidades pronta para exportação ou ativação."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    description = models.CharField(max_length=500, blank=True)
    crm_target = models.CharField(max_length=80, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leadstream_activation_list"
        ordering: ClassVar[list[str]] = ["-updated_at"]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=("tenant", "archived_at", "updated_at"),
                name="activation_list_state_idx",
            )
        ]


class ActivationListMember(TenantOwnedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activation_list = models.ForeignKey(
        ActivationList,
        on_delete=models.CASCADE,
        related_name="members",
    )
    entity = models.ForeignKey(
        Entity,
        on_delete=models.PROTECT,
        related_name="activation_list_memberships",
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "leadstream_activation_list_member"
        ordering: ClassVar[list[str]] = ["added_at"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("activation_list", "entity"),
                name="activation_list_entity_uniq",
            )
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("tenant", "entity"), name="activation_member_entity_idx")
        ]

    def clean(self) -> None:
        errors: dict[str, str] = {}
        if self.activation_list.tenant_id != self.tenant_id:
            errors["activation_list"] = "A lista deve pertencer ao mesmo workspace."
        if self.entity.tenant_id != self.tenant_id:
            errors["entity"] = "O lead deve pertencer ao mesmo workspace."
        if errors:
            raise ValidationError(errors)
