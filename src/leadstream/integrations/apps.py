from __future__ import annotations

from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "leadstream.integrations"
    verbose_name = "Integrações e Conectores de CRM"
