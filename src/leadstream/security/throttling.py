from __future__ import annotations

from typing import Any

from rest_framework.request import Request
from rest_framework.throttling import SimpleRateThrottle


class AuthRateThrottle(SimpleRateThrottle):
    """Limita tentativas de login a 5 requisicoes por minuto por IP."""

    scope = "auth"

    def get_cache_key(self, request: Request, view: Any) -> str | None:
        ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class AuthRefreshRateThrottle(SimpleRateThrottle):
    """Limita tentativas de refresh de tokens a 10 requisicoes por minuto por IP."""

    scope = "auth_refresh"

    def get_cache_key(self, request: Request, view: Any) -> str | None:
        ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class TenantApiKeyRateThrottle(SimpleRateThrottle):
    """Limita consumo de endpoints por workspace ou API Key a 120 requisicoes por minuto."""

    scope = "tenant"

    def get_cache_key(self, request: Request, view: Any) -> str | None:
        tenant = getattr(request, "tenant", None)
        if tenant:
            return self.cache_format % {"scope": self.scope, "ident": f"tenant_{tenant.pk}"}

        if request.user and request.user.is_authenticated:
            return self.cache_format % {"scope": self.scope, "ident": f"user_{request.user.pk}"}

        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}
