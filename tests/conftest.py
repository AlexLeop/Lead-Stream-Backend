from __future__ import annotations

from typing import Any

import pytest
from rest_framework.test import APIClient

from leadstream.security.crypto import generate_api_key
from leadstream.security.models import APIKey, WorkspaceRole
from leadstream.tenancy.services import get_internal_tenant


@pytest.fixture
def internal_api_key(db: Any) -> tuple[APIKey, str]:
    tenant = get_internal_tenant()
    return generate_api_key(tenant=tenant, name="Chave Testes Internos", role=WorkspaceRole.ADMIN)


@pytest.fixture
def api_client(internal_api_key: tuple[APIKey, str]) -> APIClient:
    _, raw_key = internal_api_key
    client = APIClient()
    client.credentials(HTTP_X_API_KEY=raw_key)
    return client
