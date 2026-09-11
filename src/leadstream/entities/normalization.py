from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import validate_email


class DataValidationError(ValueError):
    """Raised when a business identifier cannot be normalized safely."""


def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def normalize_cnpj(value: str) -> str:
    digits = only_digits(value)
    if len(digits) != 14 or len(set(digits)) == 1:
        raise DataValidationError("CNPJ inválido.")

    def check_digit(base: str, weights: tuple[int, ...]) -> str:
        remainder = (
            sum(int(number) * weight for number, weight in zip(base, weights, strict=True)) % 11
        )
        return "0" if remainder < 2 else str(11 - remainder)

    first = check_digit(digits[:12], (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    second = check_digit(digits[:12] + first, (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    if digits[-2:] != first + second:
        raise DataValidationError("CNPJ inválido.")
    return digits


def cnpj_root(value: str) -> str:
    return normalize_cnpj(value)[:8]


def normalize_email(value: str) -> str:
    candidate = (value or "").strip()
    try:
        validate_email(candidate)
    except ValidationError as exc:
        raise DataValidationError("E-mail inválido.") from exc
    local, domain = candidate.rsplit("@", 1)
    if "." not in domain:
        raise DataValidationError("Domínio de e-mail inválido.")
    try:
        ascii_domain = domain.rstrip(".").encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise DataValidationError("Domínio de e-mail inválido.") from exc
    return f"{local.casefold()}@{ascii_domain.casefold()}"


def normalize_domain(value: str) -> str:
    candidate = (value or "").strip()
    if not candidate:
        raise DataValidationError("Domínio inválido.")
    parsed = urlsplit(candidate if "://" in candidate else f"https://{candidate}")
    host = parsed.hostname
    if not host or " " in host or "." not in host:
        raise DataValidationError("Domínio inválido.")
    try:
        normalized = host.rstrip(".").encode("idna").decode("ascii").casefold()
    except UnicodeError as exc:
        raise DataValidationError("Domínio inválido.") from exc
    if normalized.startswith("www."):
        normalized = normalized[4:]
    labels = normalized.split(".")
    if any(not label or len(label) > 63 for label in labels):
        raise DataValidationError("Domínio inválido.")
    return normalized


def normalize_phone_br(value: str) -> str:
    digits = only_digits(value)
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("55"):
        national = digits[2:]
    else:
        national = digits
        digits = f"55{digits}"
    if len(national) not in (10, 11) or national[:2] == "00" or national[2] == "0":
        raise DataValidationError("Telefone brasileiro inválido.")
    if len(set(national)) == 1:
        raise DataValidationError("Telefone brasileiro inválido.")
    return f"+{digits}"


def _json_default(obj: Any) -> str:
    if hasattr(obj, "isoformat"):
        return str(obj.isoformat())
    return str(obj)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )


def fingerprint_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
