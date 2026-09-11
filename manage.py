#!/usr/bin/env python
from __future__ import annotations

import os
import sys
from pathlib import Path


def _load_dotenv() -> None:
    env_file = Path(__file__).resolve().parent / ".env"
    if env_file.is_file():
        try:
            with env_file.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    if (value.startswith('"') and value.endswith('"')) or (
                        value.startswith("'") and value.endswith("'")
                    ):
                        value = value[1:-1]
                    if key and key not in os.environ:
                        os.environ[key] = value
        except OSError:
            pass


def main() -> None:
    _load_dotenv()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django não está instalado. Instale as dependências do projeto antes de continuar."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
