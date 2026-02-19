#!/usr/bin/env bash
set -euo pipefail

log(){ echo "[$(date -Is)] $*"; }
die(){ echo "ERROR: $*" >&2; exit 2; }

require_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    die "Please run with sudo/root"
  fi
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing tool: $1"
}

# Repo-root can be inferred from this script location:
# scripts/host/ensure-docker-daemon-json.sh -> REPO_ROOT is 2 levels up
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

DOCKER_DAEMON_JSON_SRC="${DOCKER_DAEMON_JSON_SRC:-$REPO_ROOT/stacks/core/docker/daemon.json}"
DOCKER_DAEMON_JSON_DST="${DOCKER_DAEMON_JSON_DST:-/etc/docker/daemon.json}"
DOCKER_DAEMON_JSON_MODE="${DOCKER_DAEMON_JSON_MODE:-644}"

# 1|0: restart docker if config changed
RESTART_DOCKER_ON_CHANGE="${RESTART_DOCKER_ON_CHANGE:-1}"

validate_json() {
  # Prefer python stdlib (always available in your repo toolchain), jq optional
  if command -v jq >/dev/null 2>&1; then
    jq -e . "$DOCKER_DAEMON_JSON_SRC" >/dev/null
  else
    python3 -m json.tool "$DOCKER_DAEMON_JSON_SRC" >/dev/null
  fi
}

is_same() {
  [[ -f "$DOCKER_DAEMON_JSON_DST" ]] || return 1
  cmp -s "$DOCKER_DAEMON_JSON_SRC" "$DOCKER_DAEMON_JSON_DST"
}

apply() {
  require_root
  require_cmd install
  require_cmd cmp
  require_cmd systemctl
  require_cmd python3

  [[ -f "$DOCKER_DAEMON_JSON_SRC" ]] || die "source missing: $DOCKER_DAEMON_JSON_SRC"

  if ! validate_json; then
    die "invalid JSON: $DOCKER_DAEMON_JSON_SRC"
  fi

  if is_same; then
    log "docker-daemon: OK (no changes) dst=$DOCKER_DAEMON_JSON_DST"
    return 0
  fi

  log "docker-daemon: updating dst=$DOCKER_DAEMON_JSON_DST from src=$DOCKER_DAEMON_JSON_SRC"
  install -d -m 755 "$(dirname "$DOCKER_DAEMON_JSON_DST")"
  install -m "$DOCKER_DAEMON_JSON_MODE" "$DOCKER_DAEMON_JSON_SRC" "$DOCKER_DAEMON_JSON_DST"

  if [[ "$RESTART_DOCKER_ON_CHANGE" == "1" ]]; then
    log "docker-daemon: restarting docker (config changed)"
    systemctl daemon-reload || true
    systemctl restart docker
    systemctl is-active --quiet docker || die "docker is not active after restart"
    log "docker-daemon: docker restarted successfully"
  else
    log "docker-daemon: restart skipped (RESTART_DOCKER_ON_CHANGE=0)"
  fi
}

check() {
  require_cmd cmp
  require_cmd python3

  [[ -f "$DOCKER_DAEMON_JSON_SRC" ]] || die "source missing: $DOCKER_DAEMON_JSON_SRC"

  validate_json || die "invalid JSON: $DOCKER_DAEMON_JSON_SRC"

  if is_same; then
    log "docker-daemon: OK (in sync) dst=$DOCKER_DAEMON_JSON_DST"
    return 0
  fi

  die "docker-daemon: DRIFT detected (src != dst): $DOCKER_DAEMON_JSON_DST"
}

usage() {
  cat <<EOF
Usage: $(basename "$0") <apply|check>

Env overrides:
  DOCKER_DAEMON_JSON_SRC
  DOCKER_DAEMON_JSON_DST
  DOCKER_DAEMON_JSON_MODE
  RESTART_DOCKER_ON_CHANGE (1|0)
EOF
}

main() {
  local cmd="${1:-}"
  case "$cmd" in
    apply) apply ;;
    check) check ;;
    *) usage; exit 2 ;;
  esac
}

main "$@"
