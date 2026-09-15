from __future__ import annotations

from typing import Any

from django.views.generic import TemplateView
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.request import Request
from rest_framework.response import Response

from .health import HealthResult, check_database, check_dependencies


@extend_schema(
    operation_id="consultar_vida",
    summary="Verificar processo da API",
    responses={200: OpenApiTypes.OBJECT},
    tags=["Saúde"],
)
@api_view(["GET"])
@authentication_classes([])
@permission_classes([])
@throttle_classes([])
def live(request: Request) -> Response:
    del request
    return Response({"status": "ok"})


@extend_schema(
    operation_id="consultar_prontidao",
    summary="Verificar prontidão da API e PostgreSQL",
    responses={200: OpenApiTypes.OBJECT, 503: OpenApiTypes.OBJECT},
    tags=["Saúde"],
)
@api_view(["GET"])
@authentication_classes([])
@permission_classes([])
@throttle_classes([])
def ready(request: Request) -> Response:
    del request
    database = check_database()
    status_code = 200 if database.available else 503
    return Response(
        {"status": "ok" if database.available else "unavailable"},
        status=status_code,
    )


@extend_schema(
    operation_id="consultar_dependencias",
    summary="Diagnosticar serviços opcionais",
    responses={200: OpenApiTypes.OBJECT},
    tags=["Saúde"],
)
@api_view(["GET"])
@authentication_classes([])
@permission_classes([])
@throttle_classes([])
def dependencies(request: Request) -> Response:
    del request
    results = check_dependencies()
    overall = _aggregate_dependency_status(results)
    return Response(
        {
            "status": overall,
            "dependencias": {name: result.as_dict() for name, result in results.items()},
        }
    )


def _aggregate_dependency_status(results: dict[str, HealthResult]) -> str:
    return "ok" if all(result.available for result in results.values()) else "degraded"


class ScalarDocsView(TemplateView):
    template_name = "docs/scalar.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["schema_url"] = "/api/v1/schema/"
        context["title"] = "LeadStream API Reference — Inteligência Cadastral B2B"
        return context
