#!/usr/bin/env bash
set -euo pipefail

# bootstrap-networks.sh
# Ensures external Docker networks used by stacks exist (idempotent), with guardrails.
#
# Default behavior:
# - Ensure "monitoring" and "apps" networks exist (create if missing).
# - If you set *_SUBNET/*_GATEWAY/*_BRIDGE_NAME, validate existing network matches.
# - If missing and subnet config is set, create with that config.
#
# Usage:
#   sudo ./scripts/bootstrap-networks.sh
#   DRY_RUN=1 sudo ./scripts/bootstrap-networks.sh
#
# Env:
#   MONITORING_NETWORK=monitoring
#   APPS_NETWORK=apps
#
#   # Optional desired config (validation + creation)
#   MONITORING_SUBNET=172.20.0.0/16
#   MONITORING_GATEWAY=172.20.0.1
#   MONITORING_BRIDGE_NAME=br-monitoring
#
#   APPS_SUBNET=172.21.0.0/16
#   APPS_GATEWAY=172.21.0.1
#   APPS_BRIDGE_NAME=br-apps
#
#   # Creation behavior
#   CREATE_IF_MISSING=1   (default)
#   DRY_RUN=1            (default 0)
#
# Notes:
# - Overlap detection is best-effort (uses python ipaddress if available).
# - This script does not modify existing networks; it fails if config mismatches.

log() { printf '[%s] %s\n' "$(date -Is)" "$*" >&2; }
die() { log "ERROR: $*"; exit 2; }

require() { command -v "$1" >/dev/null 2>&1 || die "missing required tool: $1"; }

DRY_RUN="${DRY_RUN:-0}"
CREATE_IF_MISSING="${CREATE_IF_MISSING:-1}"

MONITORING_NETWORK="${MONITORING_NETWORK:-monitoring}"
APPS_NETWORK="${APPS_NETWORK:-apps}"

run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    log "DRY_RUN: $*"
    return 0
  fi
  "$@"
}

net_exists() {
  local name="$1"
  docker network inspect "$name" >/dev/null 2>&1
}

net_inspect_json() {
  local name="$1"
  docker network inspect "$name"
}

net_subnet_gateway() {
  local name="$1"
  # prints "subnet gateway" for the first IPAM config entry
  docker network inspect "$name" --format '{{(index .IPAM.Config 0).Subnet}} {{(index .IPAM.Config 0).Gateway}}'
}

net_bridge_name() {
  local name="$1"
  docker network inspect "$name" --format '{{index .Options "com.docker.network.bridge.name"}}'
}

# Best-effort overlap detection:
# - If python3 is available, do real CIDR overlap detection against all existing docker networks.
# - Otherwise, only check exact subnet equality.
check_subnet_overlap() {
  local desired_cidr="$1"
  [[ -n "$desired_cidr" ]] || return 0

  if command -v python3 >/dev/null 2>&1; then
    # Gather all docker subnets
    local subnets
    subnets="$(docker network ls -q | while read -r id; do
      docker network inspect "$id" --format '{{.Name}} {{range .IPAM.Config}}{{.Subnet}} {{end}}'
    done | awk 'NF>=2 {print $1 " " $2}')"

    python3 - <<'PY' "$desired_cidr" "$subnets" || return 1
import ipaddress, sys
desired = ipaddress.ip_network(sys.argv[1], strict=False)
lines = sys.argv[2].splitlines()
overlaps = []
for line in lines:
    name, cidr = line.split()
    try:
        net = ipaddress.ip_network(cidr, strict=False)
    except Exception:
        continue
    if net.overlaps(desired):
        overlaps.append((name, cidr))
if overlaps:
    print("OVERLAP")
    for n,c in overlaps:
        print(f"{n} {c}")
    sys.exit(1)
