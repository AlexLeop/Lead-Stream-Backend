#!/bin/sh
set -eu

python manage.py migrate --noinput
python manage.py setup_security_admin
python manage.py check --deploy
