#!/usr/bin/env bash
# One-time setup on a fresh Vultr Cloud Compute instance (Ubuntu 24.04), run as root from the project directory:
#   bash scripts/vultr-setup.sh
# Optional environment: DOMAIN (your own domain; default <server-ip>.sslip.io), PUBLIC_DEMO (default true),
# FIRST_REVIEWER (default reviewer). Safe to re-run: it never overwrites existing .env values.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [[ $EUID -ne 0 ]]; then
  echo 'Run as root (for example: sudo bash scripts/vultr-setup.sh).' >&2
  exit 1
fi

echo '1/4 Installing Docker and the firewall'
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q docker.io docker-compose-v2 ufw python3 curl
systemctl enable --now docker

echo '2/4 Opening only SSH, HTTP and HTTPS'
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo '3/4 Configuring .env'
if [[ ! -f .env ]]; then
  python3 scripts/configure.py --first-reviewer "${FIRST_REVIEWER:-reviewer}"
fi
set_default() {
  # Append KEY=value only when KEY is not already set in .env.
  grep -q "^$1=" .env || printf '%s=%s\n' "$1" "$2" >> .env
}
if [[ -z "${DOMAIN:-}" ]]; then
  ip="$(curl -fsS -m 5 http://169.254.169.254/v1/interfaces/0/ipv4/address 2>/dev/null || hostname -I | awk '{print $1}')"
  DOMAIN="${ip//./-}.sslip.io"
fi
set_default DOMAIN "$DOMAIN"
set_default PUBLIC_DEMO "${PUBLIC_DEMO:-true}"
set_default AI_DAILY_TOKEN_BUDGET 200000
chmod 600 .env

echo '4/4 Building and starting MissionControl'
docker compose -f compose.yaml -f compose.vultr.yaml up -d --build
docker compose -f compose.yaml -f compose.vultr.yaml ps -a

domain="$(grep '^DOMAIN=' .env | cut -d= -f2-)"
printf '\n%s\n' "MissionControl is starting at https://${domain}" \
  'The first HTTPS certificate can take a minute. Logs: docker compose -f compose.yaml -f compose.vultr.yaml logs -f caddy backend' \
  'Analyst and reviewer tokens are in .env (APP_TOKEN, REVIEWERS). Keep .env private.'
