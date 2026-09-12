from __future__ import annotations

from django.db import models


class PlatformBranding(models.Model):
    platform_name = models.CharField(max_length=120, default="LeadStream")
    logo_url_dark = models.URLField(max_length=500, blank=True, default="")
    logo_url_light = models.URLField(max_length=500, blank=True, default="")
    favicon_url = models.URLField(max_length=500, blank=True, default="")
    accent_color = models.CharField(max_length=32, default="#10B981")
    support_email = models.EmailField(blank=True, default="suporte@leadstream.com.br")
    terms_url = models.URLField(max_length=500, blank=True, default="")
    privacy_url = models.URLField(max_length=500, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leadstream_platform_branding"
        verbose_name = "Configuração White-Label"
        verbose_name_plural = "Configurações White-Label"

    def __str__(self) -> str:
        return f"{self.platform_name} ({self.accent_color})"

    @classmethod
    def get_active(cls) -> PlatformBranding:
        obj, _ = cls.objects.get_or_create(id=1)
        return obj
