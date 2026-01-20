#!/usr/bin/env bash
#
# Manifests the deployment of the monitoring stack using Docker Compose.
# Intended to be called with sudo to ensure proper permissions after 'git pull'.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$REPO_ROOT/monitoring/compose/docker-compose.yml}"

# Secrets are NOT stored in the repo. Default location on the Pi:
SECRETS_FILE="${SECRETS_FILE:-/etc/raspberry-pi-homelab/.env}"

# Non-secret compose env file (e.g., Grafana provisioning toggles); optional.
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-$REPO_ROOT/monitoring/compose/.env}"

INIT_SCRIPT="${INIT_SCRIPT:-$REPO_ROOT/monitoring/compose/init-permissions.sh}"

# toggles with defaults
RUN_INIT_PERMISSIONS="${RUN_INIT_PERMISSIONS:-auto}"     # auto|always|never
PULL_IMAGES="${PULL_IMAGES:-1}"                          # 1|0
RUN_TESTS="${RUN_TESTS:-1}"                              # 1|0

# repo ownership handling
FIX_REPO_OWNERSHIP="${FIX_REPO_OWNERSHIP:-auto}"         # auto|always|never
REPO_OWNER_USER="${REPO_OWNER_USER:-admin}"
REPO_OWNER_GROUP="${REPO_OWNER_GROUP:-admin}"

# logging and error handling functions
log(){ echo "[$(date -Is)] $*"; }
die(){ echo "ERROR: $*" >&2; exit 2; }

on_err() {
  local exit_code=$?
  local line_no=${1:-"?"}
  echo "ERROR: deploy.sh failed (exit=${exit_code}) at line ${line_no}." >&2
  echo "Hint: re-run with 'bash -x ./deploy.sh' for detailed tracing." >&2
  exit "$exit_code"
}
trap 'on_err $LINENO' ERR

require_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    die "Please run with sudo: sudo ./deploy.sh"
  fi
}

sanity_checks() {
  [[ -n "${REPO_ROOT}" ]] || die "REPO_ROOT is empty (unexpected)"
  [[ "${REPO_ROOT}" != "/" ]] || die "REPO_ROOT resolved to '/', refusing to continue"
  [[ -d "${REPO_ROOT}" ]] || die "REPO_ROOT is not a directory: ${REPO_ROOT}"
  [[ -f "${REPO_ROOT}/deploy.sh" ]] || die "Expected deploy.sh in REPO_ROOT, got: ${REPO_ROOT}"
}

check_prereqs() {
  command -v docker >/dev/null 2>&1 || die "docker not found"
  docker compose version >/dev/null 2>&1 || die "docker compose plugin not available"
  [[ -f "$COMPOSE_FILE" ]] || die "Compose file missing: $COMPOSE_FILE"
}

refuse_repo_root_env() {
  # docker compose auto-loads .env from the working directory.
  # If this file is root-owned/0600, 'admin' cannot run 'docker compose ps' => breaks ops.
  if [[ -e "$REPO_ROOT/.env" ]]; then
    die "Refusing to use repo-root .env ($REPO_ROOT/.env). Remove it and use $SECRETS_FILE instead."
  fi
}

load_secrets() {
  [[ -r "$SECRETS_FILE" ]] || die "Secrets file not readable: $SECRETS_FILE"
  set -a
  # shellcheck disable=SC1090
  source "$SECRETS_FILE"
  set +a
}

compose() {
  if [[ -f "$COMPOSE_ENV_FILE" ]]; then
    docker compose --env-file "$COMPOSE_ENV_FILE" -f "$COMPOSE_FILE" "$@"
  else
    docker compose -f "$COMPOSE_FILE" "$@"
  fi
}

repo_ownership_mismatch_exists() {
  find "$REPO_ROOT" -xdev \( ! -user "$REPO_OWNER_USER" -o ! -group "$REPO_OWNER_GROUP" \) -print -quit 2>/dev/null | grep -q .
}

