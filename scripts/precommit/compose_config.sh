#!/usr/bin/env bash
set -euo pipefail

# If docker is not available (common in WSL), skip gracefully.
if ! command -v docker >/dev/null 2>&1; then
  echo "ℹ️  docker not found - skipping docker compose validation"
  exit 0
fi

# Prefer 'docker compose' (v2). Fallback to legacy 'docker-compose' if installed.
if docker compose version >/dev/null 2>&1; then
  COMPOSE=("docker" "compose")
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=("docker-compose")
else
  echo "ℹ️  docker found but compose plugin not available - skipping compose validation"
  exit 0
fi

validate() {
  local file="$1"
  if [ -f "$file" ]; then
    echo "✅ Validating $file"
    "${COMPOSE[@]}" -f "$file" config >/dev/null
  fi
}

validate "docker-compose.yml"
validate "monitoring/compose/docker-compose.yml"
