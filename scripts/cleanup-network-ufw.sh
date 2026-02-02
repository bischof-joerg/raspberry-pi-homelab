#!/usr/bin/env bash
# scripts/cleanup-network-ufw.sh
#
# Purpose:
# - Remove stale Docker networks (e.g., compose_default) if unused AND not part of the current stack
# - Remove stale UFW rules referencing non-existent docker bridges
# - Ensure the desired allow rule for Docker Engine metrics (9323) on br-monitoring exists
#
# Guardrails:
# - Default is DRY-RUN (prints actions, does not change system)
# - Requires explicit --apply to make changes
# - Will NOT delete any docker network that has attached containers
# - Will NOT delete networks belonging to the current stack/project
# - Will NOT delete any UFW rule unless it references a non-existent interface OR matches a conservative known-stale pattern
# - Creates a backup of UFW status output prior to changes

set -euo pipefail

SCRIPT_NAME="$(basename "$0")"

APPLY=0
VERBOSE=0

# Desired steady state
MONITORING_NET_NAME="${MONITORING_NET_NAME:-monitoring}"
EXPECTED_BRIDGE_NAME="${EXPECTED_BRIDGE_NAME:-br-monitoring}"
EXPECTED_SUBNET="${EXPECTED_SUBNET:-172.20.0.0/16}"
DOCKER_ENGINE_PORT="${DOCKER_ENGINE_PORT:-9323}"

# Current Compose project name (what you expect for *this* repo stack).
# In your setup, the compose project name is "monitoring" (as shown by `docker compose config`).
CURRENT_COMPOSE_PROJECT="${CURRENT_COMPOSE_PROJECT:-${COMPOSE_PROJECT_NAME:-homelab-home-prod-mon}}"

# Cleanup targets:
# - Name-based candidates (typical leftover: "compose_default")
STALE_DOCKER_NETWORKS_REGEX="${STALE_DOCKER_NETWORKS_REGEX:-^(compose_default)$}"

# Known stale bridge patterns (from previous iterations)
STALE_BRIDGE_PREFIXES_REGEX="${STALE_BRIDGE_PREFIXES_REGEX:-^(br-abe|br-bd2|docker0)$}"

usage() {
  cat <<EOF
Usage:
  $SCRIPT_NAME [--apply] [--verbose]

Modes:
  (default) DRY-RUN: prints what it would do, makes no changes
  --apply: perform changes

Environment overrides:
  MONITORING_NET_NAME=$MONITORING_NET_NAME
  EXPECTED_BRIDGE_NAME=$EXPECTED_BRIDGE_NAME
  EXPECTED_SUBNET=$EXPECTED_SUBNET
  DOCKER_ENGINE_PORT=$DOCKER_ENGINE_PORT
  CURRENT_COMPOSE_PROJECT=$CURRENT_COMPOSE_PROJECT
  STALE_DOCKER_NETWORKS_REGEX=$STALE_DOCKER_NETWORKS_REGEX

Notes:
  - Must be run with sudo/root privileges.
  - Designed for Debian/Raspberry Pi OS with Docker + UFW.
EOF
}

log() { printf '[%s] %s\n' "$(date -Is)" "$*"; }
vlog() { [ "$VERBOSE" -eq 1 ] && log "$@"; }
die() { log "ERROR: $*"; exit 1; }

need_root() {
  [ "$(id -u)" -eq 0 ] || die "Run as root (e.g., sudo $SCRIPT_NAME ...)"
}

run_cmd() {
  if [ "$APPLY" -eq 1 ]; then
    vlog "RUN: $*"
    "$@"
  else
    log "DRY-RUN: $*"
  fi
}

# ---- Docker helpers ----

docker_network_exists() { docker network inspect "$1" >/dev/null 2>&1; }

docker_network_bridge_name() {
  docker network inspect "$1" --format '{{ index .Options "com.docker.network.bridge.name" }}' 2>/dev/null || true
}

docker_network_subnet() {
  docker network inspect "$1" --format '{{ (index .IPAM.Config 0).Subnet }}' 2>/dev/null || true
}

docker_network_gateway() {
  docker network inspect "$1" --format '{{ (index .IPAM.Config 0).Gateway }}' 2>/dev/null || true
}

docker_network_labels() {
  docker network inspect "$1" --format '{{json .Labels}}' 2>/dev/null || echo '{}'
}

docker_network_compose_project_label() {
  # returns empty if not a compose-managed network
  docker network inspect "$1" --format '{{ index .Labels "com.docker.compose.project" }}' 2>/dev/null || true
}

