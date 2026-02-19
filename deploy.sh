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
BOOTSTRAP_NETWORKS="${BOOTSTRAP_NETWORKS:-1}"            # 1|0

# Docker daemon.json GitOps enforcement
ENSURE_DOCKER_DAEMON_JSON="${ENSURE_DOCKER_DAEMON_JSON:-1}"  # 1|0
DOCKER_DAEMON_SCRIPT="${DOCKER_DAEMON_SCRIPT:-$REPO_ROOT/scripts/host/ensure-docker-daemon-json.sh}"

# repo ownership handling
FIX_REPO_OWNERSHIP="${FIX_REPO_OWNERSHIP:-auto}"         # auto|always|never
REPO_OWNER_USER="${REPO_OWNER_USER:-admin}"
REPO_OWNER_GROUP="${REPO_OWNER_GROUP:-admin}"

# Prometheus removal preparation
PROMETHEUS_REMOVAL_ENFORCE="${PROMETHEUS_REMOVAL_ENFORCE:-0}"

# toggles/variables to verify journald read access (for Vector host logs ingestion)
ENSURE_JOURNALD_READ="${ENSURE_JOURNALD_READ:-1}"
JOURNALD_SCRIPT="${JOURNALD_SCRIPT:-$REPO_ROOT/scripts/ensure-journald-read.sh}"
JOURNALD_TARGET_USER="${JOURNALD_TARGET_USER:-admin}"


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

ensure_docker_daemon_json() {
  [[ "$ENSURE_DOCKER_DAEMON_JSON" == "1" ]] || {
    log "docker-daemon: skipped (ENSURE_DOCKER_DAEMON_JSON=0)"
    return 0
  }
  [[ -x "$DOCKER_DAEMON_SCRIPT" ]] || die "docker-daemon script not executable: $DOCKER_DAEMON_SCRIPT"
  log "docker-daemon: ensure"
  "$DOCKER_DAEMON_SCRIPT" apply
  log "docker-daemon: ensure done"
}

refuse_repo_root_env() {
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
  docker compose --env-file "$SECRETS_FILE" -f "$COMPOSE_FILE" "$@"
}

bootstrap_networks() {
  [[ "$BOOTSTRAP_NETWORKS" == "1" ]] || {
    log "networks: bootstrap skipped (BOOTSTRAP_NETWORKS=0)"
    return 0
  }

  local script="$REPO_ROOT/scripts/bootstrap-networks.sh"
  [[ -x "$script" ]] || die "bootstrap script not executable: $script"

  log "networks: bootstrap"
  "$script"
  log "networks: bootstrap done"
}

ensure_journald_read_access() {
  [[ "$ENSURE_JOURNALD_READ" == "1" ]] || {
    log "journald: ensure read access skipped (ENSURE_JOURNALD_READ=0)"
    return 0
  }

  [[ -x "$JOURNALD_SCRIPT" ]] || die "journald script not executable: $JOURNALD_SCRIPT"

  log "journald: ensuring read access for TARGET_USER=$JOURNALD_TARGET_USER"
  local out
  out="$(TARGET_USER="$JOURNALD_TARGET_USER" "$JOURNALD_SCRIPT" apply)"
  log "journald: $out"

  if [[ "$out" =~ SYSTEMD_JOURNAL_GID=([0-9]+) ]]; then
    export SYSTEMD_JOURNAL_GID="${BASH_REMATCH[1]}"
    log "journald: exported SYSTEMD_JOURNAL_GID=$SYSTEMD_JOURNAL_GID"
  else
    die "journald: failed to determine SYSTEMD_JOURNAL_GID"
  fi

  if [[ -S /var/run/docker.sock ]]; then
    export DOCKER_GID
    DOCKER_GID="$(stat -c '%g' /var/run/docker.sock)"
    log "docker-sock: exported DOCKER_GID=$DOCKER_GID"
  else
    die "docker-sock: /var/run/docker.sock not found"
  fi

}


compute_monitoring_config_hash() {
  local files=(
    "$REPO_ROOT/stacks/monitoring/vmagent/vmagent.yml"
    "$REPO_ROOT/stacks/monitoring/vmalert/vmalert.yml"
    "$REPO_ROOT/stacks/monitoring/alertmanager/alertmanager.yml"
    "$REPO_ROOT/stacks/monitoring/victoriametrics/victoriametrics.yml"
  )

  local existing=()
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
      ;;
    always)
      log "init-permissions: running (RUN_INIT_PERMISSIONS=always) $INIT_SCRIPT"
      bash "$INIT_SCRIPT"
      log "init-permissions: done"
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

with_ephemeral_docker_config() {
  local docker_cfg_tmp
  docker_cfg_tmp="$(mktemp -d)"
  chmod 700 "$docker_cfg_tmp"
  trap 'rm -rf "${docker_cfg_tmp:-}"' RETURN
  export DOCKER_CONFIG="$docker_cfg_tmp"

  if needs_ghcr_auth; then
    # shellcheck disable=SC1090
    source "$SECRETS_FILE"
    if [[ -n "${GHCR_USER:-}" && -n "${GHCR_PAT:-}" ]]; then
      log "ghcr: logging in (ephemeral DOCKER_CONFIG)"
      echo "$GHCR_PAT" | docker login ghcr.io -u "$GHCR_USER" --password-stdin >/dev/null
      log "ghcr: login succeeded"
      unset GHCR_USER GHCR_PAT
    else
      log "ghcr: ghcr.io images detected but no credentials set; assuming public"
    fi
  else
    log "ghcr: not used by compose; skipping login"
  fi

  "$@"
}

run_postdeploy_tests() {
  [[ "$RUN_TESTS" == "1" ]] || { log "tests: skipped (RUN_TESTS=0)"; return 0; }
  log "tests: make postdeploy"
  (cd "$REPO_ROOT" && POSTDEPLOY_ON_TARGET=1 make postdeploy)
  log "tests: passed"
}

main() {
  require_root
  sanity_checks
  cd "$REPO_ROOT"

  fix_repo_ownership_if_needed
  refuse_repo_root_env
  check_prereqs

  ensure_docker_daemon_json

  validate_secrets_file

  ensure_journald_read_access

  bootstrap_networks
  maybe_init_permissions

  export MONITORING_CONFIG_HASH
  MONITORING_CONFIG_HASH="$(compute_monitoring_config_hash)"
  log "config-hash: MONITORING_CONFIG_HASH=$MONITORING_CONFIG_HASH"

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
