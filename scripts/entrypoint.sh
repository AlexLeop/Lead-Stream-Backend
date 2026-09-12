#!/bin/sh
set -e

echo "==> [LeadStream] Executando migrações do banco de dados..."
python manage.py migrate --noinput

echo "==> [LeadStream] Garantindo Super Admin provisionado..."
python manage.py setup_security_admin

echo "==> [LeadStream] Iniciando servidor..."
exec "$@"
