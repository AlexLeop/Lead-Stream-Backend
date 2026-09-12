from __future__ import annotations

import os
import secrets
from typing import Any

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from leadstream.security.crypto import generate_api_key
from leadstream.security.models import APIKey, WorkspaceMembership, WorkspaceRole
from leadstream.tenancy.services import get_internal_tenant


class Command(BaseCommand):
    help = "Inicializa o Super Admin mestre do sistema e emite a primeira API Key criptográfica."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--username",
            type=str,
            default=None,
            help="Nome de usuário do Super Admin (padrão: $DJANGO_SUPERUSER_USERNAME ou 'admin')",
        )
        parser.add_argument(
            "--email",
            type=str,
            default=None,
            help="E-mail do Super Admin (padrão: $DJANGO_SUPERUSER_EMAIL ou admin local)",
        )
        parser.add_argument(
            "--password",
            type=str,
            default=None,
            help="Senha de acesso (padrão: $DJANGO_SUPERUSER_PASSWORD ou gerada aleatoriamente)",
        )
        parser.add_argument(
            "--key-name",
            type=str,
            default="Chave Mestre Inicial",
            help="Nome descritivo da primeira chave mestre de integração",
        )
        parser.add_argument(
            "--force-new-key",
            action="store_true",
            default=False,
            help="Gera uma nova chave de API mesmo se já existir uma chave ativa para o tenant.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        username = options["username"] or os.getenv("DJANGO_SUPERUSER_USERNAME") or "admin"
        email = options["email"] or os.getenv("DJANGO_SUPERUSER_EMAIL") or "admin@leadstream.local"
        raw_password = options["password"] or os.getenv("DJANGO_SUPERUSER_PASSWORD")
        key_name = options["key_name"]
        force_new_key = bool(options.get("force_new_key", False))

        tenant = get_internal_tenant()

        user = User.objects.filter(username=username).first()
        if user:
            user.email = email
            if raw_password:
                user.set_password(raw_password)
                password_display = raw_password
            else:
                password_display = "[Mantida inalterada]"
            user.is_superuser = True
            user.is_staff = True
            user.is_active = True
            user.save()
            action_desc = "Super Admin atualizado com sucesso"
        else:
            password_to_set = raw_password or secrets.token_urlsafe(16)
            password_display = password_to_set
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password_to_set,
            )
            action_desc = "Super Admin criado com sucesso"

        membership, _ = WorkspaceMembership.objects.update_or_create(
            user=user,
            tenant=tenant,
            defaults={"role": WorkspaceRole.ADMIN, "is_active": True},
        )

        existing_key = APIKey.objects.filter(
            tenant=tenant, is_active=True, role=WorkspaceRole.ADMIN
        ).first()

        if not existing_key or force_new_key:
            _api_key_obj, raw_key = generate_api_key(
                tenant=tenant,
                name=key_name,
                role=WorkspaceRole.ADMIN,
                env="live",
            )
            key_notice = [
                self.style.WARNING("  ⭐ CHAVE DE API MESTRE (EXIBIDA UMA ÚNICA VEZ):"),
                self.style.NOTICE(f"  {raw_key}"),
            ]
        else:
            key_notice = [
                self.style.SUCCESS(
                    f"  ⭐ Chave ativa mantida: {existing_key.name} ({existing_key.prefix}...)"
                ),
            ]

        banner = "=" * 65
        line = "─" * 65
        self.stdout.write(self.style.SUCCESS(banner))
        self.stdout.write(self.style.SUCCESS(f"  🔐 LEADSTREAM SECURITY — {action_desc}"))
        self.stdout.write(self.style.SUCCESS(banner))
        self.stdout.write("")
        self.stdout.write(f"  👤 Usuário:      {username}")
        self.stdout.write(f"  📧 E-mail:       {email}")
        self.stdout.write(f"  🔑 Senha:        {password_display}")
        self.stdout.write(f"  🏢 Workspace:    {tenant.name} ({tenant.slug})")
        self.stdout.write(f"  🛡️  Papel:        {membership.role}")
        self.stdout.write("")
        self.stdout.write(f"  {line}")
        for notice_line in key_notice:
            self.stdout.write(notice_line)
        self.stdout.write(f"  {line}")
        self.stdout.write("")
        self.stdout.write("  ⚠️  IMPORTANTE: Guarde estas credenciais em um cofre de senhas.")
        self.stdout.write(self.style.SUCCESS(banner))
