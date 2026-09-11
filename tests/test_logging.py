from __future__ import annotations

import logging
import re

import pytest
import structlog
from django.test import Client

from leadstream.common.logging import REDACTED


def test_request_id_valido_e_devolvido_no_response(client: Client) -> None:
    response = client.get("/health/live", headers={"X-Request-ID": "req-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-123"


def test_request_id_invalido_e_substituido(client: Client) -> None:
    response = client.get("/health/live", headers={"X-Request-ID": "inválido com espaços"})

    request_id = response.headers["X-Request-ID"]
    assert request_id != "inválido com espaços"
    assert re.fullmatch(r"[a-f0-9]{32}", request_id)


def test_log_estruturado_redige_segredos_e_contatos(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)

    structlog.get_logger("leadstream.test").info(
        "provedor consultado para decisor@example.com e +55 11 99999-9999",
        api_key="sentinel-private-key",
        authorization="Bearer sentinel-token",
        nested={"telefone": "+55 11 98888-7777"},
    )

    rendered = caplog.text
    assert "sentinel-private-key" not in rendered
    assert "sentinel-token" not in rendered
    assert "decisor@example.com" not in rendered
    assert "99999-9999" not in rendered
    assert "98888-7777" not in rendered
    assert REDACTED in rendered


def test_openapi_documenta_workspace_e_health(client: Client) -> None:
    response = client.get("/api/v1/schema/", headers={"Accept": "application/json"})

    assert response.status_code == 200
    data = response.json()
    paths = data["paths"]
    assert "/api/v1/workspace/" in paths
    assert "/api/v1/leads/{item_id}/canonical/" in paths
    assert "/health/live" in paths
    assert "/health/ready" in paths

    components = data.get("components", {})
    assert "CanonicalLeadPayload" in components.get("schemas", {})
    assert "TenantHeader" in components.get("securitySchemes", {})

    docs_response = client.get("/api/v1/docs/")
    assert docs_response.status_code == 200
    docs_html = docs_response.content.decode("utf-8")
    assert "LeadStream" in docs_html
    assert "Scalar Docs" in docs_html
