# syntax=docker/dockerfile:1.7

FROM ghcr.io/astral-sh/uv:0.12.12 AS uv

FROM python:3.13-slim-bookworm AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app
COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.13-slim-bookworm AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production

RUN groupadd --gid 10001 leadstream \
    && useradd --uid 10001 --gid leadstream --no-create-home --shell /usr/sbin/nologin leadstream

WORKDIR /app
COPY --from=builder --chown=10001:10001 /app/.venv /app/.venv
COPY --chown=10001:10001 manage.py ./manage.py
COPY --chown=10001:10001 src ./src
COPY --chown=10001:10001 scripts ./scripts
COPY --chown=10001:10001 templates ./templates

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD ["python", "scripts/healthcheck.py"]

CMD ["gunicorn", "config.asgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--worker-class", "uvicorn_worker.UvicornWorker", "--timeout", "60", "--graceful-timeout", "30", "--error-logfile", "-"]
