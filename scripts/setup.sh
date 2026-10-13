#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export DEBUG="${DEBUG:-1}"
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-/tmp/dar-khashab-pip-cache}"
python3 -m venv .venv
.venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py createcachetable
.venv/bin/python manage.py bootstrap_store
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py check
