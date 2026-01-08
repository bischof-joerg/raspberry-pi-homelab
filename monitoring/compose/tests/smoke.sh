#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Load env file (needed for curl auth), but keep it safe:
# - only reads KEY=VALUE lines
# - ignores comments/blank lines
if [[ -f .env ]]; then
  while IFS='=' read -r key value; do
    [[ -z "${key}" || "${key}" =~ ^\s*# ]] && continue
    # strip surrounding quotes
    value="${value%\"}"; value="${value#\"}"
    value="${value%\'}"; value="${value#\'}"
    export "${key}=${value}"
  done < <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' .env)
fi

: "${GRAFANA_ADMIN_USER:?Missing GRAFANA_ADMIN_USER (set in .env)}"
: "${GRAFANA_ADMIN_PASSWORD:?Missing GRAFANA_ADMIN_PASSWORD (set in .env)}"

echo "== compose ps =="
docker compose ps

echo "== grafana =="
curl -fsS -I http://127.0.0.1:3000/login | head -n 5
curl -fsS -u "${GRAFANA_ADMIN_USER}:${GRAFANA_ADMIN_PASSWORD}" \
  http://127.0.0.1:3000/api/health

echo "== prometheus =="
curl -fsS http://127.0.0.1:9090/-/ready
curl -fsS 'http://127.0.0.1:9090/api/v1/query?query=up' > /dev/null

echo "== alertmanager =="
curl -fsS http://127.0.0.1:9093/-/ready

echo "OK"
