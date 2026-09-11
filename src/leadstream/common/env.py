from __future__ import annotations

import os
from collections.abc import Callable
from typing import overload

from django.core.exceptions import ImproperlyConfigured


@overload
def env(name: str, *, default: str) -> str: ...


@overload
def env(name: str, *, default: None = None) -> str | None: ...


def env(name: str, *, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def required_env(name: str) -> str:
    value = env(name)
    if value is None:
        raise ImproperlyConfigured(f"A variável de ambiente {name} é obrigatória.")
    return value


def env_bool(name: str, *, default: bool) -> bool:
    raw = env(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ImproperlyConfigured(f"A variável de ambiente {name} deve ser booleana.")


def env_int(name: str, *, default: int) -> int:
    return _convert(name, int, default=default, type_label="inteira")


def env_list(
    name: str,
    *,
    default: list[str] | None = None,
    required: bool = False,
) -> list[str]:
    raw = env(name)
    if raw is None:
        if required:
            raise ImproperlyConfigured(f"A variável de ambiente {name} é obrigatória.")
        return list(default or [])
    values = [item.strip() for item in raw.split(",") if item.strip()]
    if required and not values:
        raise ImproperlyConfigured(f"A variável de ambiente {name} não pode estar vazia.")
    return values


def _convert[T](
    name: str,
    converter: Callable[[str], T],
    *,
    default: T,
    type_label: str,
) -> T:
    raw = env(name)
    if raw is None:
        return default
    try:
        return converter(raw)
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured(f"A variável de ambiente {name} deve ser {type_label}.") from exc
