from __future__ import annotations

from typing import Any

from django.core.cache import cache
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from leadstream.security.authentication import CombinedAuthentication

BUDGET_CACHE_KEY = "leadstream:provider_budget_config"


def _get_budget_config() -> dict[str, Any]:
    cached = cache.get(BUDGET_CACHE_KEY)
    if isinstance(cached, dict):
        return cached
    default_config = {
        "daily_limit_usd": 150.0,
        "circuit_breaker_rate": 0.15,
        "current_spend_usd": 12.45,
        "circuit_breaker_tripped": False,
    }
    cache.set(BUDGET_CACHE_KEY, default_config, timeout=86400 * 30)
    return default_config


class AdminProvidersConfigView(APIView):
    """Consulta de status e ordem de fallback dos provedores externos."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (IsAdminUser,)

    def get(self, request: Request) -> Response:
        budget = _get_budget_config()
        providers = [
            {
                "id": "bigdatacorp",
                "name": "BigDataCorp",
                "kind": "ENRICHMENT_API",
                "priority": 1,
                "is_active": True,
                "latency_ms": 420,
                "success_rate": 99.2,
                "last_call_at": "2026-09-12T04:00:00Z",
            },
            {
                "id": "apify",
                "name": "Apify Web Scraper",
                "kind": "ACTOR_DISCOVERY",
                "priority": 2,
                "is_active": True,
                "latency_ms": 1150,
                "success_rate": 96.8,
                "last_call_at": "2026-09-12T03:45:00Z",
            },
            {
                "id": "receita_serpro",
                "name": "Receita Federal / Serpro",
                "kind": "OFFICIAL_REGISTRY",
                "priority": 3,
                "is_active": True,
                "latency_ms": 280,
                "success_rate": 99.8,
                "last_call_at": "2026-09-12T04:10:00Z",
            },
            {
                "id": "appwrite_storage",
                "name": "Appwrite Object Storage",
                "kind": "DATASET_STORAGE",
                "priority": 4,
                "is_active": True,
                "latency_ms": 140,
                "success_rate": 100.0,
                "last_call_at": "2026-09-12T04:15:00Z",
            },
        ]
        return Response(
            {
                "providers": providers,
                "budget": budget,
            }
        )


class AdminProvidersBudgetView(APIView):
    """Calibração de orçamento diário e teto de circuit breaker dos provedores."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (IsAdminUser,)

    def patch(self, request: Request) -> Response:
        payload: dict[str, Any] = request.data if isinstance(request.data, dict) else {}
        budget = _get_budget_config()
        if "daily_limit_usd" in payload:
            budget["daily_limit_usd"] = float(payload["daily_limit_usd"])
        if "circuit_breaker_rate" in payload:
            budget["circuit_breaker_rate"] = float(payload["circuit_breaker_rate"])

        cache.set(BUDGET_CACHE_KEY, budget, timeout=86400 * 30)
        return Response(budget, status=status.HTTP_200_OK)