sys.exit(0)
PY
  else
    # Weak fallback: exact match check
    local match
    match="$(docker network ls -q | while read -r id; do
      docker network inspect "$id" --format '{{.Name}} {{range .IPAM.Config}}{{.Subnet}} {{end}}'
    done | awk -v d="$desired_cidr" 'NF>=2 && $2==d {print $0}')"
    if [[ -n "$match" ]]; then
      log "ERROR: desired subnet already used (exact match). Conflicts:"
      log "$match"
      return 1
    fi
  fi
}

create_network() {
  local name="$1"
  local subnet="${2:-}"
  local gateway="${3:-}"
  local bridge_name="${4:-}"

  local args=(docker network create --driver bridge)

  if [[ -n "$bridge_name" ]]; then
    args+=(--opt "com.docker.network.bridge.name=${bridge_name}")
  fi
  if [[ -n "$subnet" ]]; then
    # overlap guard
    if ! check_subnet_overlap "$subnet" >/tmp/bootstrap-networks.overlap 2>&1; then
      log "Subnet overlap detected while trying to create network '${name}' with subnet '${subnet}'."
      log "Details:"
      sed -n '1,200p' /tmp/bootstrap-networks.overlap >&2 || true
      die "refusing to create network due to overlap"
    fi
    args+=(--subnet "$subnet")
  fi
  if [[ -n "$gateway" ]]; then
    args+=(--gateway "$gateway")
  fi

  args+=("$name")
  log "Creating network: ${args[*]}"
  run "${args[@]}"
}

validate_network() {
  local name="$1"
  local want_subnet="${2:-}"
  local want_gateway="${3:-}"
  local want_bridge="${4:-}"

  if [[ -n "$want_subnet" || -n "$want_gateway" ]]; then
    local have
    have="$(net_subnet_gateway "$name" || true)"
    local have_subnet have_gateway
    have_subnet="$(awk '{print $1}' <<<"$have")"
    have_gateway="$(awk '{print $2}' <<<"$have")"

    if [[ -n "$want_subnet" && "$have_subnet" != "$want_subnet" ]]; then
      die "network '${name}' subnet mismatch: have=${have_subnet:-<none>} want=$want_subnet"
    fi
    if [[ -n "$want_gateway" && "$have_gateway" != "$want_gateway" ]]; then
      die "network '${name}' gateway mismatch: have=${have_gateway:-<none>} want=$want_gateway"
    fi
  fi

  if [[ -n "$want_bridge" ]]; then
    local have_bridge
    have_bridge="$(net_bridge_name "$name" || true)"
    if [[ -n "$have_bridge" && "$have_bridge" != "$want_bridge" ]]; then
      die "network '${name}' bridge name mismatch: have=$have_bridge want=$want_bridge"
    fi
    # If have_bridge is empty, we don't fail (some drivers/configs omit it).
  fi
}

ensure_network() {
  local name="$1"
  local want_subnet="${2:-}"
  local want_gateway="${3:-}"
  local want_bridge="${4:-}"

  if net_exists "$name"; then
    log "Network exists: $name"
    validate_network "$name" "$want_subnet" "$want_gateway" "$want_bridge"
    return 0
  fi

  if [[ "$CREATE_IF_MISSING" != "1" ]]; then
    die "network missing: $name (CREATE_IF_MISSING=0)"
  fi

  log "Network missing: $name"
  create_network "$name" "$want_subnet" "$want_gateway" "$want_bridge"
  validate_network "$name" "$want_subnet" "$want_gateway" "$want_bridge"
}

main() {
  require docker

  log "bootstrap: ensuring external networks"
  log "settings: DRY_RUN=$DRY_RUN CREATE_IF_MISSING=$CREATE_IF_MISSING"
  log "networks: monitoring=$MONITORING_NETWORK apps=$APPS_NETWORK"

  ensure_network "$MONITORING_NETWORK" "${MONITORING_SUBNET:-}" "${MONITORING_GATEWAY:-}" "${MONITORING_BRIDGE_NAME:-}"
  ensure_network "$APPS_NETWORK" "${APPS_SUBNET:-}" "${APPS_GATEWAY:-}" "${APPS_BRIDGE_NAME:-}"

  log "OK: networks ready"
}

main "$@"
