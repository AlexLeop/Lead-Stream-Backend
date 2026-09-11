from __future__ import annotations

from typing import Any

from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from leadstream.security.models import WorkspaceRole

ROLE_HIERARCHY: dict[str, int] = {
    WorkspaceRole.READ_ONLY: 1,
    WorkspaceRole.OPERATOR: 2,
    WorkspaceRole.ADMIN: 3,
}


def _get_user_role(request: Request) -> str | None:
    if getattr(request.user, "is_superuser", False):
        return WorkspaceRole.ADMIN

    from leadstream.security.authentication import ApiKeyUser

    if isinstance(request.user, ApiKeyUser):
        return str(request.user.role)

    membership = getattr(request, "workspace_membership", None)
    if membership:
        return str(membership.role)

    return None


class IsTenantMember(BasePermission):
    """Garante que a requisição pertença ativamente ao tenant contextualizado."""

    def has_permission(self, request: Request, view: Any) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False

        if getattr(request.user, "is_superuser", False):
            return True

        tenant = getattr(request, "tenant", None)
        if not tenant:
            return False

        from leadstream.security.authentication import ApiKeyUser

        if isinstance(request.user, ApiKeyUser):
            return bool(request.user.tenant.pk == tenant.pk and request.user.api_key.is_active)

        membership = getattr(request, "workspace_membership", None)
        if membership:
            return bool(membership.is_active and membership.tenant.pk == tenant.pk)

        return False


class HasWorkspaceRole(BasePermission):
    """Valida se o usuário ou chave possui papel hierarquicamente suficiente no workspace."""

    def __init__(self, min_role: str = WorkspaceRole.OPERATOR) -> None:
        self.min_role = min_role

    def __call__(self) -> HasWorkspaceRole:
        return self

    def has_permission(self, request: Request, view: Any) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False

        if getattr(request.user, "is_superuser", False):
            return True

        current_role = _get_user_role(request)
        if not current_role:
            return False

        current_level = ROLE_HIERARCHY.get(current_role, 0)
        required_level = ROLE_HIERARCHY.get(self.min_role, 0)
        return current_level >= required_level


class IsWorkspaceAdmin(HasWorkspaceRole):
    def __init__(self) -> None:
        super().__init__(min_role=WorkspaceRole.ADMIN)


class IsWorkspaceOperator(HasWorkspaceRole):
    def __init__(self) -> None:
        super().__init__(min_role=WorkspaceRole.OPERATOR)


class IsWorkspaceReadOnly(HasWorkspaceRole):
    def __init__(self) -> None:
        super().__init__(min_role=WorkspaceRole.READ_ONLY)


class IsSuperAdminUser(BasePermission):
    """Exige que o usuário seja um Super Admin global do sistema."""

    def has_permission(self, request: Request, view: Any) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "is_superuser", False))
