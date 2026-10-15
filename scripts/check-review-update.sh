#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
# Separate, unique project: never touch the running demo database or its volume.
check_project="missioncontrol-review-check-$(date +%s)-${RANDOM}"
cleanup() {
  docker compose -p "$check_project" -f compose.yaml -f compose.test.yaml down -v --remove-orphans
}
trap cleanup EXIT
printf 'Running PostgreSQL checks in disposable project %s\n' "$check_project"
docker compose -p "$check_project" -f compose.yaml -f compose.test.yaml run --build --rm tests
printf '%s\n' 'Review-update tests passed. The main demo database was not changed.'
