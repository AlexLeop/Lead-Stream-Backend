from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from leadstream.security.models import APIKey
    from leadstream.tenancy.models import Tenant


def hash_api_key(raw_key: str) -> str:
    """Calcula o hash SHA-256 de uma chave bruta de API."""
    return hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()


def verify_api_key(raw_key: str, hashed_key: str) -> bool:
    """Compara a chave fornecida com o hash persistido de forma segura contra timing attacks."""
    candidate_hash = hash_api_key(raw_key)
    return hmac.compare_digest(candidate_hash, hashed_key)


def generate_api_key(
    tenant: Tenant,
    name: str,
    role: str = "OPERATOR",
    env: str = "live",
    scopes: list[str] | None = None,
    **kwargs: Any,
) -> tuple[APIKey, str]:
    """Gera uma nova chave de API criptograficamente segura.
    
    Retorna uma tupla (instancia_APIKey, chave_bruta).
    A chave bruta e exibida apenas no momento de sua emissao e nunca mais pode ser recuperada.
    """
    from leadstream.security.models import APIKey, WorkspaceRole

    valid_env = "live" if env == "live" else "test"
    random_part = secrets.token_urlsafe(32).replace("-", "").replace("_", "")[:32]
    raw_key = f"ls_{valid_env}_{random_part}"
    prefix = raw_key[:16]
    hashed_key = hash_api_key(raw_key)

    if role not in WorkspaceRole.values:
        role = WorkspaceRole.OPERATOR

    api_key_obj = APIKey.objects.create(
        tenant=tenant,
        name=name,
        prefix=prefix,
        hashed_key=hashed_key,
        role=role,
        scopes=scopes or [],
        **kwargs,
    )
    return api_key_obj, raw_key
