#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "$(dirname "$0")/.."
folder=".backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$folder"
# Pause writes while dumping DB and uploaded files to keep them consistent.
docker compose stop app
trap 'docker compose start app >/dev/null' EXIT
docker compose exec -T db pg_dump -U dar -d dar -Fc > "$folder/database.dump"
docker compose run --rm --no-deps app tar -czf - -C /app/media . > "$folder/media.tar.gz"
# Verify archive structures before reporting success.
docker compose exec -T db pg_restore --list < "$folder/database.dump" >/dev/null
tar -tzf "$folder/media.tar.gz" >/dev/null
echo "Backup stored in $folder. Keep a protected copy outside this server."
