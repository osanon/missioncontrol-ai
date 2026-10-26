#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if ! command -v docker >/dev/null 2>&1; then
  printf '%s\n' 'Docker is missing. In Codespaces, run Codespaces: Rebuild Container to apply .devcontainer/devcontainer.json.' >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  printf '%s\n' 'Docker is not ready. Wait for the Codespace to finish starting, then retry. If it persists, rebuild the container.' >&2
  exit 1
fi
docker compose version >/dev/null
if [[ ! -f .env ]]; then
  python3 scripts/configure.py
fi
docker compose up --build -d
docker compose ps -a
printf '%s\n' 'The stack has been started. Check backend health in the status output.' 'In Codespaces, open Ports → 8080 → Open in Browser; keep visibility Private.' 'Open the workspace .env file for APP_TOKEN; use your personal token from REVIEWERS only for review decisions.' 'Diagnostics: docker compose logs --tail=100 db seed backend frontend'
