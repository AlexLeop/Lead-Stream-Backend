from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import ClassVar

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.base import ModelBase

from leadstream.tenancy.branding_models import PlatformBranding

__all__ = ["PlatformBranding", "Tenant", "TenantOwnedModel"]


class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=63, unique=True, editable=False)
    name = models.CharField(max_length=160)
    is_active = models.BooleanField(default=True)
    max_batch_size = models.PositiveIntegerField(default=100000)
    rate_limit_per_minute = models.PositiveIntegerField(default=60)
    max_concurrency = models.PositiveIntegerField(default=4)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leadstream_tenant"
        ordering: ClassVar[list[str]] = ["slug"]

    def __str__(self) -> str:
        return self.name

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if self.pk:
            persisted_slug = (
                type(self).objects.filter(pk=self.pk).values_list("slug", flat=True).first()
            )
            if persisted_slug is not None and persisted_slug != self.slug:
                raise ValidationError({"slug": "O identificador do tenant não pode ser alterado."})
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )


class TenantOwnedModel(models.Model):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="%(app_label)s_%(class)s_set",
        db_index=True,
    )

    class Meta:
        abstract = True
