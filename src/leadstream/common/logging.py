from __future__ import annotations

import re
from collections.abc import Mapping
from typing import cast

import structlog
from structlog.contextvars import merge_contextvars
from structlog.typing import EventDict, Processor, WrappedLogger

REDACTED = "[REDACTED]"
SENSITIVE_KEY_PARTS = (
    "authorization",
    "cookie",
    "password",
    "senha",
    "secret",
    "token",
    "api_key",
    "apikey",
    "email",
    "e-mail",
    "phone",
    "telefone",
    "celular",
    "whatsapp",
    "cpf",
)
EMAIL_PATTERN = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
PHONE_PATTERN = re.compile(r"(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)")


def redact_sensitive(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    del logger, method_name
    for key, value in list(event_dict.items()):
        event_dict[key] = _sanitize(value, key=key)
    return event_dict


def build_logging_config(level: str) -> dict[str, object]:
    shared_processors: list[Processor] = [
        merge_contextvars,
        structlog.stdlib.add_log_level,
        redact_sensitive,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": structlog.stdlib.ProcessorFormatter,
                "foreign_pre_chain": shared_processors,
                "processors": [
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    structlog.processors.JSONRenderer(ensure_ascii=False),
                ],
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
            }
        },
        "root": {"handlers": ["console"], "level": level.upper()},
        "loggers": {
            "django.server": {"handlers": ["console"], "level": level.upper(), "propagate": False},
        },
    }


def _sanitize(value: object, *, key: str) -> object:
    normalized_key = key.lower().replace("-", "_")
    if any(fragment in normalized_key for fragment in SENSITIVE_KEY_PARTS):
        return REDACTED
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        return {
            str(item_key): _sanitize(item, key=str(item_key)) for item_key, item in mapping.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_sanitize(item, key=key) for item in value]
    if isinstance(value, str):
        without_email = EMAIL_PATTERN.sub(REDACTED, value)
        return PHONE_PATTERN.sub(REDACTED, without_email)
    return value
