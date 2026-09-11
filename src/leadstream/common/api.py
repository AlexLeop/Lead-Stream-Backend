from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from rest_framework.exceptions import ValidationError

if TYPE_CHECKING:
    from rest_framework.request import Request

    from leadstream.tenancy.models import Tenant


def reject_tenant_override(data: object) -> None:
    if isinstance(data, Mapping) and {"tenant", "tenant_id"}.intersection(data):
        raise ValidationError(
            {"tenant": "O tenant é aplicado automaticamente e não pode ser informado."}
        )


def resolve_tenant(request: Request) -> Tenant:
    tenant = getattr(request, "tenant", None)
    if tenant:
        return tenant

    from leadstream.tenancy.services import get_internal_tenant

    return get_internal_tenant()
