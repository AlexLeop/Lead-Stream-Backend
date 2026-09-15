#!/usr/bin/env sh
set -eu

if [ -x ".venv/bin/python" ]; then
  leadstream_python=".venv/bin/python"
else
  leadstream_python="python"
fi

printf '\n==> Ruff\n'
"$leadstream_python" -m ruff check .

printf '\n==> Mypy\n'
"$leadstream_python" -m mypy src

printf '\n==> Migrations pendentes\n'
DJANGO_SETTINGS_MODULE=config.settings.test \
  "$leadstream_python" manage.py makemigrations --check --dry-run

printf '\n==> Configuração de produção\n'
DJANGO_SETTINGS_MODULE=config.settings.production \
DJANGO_SECRET_KEY=quality-check-only-this-is-not-a-production-secret-change-me \
DJANGO_ALLOWED_HOSTS=quality.invalid \
DATABASE_URL=postgresql://quality:quality@localhost:5432/quality \
CELERY_BROKER_URL=amqp://quality:quality@localhost:5672// \
REDIS_URL=redis://localhost:6379/15 \
DJANGO_SECURE_SSL_REDIRECT=true \
DATA_HASH_KEY=quality-check-only-data-hash-key \
DATA_HASH_KEY_VERSION=v1 \
FIELD_ENCRYPTION_KEYS=LN9efNDmugNtrk_5pkcuBrkDKU3LrWZgHEZVWlUzvDI= \
  "$leadstream_python" manage.py check --deploy --fail-level WARNING

printf '\n==> Testes\n'
DJANGO_SETTINGS_MODULE=config.settings.test "$leadstream_python" -m pytest -q

printf '\nTodos os gates de qualidade passaram.\n'
