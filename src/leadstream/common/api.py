from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from rest_framework.exceptions import ValidationError

from leadstream.tenancy.models import Tenant

if TYPE_CHECKING:
    from rest_framework.request import Request


def reject_tenant_override(data: object) -> None:
    if isinstance(data, Mapping) and {"tenant", "tenant_id"}.intersection(data):
        raise ValidationError(
            {"tenant": "O tenant é aplicado automaticamente e não pode ser informado."}
        )


def resolve_tenant(request: Request) -> Tenant:
    tenant = getattr(request, "tenant", None)
    if isinstance(tenant, Tenant):
        return tenant

    from leadstream.tenancy.services import get_internal_tenant

    return get_internal_tenant()

