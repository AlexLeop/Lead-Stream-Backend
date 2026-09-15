from __future__ import annotations

from typing import Any

import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_cors_preflight_allows_idempotency_key_header(settings: Any) -> None:
    origin = "https://lead-stream-frontend.a3rpjn.easypanel.host"
    settings.CORS_ALLOWED_ORIGINS = [origin]

    client = APIClient()
    response = client.options(
        "/api/v1/enrichment/company",
        HTTP_ORIGIN=origin,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="idempotency-key,authorization,content-type",
    )

    assert response.status_code == 200
    allow_headers = response.headers.get("Access-Control-Allow-Headers", "").lower()
    assert "idempotency-key" in allow_headers
    assert response.headers.get("Access-Control-Allow-Origin") == origin
