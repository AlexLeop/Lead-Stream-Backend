from __future__ import annotations

import logging
from typing import Any

from redis.exceptions import RedisError
from rest_framework.request import Request
from rest_framework.throttling import SimpleRateThrottle

logger = logging.getLogger(__name__)


class ResilientRateThrottle(SimpleRateThrottle):
    """Throttle base com degradacao graciosa caso o cache esteja indisponivel."""

    def allow_request(self, request: Request, view: Any) -> bool:
        try:
            return super().allow_request(request, view)
        except (ConnectionError, TimeoutError, OSError, RedisError) as exc:
            logger.warning(
                "Falha ao consultar cache para rate limiting (%s: %s). Permitindo requisicao.",
                type(exc).__name__,
                exc,
            )
            return True


class AuthRateThrottle(ResilientRateThrottle):
    """Limita tentativas de login a 5 requisicoes por minuto por IP."""

    scope = "auth"

    def get_cache_key(self, request: Request, view: Any) -> str | None:
        ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class AuthRefreshRateThrottle(ResilientRateThrottle):
    """Limita tentativas de refresh de tokens a 10 requisicoes por minuto por IP."""

    scope = "auth_refresh"

    def get_cache_key(self, request: Request, view: Any) -> str | None:
        ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class TenantApiKeyRateThrottle(ResilientRateThrottle):
    """Limita consumo de endpoints por workspace ou API Key a 120 requisicoes por minuto."""

    scope = "tenant"

    def get_cache_key(self, request: Request, view: Any) -> str | None:
        tenant = getattr(request, "tenant", None)
        if tenant:
            return self.cache_format % {"scope": self.scope, "ident": f"tenant_{tenant.pk}"}

        if request.user and request.user.is_authenticated:
            return self.cache_format % {"scope": self.scope, "ident": f"user_{request.user.pk}"}

        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}
