from __future__ import annotations

from unittest.mock import patch

import pytest
from django.test import Client

from leadstream.common.health import HealthResult


def test_liveness_nao_consulta_dependencias(client: Client) -> None:
    with (
        patch("leadstream.common.health.check_database") as database,
        patch("leadstream.common.health.check_dependencies") as dependencies,
    ):
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    database.assert_not_called()
    dependencies.assert_not_called()


@pytest.mark.django_db
def test_readiness_confirma_banco_e_migrations(client: Client) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_falha_sem_expor_detalhe(client: Client) -> None:
    with patch(
        "leadstream.common.views.check_database",
        return_value=HealthResult("unavailable"),
    ):
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert "postgres" not in response.content.decode().lower()


def test_dependencias_opcionais_degradam_sem_bloquear_api(client: Client) -> None:
    results = {
        "redis": HealthResult("ok"),
        "rabbitmq": HealthResult("unavailable"),
        "appwrite": HealthResult("degraded"),
    }
    with patch("leadstream.common.views.check_dependencies", return_value=results):
        response = client.get("/health/dependencies")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "dependencias": {
            "redis": {"status": "ok"},
            "rabbitmq": {"status": "unavailable"},
            "appwrite": {"status": "degraded"},
        },
    }


def test_documentation_endpoints_accessible_without_auth(client: Client) -> None:
    import json

    resp_docs = client.get("/api/v1/docs/")
    assert resp_docs.status_code == 200
    assert "LeadStream" in resp_docs.content.decode()

    resp_schema = client.get("/api/v1/schema/?format=json")
    assert resp_schema.status_code == 200
    schema_json = json.loads(resp_schema.content)
    assert schema_json["openapi"] == "3.1.0"
    assert "BearerAuth" in schema_json["components"]["securitySchemes"]
    assert "ApiKeyAuth" in schema_json["components"]["securitySchemes"]
