#!/usr/bin/env bash

# Manifests the deployment of the monitoring stack using Docker Compose.
# Intended to be called with sudo to ensure proper permissions after 'git pull'.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$REPO_ROOT/monitoring/compose/docker-compose.yml}"
SECRETS_FILE="${SECRETS_FILE:-/etc/raspberry-pi-homelab/secrets.env}"
INIT_SCRIPT="${INIT_SCRIPT:-$REPO_ROOT/monitoring/compose/init-permissions.sh}"

# toggles with defaults
RUN_INIT_PERMISSIONS="${RUN_INIT_PERMISSIONS:-auto}"   # auto|always|never
PULL_IMAGES="${PULL_IMAGES:-1}"                        # 1|0
RUN_TESTS="${RUN_TESTS:-1}"                            # 1|0

# logging and error handling functions
log(){ echo "[$(date -Is)] $*"; }
die(){ echo "ERROR: $*" >&2; exit 2; }

# Ensure the script is run as root
require_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    die "Please run with sudo: sudo ./deploy.sh"
  fi
}

# Check prerequisites: docker, docker compose, compose file
check_prereqs() {
  command -v docker >/dev/null 2>&1 || die "docker not found"
  docker compose version >/dev/null 2>&1 || die "docker compose plugin not available"
  [[ -f "$COMPOSE_FILE" ]] || die "Compose file missing: $COMPOSE_FILE"
}

# Load secrets from the specified file
load_secrets() {
  [[ -f "$SECRETS_FILE" ]] || die "Secrets file not found: $SECRETS_FILE"

  set -a
  # shellcheck disable=SC1090
  source "$SECRETS_FILE"
  set +a

  : "${GRAFANA_ADMIN_USER:?Missing GRAFANA_ADMIN_USER in $SECRETS_FILE}"
  : "${GRAFANA_ADMIN_PASSWORD:?Missing GRAFANA_ADMIN_PASSWORD in $SECRETS_FILE}"
}

compose() {
  docker compose -f "$COMPOSE_FILE" "$@"
}

maybe_init_permissions() {
  [[ -f "$INIT_SCRIPT" ]] || { log "init-permissions: not found, skipping ($INIT_SCRIPT)"; return 0; }

  case "$RUN_INIT_PERMISSIONS" in
    never)  log "init-permissions: skipped (RUN_INIT_PERMISSIONS=never)"; return 0 ;;
    always) ;;
    auto)
      # If something is already running, skip by default (avoid heavy recursive chown)
      if compose ps --status running 2>/dev/null | grep -q .; then
        log "init-permissions: skipped (stack running; RUN_INIT_PERMISSIONS=auto)"
        return 0
      fi
      ;;
    *) die "Invalid RUN_INIT_PERMISSIONS=$RUN_INIT_PERMISSIONS (use auto|always|never)" ;;
  esac

  log "init-permissions: running $INIT_SCRIPT"
  bash "$INIT_SCRIPT"
  log "init-permissions: done"
}

main() {
  require_root
  cd "$REPO_ROOT"
  check_prereqs
  load_secrets

  maybe_init_permissions

  if [[ "$PULL_IMAGES" == "1" ]]; then
    log "compose: pull"
    compose pull
  else
    log "compose: pull skipped (PULL_IMAGES=0)"
  fi

  log "compose: up -d"
  compose up -d

  log "compose: ps"
  compose ps

  if [[ "$RUN_TESTS" == "1" ]]; then
    log "tests: make postdeploy"
    (cd "$REPO_ROOT" && make postdeploy)
    log "tests: passed"
  else
    log "tests: skipped (RUN_TESTS=0)"
  fi

  log "deploy: done"
}

main "$@"
