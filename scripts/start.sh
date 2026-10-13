#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export DEBUG="${DEBUG:-1}"
if [[ "$DEBUG" != 1 ]]; then
  exec .venv/bin/gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers "${WEB_WORKERS:-2}" --timeout 60
fi
exec .venv/bin/python manage.py runserver 127.0.0.1:8000
