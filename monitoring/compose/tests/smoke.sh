#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

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