fix_repo_ownership_if_needed() {
  case "$FIX_REPO_OWNERSHIP" in
    never|always|auto) ;;
    *) die "Invalid FIX_REPO_OWNERSHIP=$FIX_REPO_OWNERSHIP (use auto|always|never)" ;;
  esac

  id -u "$REPO_OWNER_USER" >/dev/null 2>&1 || die "User not found: REPO_OWNER_USER=$REPO_OWNER_USER"
  getent group "$REPO_OWNER_GROUP" >/dev/null 2>&1 || die "Group not found: REPO_OWNER_GROUP=$REPO_OWNER_GROUP"

  if [[ "$FIX_REPO_OWNERSHIP" == "always" ]]; then
    log "repo-ownership: forcing ownership to ${REPO_OWNER_USER}:${REPO_OWNER_GROUP} (FIX_REPO_OWNERSHIP=always)"
    chown -R --no-dereference "${REPO_OWNER_USER}:${REPO_OWNER_GROUP}" "$REPO_ROOT"
    return 0
  fi

  if repo_ownership_mismatch_exists; then
    if [[ "$FIX_REPO_OWNERSHIP" == "never" ]]; then
      die "repo-ownership: mismatch detected in $REPO_ROOT; refusing to fix (FIX_REPO_OWNERSHIP=never)"
    fi
    log "repo-ownership: mismatch detected; fixing ownership to ${REPO_OWNER_USER}:${REPO_OWNER_GROUP} (FIX_REPO_OWNERSHIP=auto)"
    chown -R --no-dereference "${REPO_OWNER_USER}:${REPO_OWNER_GROUP}" "$REPO_ROOT"
    log "repo-ownership: fixed"
  else
    log "repo-ownership: OK (${REPO_OWNER_USER}:${REPO_OWNER_GROUP})"
  fi
}

maybe_init_permissions() {
  [[ -f "$INIT_SCRIPT" ]] || { log "init-permissions: not found, skipping ($INIT_SCRIPT)"; return 0; }

  case "$RUN_INIT_PERMISSIONS" in
    never)  log "init-permissions: skipped (RUN_INIT_PERMISSIONS=never)"; return 0 ;;
    always) ;;
    auto)
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

needs_ghcr_auth() {
  # If compose file references ghcr.io images, assume auth might be needed.
  grep -qE '^\s*image:\s*ghcr\.io/' "$COMPOSE_FILE"
}

with_ephemeral_docker_config() {
  # Creates an ephemeral DOCKER_CONFIG so docker login does NOT write to /root/.docker/config.json
  local docker_cfg_tmp=""
  docker_cfg_tmp="$(mktemp -d)"
  chmod 700 "$docker_cfg_tmp"

  # Ensure cleanup even if something fails
  trap 'rm -rf "${docker_cfg_tmp:-}"' RETURN

  export DOCKER_CONFIG="$docker_cfg_tmp"

  if needs_ghcr_auth; then
    : "${GHCR_USER:?Missing GHCR_USER in $SECRETS_FILE}"
    : "${GHCR_PAT:?Missing GHCR_PAT in $SECRETS_FILE}"

    log "ghcr: logging in (ephemeral DOCKER_CONFIG)"
    # Suppress the credential-store warning; still fail hard on login errors.
    if ! echo "$GHCR_PAT" | docker login ghcr.io -u "$GHCR_USER" --password-stdin >/dev/null 2>&1; then
      die "ghcr: login failed"
    fi
    log "ghcr: login succeeded"
  else
    log "ghcr: not used by compose; skipping login"
  fi

  "$@"
}

run_postdeploy_tests() {
  if [[ "$RUN_TESTS" != "1" ]]; then
    log "tests: skipped (RUN_TESTS=0)"
    return 0
  fi

  command -v make >/dev/null 2>&1 || die "tests requested but 'make' not found"
  [[ -f "$REPO_ROOT/Makefile" ]] || die "tests requested but Makefile not found in repo root"

  log "tests: make postdeploy"
  (cd "$REPO_ROOT" && make postdeploy)
  log "tests: passed"
}

main() {
  require_root
  sanity_checks
  cd "$REPO_ROOT"

  # Ensure the repo remains operable by the intended non-root user
  fix_repo_ownership_if_needed

  # Enforce GitOps discipline: no secrets in repo root .env
  refuse_repo_root_env

  check_prereqs
  load_secrets

  maybe_init_permissions

  if [[ "$PULL_IMAGES" == "1" ]]; then
    log "compose: pull + up (single ghcr session)"
    with_ephemeral_docker_config bash -euo pipefail -c '
      if [[ -f "'"$COMPOSE_ENV_FILE"'" ]]; then
        docker compose --env-file "'"$COMPOSE_ENV_FILE"'" -f "'"$COMPOSE_FILE"'" pull
        docker compose --env-file "'"$COMPOSE_ENV_FILE"'" -f "'"$COMPOSE_FILE"'" up -d
      else
        docker compose -f "'"$COMPOSE_FILE"'" pull
        docker compose -f "'"$COMPOSE_FILE"'" up -d
      fi
    '

  else
    log "compose: pull skipped (PULL_IMAGES=0)"
    compose up -d
  fi

  log "compose: ps"
  compose ps

  run_postdeploy_tests

  log "deploy: done"
}

main "$@"
