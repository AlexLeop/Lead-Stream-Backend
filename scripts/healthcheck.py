from __future__ import annotations

import os
import sys
import urllib.request


def is_live() -> bool:
    # 1. Verifica servidor web HTTP (porta 8000) caso seja o container da API
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/health/live", timeout=2) as resp:
            if resp.status == 200:
                return True
    except Exception:
        pass

    # 2. Se não houver HTTP, verifica processo Celery ativo (para container worker)
    try:
        for entry in os.listdir("/proc"):
            if entry.isdigit():
                try:
                    with open(f"/proc/{entry}/cmdline", "rb") as f:
                        cmdline = f.read()
                        if b"celery" in cmdline:
                            return True
                except OSError:
                    continue
    except Exception:
        pass

    return False


if __name__ == "__main__":
    sys.exit(0 if is_live() else 1)