docker_network_compose_network_label() {
  docker network inspect "$1" --format '{{ index .Labels "com.docker.compose.network" }}' 2>/dev/null || true
}

docker_network_has_containers() {
  # Returns 0 if has attached containers; 1 if empty
  local net="$1"
  local containers_json
  containers_json="$(docker network inspect "$net" --format '{{json .Containers}}' 2>/dev/null || echo '{}')"
  if echo "$containers_json" | grep -qv '^{ *} *$'; then
    return 0
  fi
  return 1
}

list_docker_networks() { docker network ls --format '{{.Name}}'; }

# Decide if a candidate stale network is safe to remove:
# - must have no containers
# - must NOT be the monitoring network
# - if it is compose-managed:
#     - do not remove if compose project label == CURRENT_COMPOSE_PROJECT
# - if not compose-managed:
#     - only remove if name matches STALE_DOCKER_NETWORKS_REGEX (already checked)
docker_network_is_safe_to_remove() {
  local net="$1"

  [ "$net" != "$MONITORING_NET_NAME" ] || return 1

  if docker_network_has_containers "$net"; then
    return 1
  fi

  local proj
  proj="$(docker_network_compose_project_label "$net")"
  if [ -n "$proj" ]; then
    if [ "$proj" = "$CURRENT_COMPOSE_PROJECT" ]; then
      # belongs to this repo's compose project
      return 1
    fi
  fi

  return 0
}

# ---- UFW helpers ----

ufw_is_active() { ufw status | head -n1 | grep -qi 'Status: active'; }

backup_ufw_status() {
  local dir="/var/backups/raspberry-pi-homelab"
  local ts
  ts="$(date +%Y%m%d-%H%M%S)"
  run_cmd mkdir -p "$dir"
  if [ "$APPLY" -eq 1 ]; then
    ufw status verbose > "${dir}/ufw-status-${ts}.txt"
    ufw status numbered > "${dir}/ufw-status-numbered-${ts}.txt"
    log "UFW backup written to ${dir}/ufw-status-*.txt"
  else
    log "DRY-RUN: would write UFW backup to ${dir}/ufw-status-${ts}.txt"
  fi
}

ufw_list_numbered() { ufw status numbered; }

iface_exists() { ip link show "$1" >/dev/null 2>&1; }

ensure_ufw_rule_for_docker_engine_metrics() {
  # Ensure allow in on br-monitoring from 172.20.0.0/16 to port 9323 exists.
  local want_re
  want_re="^${DOCKER_ENGINE_PORT}/tcp on ${EXPECTED_BRIDGE_NAME}[[:space:]]+ALLOW IN[[:space:]]+${EXPECTED_SUBNET}\b"

  local cur
  cur="$(ufw_list_numbered | sed -n '1,220p')"

  if echo "$cur" | grep -Eq "$want_re"; then
    log "UFW: OK (found allow rule for ${EXPECTED_BRIDGE_NAME} ${EXPECTED_SUBNET} port ${DOCKER_ENGINE_PORT})"
    return 0
  fi

  log "UFW: missing allow rule for ${EXPECTED_BRIDGE_NAME} ${EXPECTED_SUBNET} port ${DOCKER_ENGINE_PORT}"
  run_cmd ufw allow in on "$EXPECTED_BRIDGE_NAME" from "$EXPECTED_SUBNET" to any port "$DOCKER_ENGINE_PORT" proto tcp comment "Docker engine metrics from monitoring net"
}

delete_ufw_rule_by_number() {
  local num="$1"
  if [ "$APPLY" -eq 1 ]; then
    yes y | ufw delete "$num" >/dev/null
    log "UFW: deleted rule [$num]"
  else
    log "DRY-RUN: ufw delete $num"
  fi
}

