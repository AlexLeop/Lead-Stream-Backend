from __future__ import annotations

import hashlib
import re


def correlation_tag(value: str, *, length: int = 12) -> str:
    """Identificador irreversível curto para correlacionar logs sem expor o valor."""
    digest = hashlib.sha256((value or "").encode("utf-8")).hexdigest()
    return digest[:length]


def mask_cpf(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) != 11:
        return "***"
    return f"***.{digits[3:6]}.{digits[6:9]}-**"


def mask_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) < 4:
        return "***"
    return f"***{digits[-4:]}"
