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


@pytest.mark.django_db
def test_setup_security_admin_with_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    Tenant.objects.get_or_create(slug="internal", defaults={"name": "Operação interna"})

    monkeypatch.setenv("DJANGO_SUPERUSER_USERNAME", "env_admin")
    monkeypatch.setenv("DJANGO_SUPERUSER_EMAIL", "env_admin@empresa.com.br")
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "EnvSecretPassword987#")

    out = io.StringIO()
    call_command("setup_security_admin", stdout=out)

    output = out.getvalue()
    assert "LEADSTREAM SECURITY" in output
    assert "env_admin" in output
    assert "env_admin@empresa.com.br" in output

    user = User.objects.get(username="env_admin")
    assert user.is_superuser is True
    assert user.check_password("EnvSecretPassword987#") is True

    membership = WorkspaceMembership.objects.get(user=user)
    assert membership.role == WorkspaceRole.ADMIN

    # Execução subsequente (idempotente): não deve gerar duplicata de APIKey
    out2 = io.StringIO()
    call_command("setup_security_admin", stdout=out2)
    assert APIKey.objects.filter(tenant=membership.tenant, is_active=True).count() == 1


@pytest.mark.django_db
def test_email_or_username_authentication() -> None:
    from django.contrib.auth import authenticate

    User.objects.create_user(
        username="corporativo_user",
        email="diretor@empresa.com.br",
        password="ValidPassword456!",
    )

    # Teste 1: Autenticação por username
    user1 = authenticate(username="corporativo_user", password="ValidPassword456!")
    assert user1 is not None
    assert isinstance(user1, User)
    assert user1.username == "corporativo_user"

    # Teste 2: Autenticação por e-mail
    user2 = authenticate(username="diretor@empresa.com.br", password="ValidPassword456!")
    assert user2 is not None
    assert isinstance(user2, User)
    assert user2.username == "corporativo_user"

    # Teste 3: Autenticação por e-mail com maiúsculas (case-insensitive)
    user3 = authenticate(username="DIRETOR@EMPRESA.COM.BR", password="ValidPassword456!")
    assert user3 is not None

    # Teste 4: Senha incorreta
    user_fail = authenticate(username="diretor@empresa.com.br", password="WrongPassword")
    assert user_fail is None
