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


def resolve_tenant(request: Request | None) -> Tenant:
    if request is None:
        from leadstream.tenancy.services import get_internal_tenant

        return get_internal_tenant()

    tenant = getattr(request, "tenant", None)
    if isinstance(tenant, Tenant):
        return tenant

    if hasattr(request, "headers"):
        tenant_header = request.headers.get("X-Tenant-ID")
        if tenant_header:
            from uuid import UUID

            from django.http import Http404

            try:
                return Tenant.objects.get(id=UUID(tenant_header))
            except (Tenant.DoesNotExist, ValueError) as exc:
                raise Http404("Tenant não encontrado.") from exc

    from leadstream.tenancy.services import get_internal_tenant

    return get_internal_tenant()
