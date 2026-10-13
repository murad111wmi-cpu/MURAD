#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m pip install --disable-pip-version-check -r requirements.txt
python manage.py migrate --noinput
python manage.py createcachetable
python manage.py bootstrap_store
python manage.py collectstatic --noinput
python manage.py check --deploy --fail-level WARNING
