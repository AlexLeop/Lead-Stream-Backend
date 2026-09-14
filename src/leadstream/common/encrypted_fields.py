from __future__ import annotations

import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import models

_ENCRYPTED_PREFIX = "enc:v1:"


def validate_encryption_keys(raw_keys: list[str]) -> list[Fernet]:
    keys = [str(key).strip() for key in raw_keys if str(key).strip()]
    if not keys:
        raise ImproperlyConfigured(
            "FIELD_ENCRYPTION_KEYS deve conter ao menos uma chave Fernet."
        )
    try:
        return [Fernet(key.encode("ascii")) for key in keys]
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured(
            "FIELD_ENCRYPTION_KEYS contém uma chave inválida; gere uma chave Fernet."
        ) from exc


def _cipher() -> MultiFernet:
    raw_keys = getattr(settings, "FIELD_ENCRYPTION_KEYS", [])
    return MultiFernet(validate_encryption_keys(raw_keys))


def encrypt_json(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    token = _cipher().encrypt(payload).decode("ascii")
    return f"{_ENCRYPTED_PREFIX}{token}"


def decrypt_json(value: str) -> dict[str, Any]:
    if not value.startswith(_ENCRYPTED_PREFIX):
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValidationError("O valor protegido deve ser um objeto JSON.")
        return parsed
    try:
        payload = _cipher().decrypt(value.removeprefix(_ENCRYPTED_PREFIX).encode("ascii"))
    except InvalidToken as exc:
        raise ValidationError(
            "Não foi possível descriptografar o campo protegido com as chaves configuradas."
        ) from exc
    parsed = json.loads(payload.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValidationError("O valor protegido deve ser um objeto JSON.")
    return parsed


class EncryptedJSONField(models.TextField):  # type: ignore[type-arg]
    """Objeto JSON cifrado no banco e entregue como ``dict`` no domínio."""

    description = "JSON criptografado com Fernet"

    def from_db_value(
        self,
        value: str | dict[str, Any] | None,
        expression: Any,
        connection: Any,
    ) -> dict[str, Any]:
        return self.to_python(value)

    def to_python(self, value: Any) -> dict[str, Any]:
        if value in (None, ""):
            return {}
        if isinstance(value, dict):
            return value
        if not isinstance(value, str):
            raise ValidationError("O valor protegido deve ser um objeto JSON.")
        parsed = decrypt_json(value)
        return parsed

    def get_prep_value(self, value: Any) -> str:
        if isinstance(value, str) and value.startswith(_ENCRYPTED_PREFIX):
            return value
        normalized = self.to_python(value)
        return encrypt_json(normalized)

    def value_to_string(self, obj: models.Model) -> str:
        value = self.value_from_object(obj)
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
