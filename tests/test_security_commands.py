from __future__ import annotations

import io

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

from leadstream.security.models import APIKey, WorkspaceMembership, WorkspaceRole
from leadstream.tenancy.models import Tenant


@pytest.mark.django_db
def test_setup_security_admin_command() -> None:
    Tenant.objects.get_or_create(slug="internal", defaults={"name": "Operação interna"})

    out = io.StringIO()
    call_command(
        "setup_security_admin",
        username="admin_test",
        email="adm@teste.com",
        password="MyStrongPassword123!",
        stdout=out,
    )

    output = out.getvalue()
    assert "LEADSTREAM SECURITY" in output
    assert "admin_test" in output
    assert "ls_live_" in output

    user = User.objects.get(username="admin_test")
    assert user.is_superuser is True
    assert user.check_password("MyStrongPassword123!") is True

    membership = WorkspaceMembership.objects.get(user=user)
    assert membership.role == WorkspaceRole.ADMIN

    api_key = APIKey.objects.filter(tenant=membership.tenant).first()
    assert api_key is not None
    assert api_key.role == WorkspaceRole.ADMIN
