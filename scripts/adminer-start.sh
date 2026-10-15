#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if ! docker compose exec -T db pg_isready -q -U mc_admin -d missioncontrol >/dev/null 2>&1; then
  printf '%s\n' 'The MissionControl database is not ready. Run bash scripts/cloud-start.sh first, then retry.' >&2
  exit 1
fi
docker compose --profile database-tools up -d --no-deps adminer
docker compose --profile database-tools ps adminer
printf '%s\n' \
  'Open Codespaces Ports, add 8081 if needed, confirm Private visibility, then Open in Browser.' \
  'Adminer login: System PostgreSQL; Server db; Username mc_admin; Database missioncontrol.' \
  'Use POSTGRES_PASSWORD from your existing .env as the database password.' \
  'This is separate from APP_TOKEN and REVIEW_TOKEN. Keep the forwarded-port protocol HTTP.' \
  'Stop the editor with: docker compose --profile database-tools stop adminer'
