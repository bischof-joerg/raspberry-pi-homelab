#!/usr/bin/env bash
#
# Deploy monitoring stack (GitOps) using Docker Compose.
# Intended to be executed on the Pi via sudo after `git pull`.
#
# Key principles:
# - No secrets in repo
# - Host-only secrets/config via /etc/raspberry-pi-homelab/monitoring.env
# - Compose file under stacks/monitoring/compose
#
# Notes:
# - docker compose auto-loads ".env" from the working directory. We refuse repo-root .env.
# - GHCR login is OPTIONAL. If GHCR_USER/GHCR_PAT are absent and images are public, we proceed.
#
# Migration note (Prometheus removal):
# - The monitoring stack is migrating to VictoriaMetrics + vmagent as the primary ingestion/storage path.
# - Postdeploy tests are being updated to stop relying on Prometheus.
# - If Prometheus is still present in compose, this script will warn (or fail if PROMETHEUS_REMOVAL_ENFORCE=1).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PROMETHEUS_REMOVED="${PROMETHEUS_REMOVED:-1}"
export PROMETHEUS_REMOVED

# Prefer new target layout; allow override for transitions
COMPOSE_FILE="${COMPOSE_FILE:-$REPO_ROOT/stacks/monitoring/compose/docker-compose.yml}"
if [[ ! -f "$COMPOSE_FILE" ]]; then
  # fallback for legacy layout
  COMPOSE_FILE="$REPO_ROOT/monitoring/compose/docker-compose.yml"
fi

# Host-only config+secrets for the monitoring stack (root-only, not in git)
SECRETS_FILE="${SECRETS_FILE:-/etc/raspberry-pi-homelab/monitoring.env}"

# Init script path
INIT_SCRIPT="${INIT_SCRIPT:-$REPO_ROOT/stacks/monitoring/compose/init-permissions.sh}"
if [[ ! -f "$INIT_SCRIPT" ]]; then
  INIT_SCRIPT="$REPO_ROOT/monitoring/compose/init-permissions.sh"
fi

# toggles with defaults
RUN_INIT_PERMISSIONS="${RUN_INIT_PERMISSIONS:-auto}"     # auto|always|never
PULL_IMAGES="${PULL_IMAGES:-1}"                          # 1|0
RUN_TESTS="${RUN_TESTS:-1}"                              # 1|0

# repo ownership handling
FIX_REPO_OWNERSHIP="${FIX_REPO_OWNERSHIP:-auto}"         # auto|always|never
REPO_OWNER_USER="${REPO_OWNER_USER:-admin}"
REPO_OWNER_GROUP="${REPO_OWNER_GROUP:-admin}"

# Prometheus removal preparation
PROMETHEUS_REMOVAL_ENFORCE="${PROMETHEUS_REMOVAL_ENFORCE:-0}"  # 1 => fail deploy if prometheus is still referenced

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
  if [[ -e "$REPO_ROOT/.env" ]]; then
    die "Refusing repo-root .env ($REPO_ROOT/.env). Remove it and use $SECRETS_FILE instead."
  fi
}

validate_secrets_file() {
  [[ -e "$SECRETS_FILE" ]] || die "Stack env file not found: $SECRETS_FILE"
  [[ -r "$SECRETS_FILE" ]] || die "Stack env file not readable: $SECRETS_FILE"

  local owner group mode
  owner="$(stat -c '%U' "$SECRETS_FILE" 2>/dev/null || true)"
  group="$(stat -c '%G' "$SECRETS_FILE" 2>/dev/null || true)"
  mode="$(stat -c '%a' "$SECRETS_FILE" 2>/dev/null || true)"

  [[ "$owner" == "root" ]] || die "Env file must be owned by root (found owner=$owner): $SECRETS_FILE"
  [[ "$group" == "root" ]] || die "Env file should be group root (found group=$group): $SECRETS_FILE"
  [[ "$mode" == "600" ]] || die "Env file must have mode 600 (found $mode): $SECRETS_FILE"
}

compose() {
  # Always drive compose via host-only env file to keep repo hermetic.
  docker compose --env-file "$SECRETS_FILE" -f "$COMPOSE_FILE" "$@"
}

