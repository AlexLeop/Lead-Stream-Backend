from __future__ import annotations

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_auth_login_rate_limiting_throttle() -> None:
    cache.clear()
    client = APIClient()

    # Dispara 5 tentativas de login
    for _ in range(5):
        response = client.post(
            "/api/v1/auth/token/",
            {"username": "nonexistent_user", "password": "wrong_password"},
            format="json",
        )
        assert response.status_code == 401

    # A 6ª tentativa na mesma janela temporal de 1 minuto deve receber 429 Too Many Requests
    blocked_response = client.post(
        "/api/v1/auth/token/",
        {"username": "nonexistent_user", "password": "wrong_password"},
        format="json",
    )
    assert blocked_response.status_code == 429
    data = blocked_response.json()
    assert "detail" in data
