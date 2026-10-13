#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Run only on your chosen server after configuring .env and domain DNS.
if [[ ! -f .env ]]; then echo 'Generate .env with python3 scripts/init-production-env.py first'; exit 1; fi
docker compose build app
docker compose up -d db
docker compose run --rm app python manage.py migrate --noinput
docker compose run --rm app python manage.py createcachetable
docker compose run --rm app python manage.py bootstrap_store
docker compose run --rm app python manage.py collectstatic --noinput
docker compose run --rm app python manage.py check --deploy --fail-level WARNING
docker compose --profile public up -d