compute_monitoring_config_hash() {
  local files=(
    "$REPO_ROOT/stacks/monitoring/vmagent/vmagent.yml"
    "$REPO_ROOT/stacks/monitoring/vmalert/vmalert.yml"
    "$REPO_ROOT/stacks/monitoring/alertmanager/alertmanager.yml"
    "$REPO_ROOT/stacks/monitoring/victoriametrics/victoriametrics.yml"
  )

  local existing=()
  local f
  for f in "${files[@]}"; do
    [[ -f "$f" ]] && existing+=("$f")
  done

  [[ ${#existing[@]} -gt 0 ]] || { echo "no-config-files"; return 0; }

  sha256sum "${existing[@]}" | sha256sum | awk '{print $1}'
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
    log "repo-ownership: forcing ownership to ${REPO_OWNER_USER}:${REPO_OWNER_GROUP}"
    chown -R --no-dereference "${REPO_OWNER_USER}:${REPO_OWNER_GROUP}" "$REPO_ROOT"
    return 0
  fi

  if repo_ownership_mismatch_exists; then
    if [[ "$FIX_REPO_OWNERSHIP" == "never" ]]; then
      die "repo-ownership: mismatch detected; refusing to fix (FIX_REPO_OWNERSHIP=never)"
    fi
    log "repo-ownership: mismatch detected; fixing to ${REPO_OWNER_USER}:${REPO_OWNER_GROUP}"
    chown -R --no-dereference "${REPO_OWNER_USER}:${REPO_OWNER_GROUP}" "$REPO_ROOT"
    log "repo-ownership: fixed"
  else
    log "repo-ownership: OK (${REPO_OWNER_USER}:${REPO_OWNER_GROUP})"
  fi
}

init_permissions_needed() {
  [[ -f "$INIT_SCRIPT" ]] || return 1
  # init-permissions.sh --check returns:
  # 0 = OK, 1 = needs changes
  if bash "$INIT_SCRIPT" --check; then
    return 1
  fi
  return 0
}

maybe_init_permissions() {
  [[ -f "$INIT_SCRIPT" ]] || { log "init-permissions: not found, skipping ($INIT_SCRIPT)"; return 0; }

  case "$RUN_INIT_PERMISSIONS" in
    never)
      log "init-permissions: skipped (RUN_INIT_PERMISSIONS=never)"
      return 0
      ;;
    always)
      log "init-permissions: running (RUN_INIT_PERMISSIONS=always) $INIT_SCRIPT"
      bash "$INIT_SCRIPT"
      log "init-permissions: done"
      return 0
      ;;
    auto)
      if init_permissions_needed; then
        log "init-permissions: running (needed) $INIT_SCRIPT"
        bash "$INIT_SCRIPT"
        log "init-permissions: done"
      else
        log "init-permissions: skipped (already correct; RUN_INIT_PERMISSIONS=auto)"
      fi
      ;;
    *)
      die "Invalid RUN_INIT_PERMISSIONS=$RUN_INIT_PERMISSIONS (use auto|always|never)"
      ;;
  esac
}

needs_ghcr_auth() {
  grep -Eq 'image:\s*ghcr\.io/' "$COMPOSE_FILE"
}

compose_references_prometheus() {
  grep -Eq 'image:\s*(prom/prometheus|quay\.io/prometheus/prometheus|ghcr\.io/.*/prometheus)' "$COMPOSE_FILE" || \
  grep -Eq 'service:\s*prometheus\b' "$COMPOSE_FILE"
}

with_ephemeral_docker_config() {
  local docker_cfg_tmp=""
  docker_cfg_tmp="$(mktemp -d)"
  chmod 700 "$docker_cfg_tmp"
  trap 'rm -rf "${docker_cfg_tmp:-}"' RETURN
  export DOCKER_CONFIG="$docker_cfg_tmp"

  if needs_ghcr_auth; then
    validate_secrets_file
    # shellcheck disable=SC1090
    source "$SECRETS_FILE"

    if [[ -n "${GHCR_USER:-}" && -n "${GHCR_PAT:-}" ]]; then
      log "ghcr: logging in (ephemeral DOCKER_CONFIG)"
      if ! echo "$GHCR_PAT" | docker login ghcr.io -u "$GHCR_USER" --password-stdin >/dev/null 2>&1; then
        die "ghcr: login failed (check GHCR_USER/GHCR_PAT in $SECRETS_FILE)"
      fi
      log "ghcr: login succeeded"
      unset GHCR_PAT || true
      unset GHCR_USER || true
    else
      log "ghcr: compose uses ghcr.io but GHCR_USER/GHCR_PAT not set; proceeding without login (public images expected)"
    fi
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
  (
    cd "$REPO_ROOT" && \
    POSTDEPLOY_ON_TARGET=1 \
    PROMETHEUS_REMOVED="${PROMETHEUS_REMOVED}" \
    make postdeploy
  )
  log "tests: passed"
}

main() {
  require_root
  sanity_checks
  cd "$REPO_ROOT"

  fix_repo_ownership_if_needed
  refuse_repo_root_env
  check_prereqs
  validate_secrets_file

  maybe_init_permissions

  # Compute once in parent shell so it's deterministic and shellcheck-clean.
  export MONITORING_CONFIG_HASH
  MONITORING_CONFIG_HASH="$(compute_monitoring_config_hash)"
  log "config-hash: MONITORING_CONFIG_HASH=$MONITORING_CONFIG_HASH"

  # Make sure these are available to the child shell when using bash -c
  export SECRETS_FILE COMPOSE_FILE

  if [[ "$PULL_IMAGES" == "1" ]]; then
    log "compose: pull + up (single ghcr session)"
    with_ephemeral_docker_config bash -euo pipefail -c "
      docker compose --env-file \"\$SECRETS_FILE\" -f \"\$COMPOSE_FILE\" pull
      docker compose --env-file \"\$SECRETS_FILE\" -f \"\$COMPOSE_FILE\" up -d
    "
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
