from __future__ import annotations

import secrets
from typing import Any

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from leadstream.security.crypto import generate_api_key
from leadstream.security.models import WorkspaceMembership, WorkspaceRole
from leadstream.tenancy.services import get_internal_tenant


class Command(BaseCommand):
    help = "Inicializa o Super Admin mestre do sistema e emite a primeira API Key criptográfica."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--username",
            type=str,
            default="admin",
            help="Nome de usuário do Super Admin (padrão: admin)",
        )
        parser.add_argument(
            "--email",
            type=str,
            default="admin@leadstream.local",
            help="E-mail corporativo do Super Admin",
        )
        parser.add_argument(
            "--password",
            type=str,
            default=None,
            help="Senha de acesso (se não fornecida, uma senha aleatória forte será gerada)",
        )
        parser.add_argument(
            "--key-name",
            type=str,
            default="Chave Mestre Inicial",
            help="Nome descritivo da primeira chave mestre de integração",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        username = options["username"]
        email = options["email"]
        raw_password = options["password"] or secrets.token_urlsafe(16)
        key_name = options["key_name"]

        tenant = get_internal_tenant()

        user = User.objects.filter(username=username).first()
        if user:
            user.email = email
            user.set_password(raw_password)
            user.is_superuser = True
            user.is_staff = True
            user.is_active = True
            user.save()
            action_desc = "Super Admin atualizado com sucesso"
        else:
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=raw_password,
            )
            action_desc = "Super Admin criado com sucesso"

        membership, _ = WorkspaceMembership.objects.update_or_create(
            user=user,
            tenant=tenant,
            defaults={"role": WorkspaceRole.ADMIN, "is_active": True},
        )

        _api_key_obj, raw_key = generate_api_key(
            tenant=tenant,
            name=key_name,
            role=WorkspaceRole.ADMIN,
            env="live",
        )

        banner = "=" * 65
        line = "─" * 65
        self.stdout.write(self.style.SUCCESS(banner))
        self.stdout.write(self.style.SUCCESS(f"  🔐 LEADSTREAM SECURITY — {action_desc}"))
        self.stdout.write(self.style.SUCCESS(banner))
        self.stdout.write("")
        self.stdout.write(f"  👤 Usuário:      {username}")
        self.stdout.write(f"  📧 E-mail:       {email}")
        self.stdout.write(f"  🔑 Senha:        {raw_password}")
        self.stdout.write(f"  🏢 Workspace:    {tenant.name} ({tenant.slug})")
        self.stdout.write(f"  🛡️  Papel:        {membership.role}")
        self.stdout.write("")
        self.stdout.write(f"  {line}")
        self.stdout.write(self.style.WARNING("  ⭐ CHAVE DE API MESTRE (EXIBIDA UMA ÚNICA VEZ):"))
        self.stdout.write(self.style.NOTICE(f"  {raw_key}"))
        self.stdout.write(f"  {line}")
        self.stdout.write("")
        self.stdout.write("  ⚠️  IMPORTANTE: Guarde estas credenciais em um cofre de senhas.")
        self.stdout.write("      A chave de API bruta nunca poderá ser recuperada posteriormente.")
        self.stdout.write(self.style.SUCCESS(banner))