cleanup_stale_ufw_rules() {
  local lines
  lines="$(ufw_list_numbered | sed -n '1,320p')"

  while IFS= read -r line; do
    local num iface
    num="$(echo "$line" | sed -n 's/^\[\s*\([0-9]\+\)\].*/\1/p')"
    [ -n "$num" ] || continue

    iface="$(echo "$line" | sed -n 's/.* on \([a-zA-Z0-9_.-]\+\).*/\1/p')"
    [ -n "$iface" ] || continue

    if ! echo "$iface" | grep -Eq '^(br-|docker0)'; then
      continue
    fi

    # Candidate 1: interface does not exist anymore AND looks like a known stale prefix
    if ! iface_exists "$iface"; then
      if echo "$iface" | grep -Eq "$STALE_BRIDGE_PREFIXES_REGEX"; then
        log "UFW: stale iface rule candidate (iface missing): [$num] $line"
        delete_ufw_rule_by_number "$num"
      else
        vlog "UFW: iface missing but not in stale prefix allowlist; skipping: iface=$iface line=$line"
      fi
      continue
    fi

    # Candidate 2: overly broad allow-anywhere for 9323 on br-monitoring, if subnet-scoped rule exists.
    if echo "$line" | grep -Eq "^\\[\\s*${num}\\]\\s+${DOCKER_ENGINE_PORT}/tcp on ${EXPECTED_BRIDGE_NAME}\\s+ALLOW IN\\s+Anywhere\\b"; then
      if echo "$lines" | grep -Eq "^\\[\\s*[0-9]+\\]\\s+${DOCKER_ENGINE_PORT}/tcp on ${EXPECTED_BRIDGE_NAME}\\s+ALLOW IN\\s+${EXPECTED_SUBNET}\\b"; then
        log "UFW: broad 9323 allow-anywhere on ${EXPECTED_BRIDGE_NAME} is redundant; candidate: [$num] $line"
        delete_ufw_rule_by_number "$num"
      fi
    fi

  done < <(echo "$lines" | grep -E '^\[\s*[0-9]+\]' || true)
}

# ---- Main ----

main() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --apply) APPLY=1; shift ;;
      --verbose) VERBOSE=1; shift ;;
      -h|--help) usage; exit 0 ;;
      *) die "Unknown arg: $1 (use --help)" ;;
    esac
  done

  need_root

  log "mode: $( [ "$APPLY" -eq 1 ] && echo APPLY || echo DRY-RUN )"
  log "docker: verifying monitoring network '${MONITORING_NET_NAME}'"

  command -v docker >/dev/null 2>&1 || die "docker not found"
  command -v ufw >/dev/null 2>&1 || die "ufw not found"

  docker_network_exists "$MONITORING_NET_NAME" || die "Docker network '${MONITORING_NET_NAME}' not found. Start the stack first."

  local bridge subnet gateway
  bridge="$(docker_network_bridge_name "$MONITORING_NET_NAME")"
  subnet="$(docker_network_subnet "$MONITORING_NET_NAME")"
  gateway="$(docker_network_gateway "$MONITORING_NET_NAME")"

  [ "$bridge" = "$EXPECTED_BRIDGE_NAME" ] || die "Monitoring network bridge mismatch: expected '${EXPECTED_BRIDGE_NAME}', got '${bridge}'."
  [ "$subnet" = "$EXPECTED_SUBNET" ] || die "Monitoring network subnet mismatch: expected '${EXPECTED_SUBNET}', got '${subnet}'."

  log "docker: OK network=${MONITORING_NET_NAME} bridge=${bridge} subnet=${subnet} gateway=${gateway}"

  # Docker cleanup: remove stale networks if unused and foreign
  log "docker: scanning for stale networks matching regex: ${STALE_DOCKER_NETWORKS_REGEX}"
  local n
  for n in $(list_docker_networks); do
    if echo "$n" | grep -Eq "$STALE_DOCKER_NETWORKS_REGEX"; then
      local proj netlbl labels
      proj="$(docker_network_compose_project_label "$n")"
      netlbl="$(docker_network_compose_network_label "$n")"
      labels="$(docker_network_labels "$n")"

      if docker_network_is_safe_to_remove "$n"; then
        log "docker: removing unused stale network '${n}' (compose.project='${proj:-}' compose.network='${netlbl:-}')"
        vlog "docker: labels=${labels}"
        run_cmd docker network rm "$n"
      else
        log "docker: keeping '${n}' (not safe to remove). compose.project='${proj:-}' compose.network='${netlbl:-}'"
        vlog "docker: labels=${labels}"
      fi
    fi
  done

  # UFW cleanup
  if ! ufw_is_active; then
    log "ufw: inactive; skipping UFW cleanup"
  else
    log "ufw: active; backing up and reconciling rules"
    backup_ufw_status
    cleanup_stale_ufw_rules
    ensure_ufw_rule_for_docker_engine_metrics
  fi

  log "done"
  if [ "$APPLY" -eq 0 ]; then
    log "No changes were made. Re-run with --apply to perform actions."
  fi
}

main "$@"
