#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [[ ! -f .env ]]; then
  python3 scripts/configure.py
fi
printf '%s\n' 'MissionControl cloud workspace is configured.' 'Start the app: bash scripts/cloud-start.sh' 'Keep forwarded port 8080 Private in the Ports panel.'
