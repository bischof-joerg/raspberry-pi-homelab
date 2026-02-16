#!/usr/bin/env bash
# scripts/cleanup-network-ufw.sh
#
# Usage:
: <<'DOC'
Dry-run:
sudo bash -lc '
  set -euo pipefail
  set -a
  source /etc/raspberry-pi-homelab/monitoring.env
  set +a
  /home/admin/iac/raspberry-pi-homelab/scripts/cleanup-network-ufw.sh --verbose
'

Apply:
sudo bash -lc '
  set -euo pipefail
  set -a
  source /etc/raspberry-pi-homelab/monitoring.env
  set +a
  /home/admin/iac/raspberry-pi-homelab/scripts/cleanup-network-ufw.sh --apply --verbose
'
DOC
#
# Purpose:
# - Remove stale Docker networks (optional, conservative) if unused AND not part of current stack
# - Remove stale UFW rules referencing non-existent docker bridges
# - Enforce a deterministic UFW allowlist for inbound exposure (GitOps)
# - Tag all rules managed by this script as: "iac:<tag> <human text>"
#
# Managed inbound exposure (IPv4-only for LAN services; IPv6 inbound closed):
# - SSH:     22/tcp  ALLOW from ADMIN_IPV4(/32) and LAN_CIDR (IPv4)
# - Grafana: 3000/tcp ALLOW from LAN_CIDR (IPv4) + DENY Anywhere (v4/v6)
# - VictoriaLogs UI: 9428/tcp ALLOW from LAN_CIDR (IPv4) + DENY Anywhere (v4/v6)
# - Docker engine metrics: 9323/tcp on br-monitoring ALLOW from 172.20.0.0/16
#
# Removed exposures:
# - Prometheus:   9090/tcp (v4/v6)
# - Alertmanager: 9093/tcp (v4/v6)
#
# Guardrails:
# - Default is DRY-RUN (prints actions, does not change system)
# - Requires explicit --apply to make changes
# - Creates a backup of UFW status output prior to changes (in APPLY mode)
#
set -euo pipefail

SCRIPT_NAME="$(basename "$0")"

APPLY=0
VERBOSE=0

# ---- Desired steady state (Docker metrics) ----
MONITORING_NET_NAME="${MONITORING_NET_NAME:-monitoring}"
EXPECTED_BRIDGE_NAME="${EXPECTED_BRIDGE_NAME:-br-monitoring}"
EXPECTED_SUBNET="${EXPECTED_SUBNET:-172.20.0.0/16}"
DOCKER_ENGINE_PORT="${DOCKER_ENGINE_PORT:-9323}"

# Current Compose project name (what you expect for *this* repo stack).
CURRENT_COMPOSE_PROJECT="${CURRENT_COMPOSE_PROJECT:-${COMPOSE_PROJECT_NAME:-homelab-home-prod-mon}}"

# ---- Desired steady state (Inbound exposure) ----
LAN_CIDR="${LAN_CIDR:-}"               # e.g. 192.168.178.0/24
ADMIN_IPV4="${ADMIN_IPV4:-}"           # e.g. 192.168.178.42

SSH_PORT="${SSH_PORT:-22}"
GRAFANA_PORT="${GRAFANA_PORT:-3000}"
VLOGS_UI_PORT="${VLOGS_UI_PORT:-9428}"

PROMETHEUS_PORT="${PROMETHEUS_PORT:-9090}"
ALERTMANAGER_PORT="${ALERTMANAGER_PORT:-9093}"

# If set to 1, keep legacy "Anywhere on docker0 ALLOW IN Anywhere" rules (NOT recommended).
KEEP_DOCKER0_ANYWHERE_RULE="${KEEP_DOCKER0_ANYWHERE_RULE:-0}"

# Cleanup targets:
STALE_DOCKER_NETWORKS_REGEX="${STALE_DOCKER_NETWORKS_REGEX:-^(compose_default)$}"
STALE_BRIDGE_PREFIXES_REGEX="${STALE_BRIDGE_PREFIXES_REGEX:-^(br-abe|br-bd2|docker0)$}"

# Tagging
TAG_PREFIX="iac:"

usage() {
  cat <<EOF
Usage:
  $SCRIPT_NAME [--apply] [--verbose]

Modes:
  (default) DRY-RUN: prints what it would do, makes no changes
  --apply: perform changes

Required environment:
  LAN_CIDR=192.168.178.0/24
  ADMIN_IPV4=192.168.178.42

Optional environment overrides:
  SSH_PORT=$SSH_PORT
  GRAFANA_PORT=$GRAFANA_PORT
  VLOGS_UI_PORT=$VLOGS_UI_PORT
  PROMETHEUS_PORT=$PROMETHEUS_PORT
  ALERTMANAGER_PORT=$ALERTMANAGER_PORT

Docker metrics overrides:
  MONITORING_NET_NAME=$MONITORING_NET_NAME
  EXPECTED_BRIDGE_NAME=$EXPECTED_BRIDGE_NAME
  EXPECTED_SUBNET=$EXPECTED_SUBNET
  DOCKER_ENGINE_PORT=$DOCKER_ENGINE_PORT

Notes:
  - Must be run with sudo/root privileges.
  - IPv6 inbound is intentionally closed for managed services (no allow rules; explicit deny for 3000/9428).
EOF
}

log() { printf '[%s] %s\n' "$(date -Is)" "$*"; }
vlog() { [ "$VERBOSE" -eq 1 ] && log "$@"; }
die() { log "ERROR: $*"; exit 1; }

need_root() { [ "$(id -u)" -eq 0 ] || die "Run as root (e.g., sudo $SCRIPT_NAME ...)"; }

require_env() {
  local name="$1"
  local val="${!name:-}"
  [ -n "$val" ] || die "${name} is required (export ${name}=... or set it in monitoring.env)"
}

run_cmd() {
  if [ "$APPLY" -eq 1 ]; then
    vlog "RUN: $*"
    "$@"
  else
    log "DRY-RUN: $*"
  fi
}

ufw_supports_comment() {
  ufw --help 2>&1 | grep -qi 'comment'
}

UFW_HAS_COMMENT=0
tag_comment() {
  # tag_comment "<tag>" "<human>"
  printf '%s%s %s' "$TAG_PREFIX" "$1" "$2"
}

# ---- Docker helpers ----
docker_network_exists() { docker network inspect "$1" >/dev/null 2>&1; }
docker_network_bridge_name() { docker network inspect "$1" --format '{{ index .Options "com.docker.network.bridge.name" }}' 2>/dev/null || true; }
docker_network_subnet() { docker network inspect "$1" --format '{{ (index .IPAM.Config 0).Subnet }}' 2>/dev/null || true; }
docker_network_gateway() { docker network inspect "$1" --format '{{ (index .IPAM.Config 0).Gateway }}' 2>/dev/null || true; }
docker_network_labels() { docker network inspect "$1" --format '{{json .Labels}}' 2>/dev/null || echo '{}'; }
docker_network_compose_project_label() { docker network inspect "$1" --format '{{ index .Labels "com.docker.compose.project" }}' 2>/dev/null || true; }
docker_network_compose_network_label() { docker network inspect "$1" --format '{{ index .Labels "com.docker.compose.network" }}' 2>/dev/null || true; }

docker_network_has_containers() {
  local net="$1"
  local containers_json
  containers_json="$(docker network inspect "$net" --format '{{json .Containers}}' 2>/dev/null || echo '{}')"
  if echo "$containers_json" | grep -qv '^{ *} *$'; then return 0; fi
  return 1
}

list_docker_networks() { docker network ls --format '{{.Name}}'; }

docker_network_is_safe_to_remove() {
  local net="$1"
  [ "$net" != "$MONITORING_NET_NAME" ] || return 1
  if docker_network_has_containers "$net"; then return 1; fi
  local proj
  proj="$(docker_network_compose_project_label "$net")"
  if [ -n "$proj" ] && [ "$proj" = "$CURRENT_COMPOSE_PROJECT" ]; then return 1; fi
  return 0
}

# ---- UFW helpers ----
ufw_is_active() { ufw status | head -n1 | grep -qi 'Status: active'; }
ufw_list_numbered() { ufw status numbered; }

iface_exists() { ip link show "$1" >/dev/null 2>&1; }

# Normalize "ufw status numbered" lines so regex can anchor at start of rule:
# - Strip leading "[ N] "
# - Strip trailing " # comment"
ufw_normalized_numbered_lines() {
  ufw_list_numbered | awk '
    $0 ~ /^\[[[:space:]]*[0-9]+\]/ {
      line=$0
      sub(/^\[[[:space:]]*[0-9]+\][[:space:]]+/, "", line)  # drop "[ N] "
      sub(/[[:space:]]+#.*$/, "", line)                      # drop trailing comment
      print line
    }
  '
}

delete_ufw_rule_by_number() {
  local n="$1"
  [ -n "$n" ] || return 0

  if [ "$APPLY" -eq 1 ]; then
    if yes y | ufw delete "$n" >/dev/null 2>&1; then
      log "UFW: deleted rule [$n]"
    else
      log "UFW: WARN could not delete rule [$n] (may have been renumbered/removed); continuing"
    fi
  else
    log "DRY-RUN: ufw delete $n"
  fi
}

# Delete rules whose normalized LINE matches a regex.
# Deletes highest->lowest to avoid renumbering issues.
delete_ufw_rules_matching_line_regex() {
  local line_re="$1"

  local nums
  nums="$(
    ufw_list_numbered | awk -v re="$line_re" '
      $0 ~ /^\[[[:space:]]*[0-9]+\]/ {
        raw=$0

        # Extract rule number from leading "[  N]"
        num=raw
        sub(/^\[[[:space:]]*/, "", num)
        sub(/\].*$/, "", num)

        # Normalize line (drop "[N] " and trailing comments)
        line=raw
        sub(/^\[[[:space:]]*[0-9]+\][[:space:]]+/, "", line)
        sub(/[[:space:]]+#.*$/, "", line)

        if (line ~ re) {
          print num
        }
      }
    ' | sort -nr
  )"

  [ -n "$nums" ] || return 0

  log "UFW: deleting rules matching line regex: ${line_re}"
  while read -r n; do
    [ -n "$n" ] || continue
    delete_ufw_rule_by_number "$n"
  done <<<"$nums"
}

# Delete rules by tag in the raw numbered output line (comment portion).
delete_ufw_rules_by_tag() {
  local tag="$1"
  local tag_re="#[[:space:]]*${TAG_PREFIX}${tag}([[:space:]]|$)"

  local nums
  nums="$(
    ufw_list_numbered | awk -v re="$tag_re" '
      $0 ~ /^\[[[:space:]]*[0-9]+\]/ {
        raw=$0
        if (raw ~ re) {
          num=raw
          sub(/^\[[[:space:]]*/, "", num)
          sub(/\].*$/, "", num)
          print num
        }
      }
    ' | sort -nr
  )"

  [ -n "$nums" ] || return 0

  log "UFW: deleting rules by tag ${TAG_PREFIX}${tag}"
  while read -r n; do
    [ -n "$n" ] || continue
    delete_ufw_rule_by_number "$n"
  done <<<"$nums"
}


# Returns 0 if there exists a rule whose normalized line matches line_re AND whose raw line contains tag.
ufw_rule_present_with_tag() {
  local line_re="$1"
  local tag="$2"
  local tag_re="#[[:space:]]*${TAG_PREFIX}${tag}([[:space:]]|$)"

  ufw_list_numbered | awk -v line_re="$line_re" -v tag_re="$tag_re" '
    $0 ~ /^\[[[:space:]]*[0-9]+\]/ {
      raw=$0
      norm=raw
      sub(/^\[[[:space:]]*[0-9]+\][[:space:]]+/, "", norm)
      sub(/[[:space:]]+#.*$/, "", norm)
      if (norm ~ line_re && raw ~ tag_re) { found=1 }
    }
    END { exit(found?0:1) }
  '
}


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

# ---- Fix (1): no truncation of ufw status numbered ----
cleanup_stale_ufw_iface_rules() {
  while IFS= read -r line; do
    local num iface
    num="$(echo "$line" | sed -n 's/^\[\s*\([0-9]\+\)\].*/\1/p')"
    [ -n "$num" ] || continue

    iface="$(echo "$line" | sed -n 's/.* on \([a-zA-Z0-9_.-]\+\).*/\1/p')"
    [ -n "$iface" ] || continue

    if ! echo "$iface" | grep -Eq '^(br-|docker0)'; then
      continue
    fi

    if ! iface_exists "$iface"; then
      if echo "$iface" | grep -Eq "$STALE_BRIDGE_PREFIXES_REGEX"; then
        log "UFW: stale iface rule candidate (iface missing): [$num] $line"
        delete_ufw_rule_by_number "$num"
      else
        vlog "UFW: iface missing but not in stale prefix allowlist; skipping: iface=$iface line=$line"
      fi
    fi
  done < <(ufw_list_numbered | grep -E '^\[\s*[0-9]+\]' || true)
}

# Wrapper to add rules with optional comment support.
ufw_allow_with_comment() {
  # args: ...; last two args are: tag, human
  local tag="$1"; shift
  local human="$1"; shift

  local c
  c="$(tag_comment "$tag" "$human")"
  if [ "$UFW_HAS_COMMENT" -eq 1 ]; then
    run_cmd ufw "$@" comment "$c"
  else
    run_cmd ufw "$@"
  fi
}

ufw_deny_with_comment() {
  local tag="$1"; shift
  local human="$1"; shift

  local c
  c="$(tag_comment "$tag" "$human")"
  if [ "$UFW_HAS_COMMENT" -eq 1 ]; then
    run_cmd ufw "$@" comment "$c"
  else
    run_cmd ufw "$@"
  fi
}

ensure_ufw_rule_for_docker_engine_metrics() {
  local tag="docker-engine-metrics"
  local human="Docker engine metrics from monitoring net"
  local want_re
  want_re="^${DOCKER_ENGINE_PORT}/tcp on ${EXPECTED_BRIDGE_NAME}[[:space:]]+ALLOW IN[[:space:]]+${EXPECTED_SUBNET}([[:space:]]|$)"

  if ufw_rule_present_with_tag "$want_re" "$tag"; then
    log "UFW: OK (tagged allow rule for ${EXPECTED_BRIDGE_NAME} ${EXPECTED_SUBNET} port ${DOCKER_ENGINE_PORT})"
    return 0
  fi

  # If rule exists untagged, replace it with tagged one
  if ufw_normalized_numbered_lines | grep -Eq "$want_re"; then
    log "UFW: metrics rule exists but is untagged/wrong-tagged -> replacing"
    delete_ufw_rules_matching_line_regex "$want_re"
  fi

  # Remove any previous managed variants under this tag
  delete_ufw_rules_by_tag "$tag"

  log "UFW: ensuring tagged metrics allow rule"
  ufw_allow_with_comment "$tag" "$human" allow in on "$EXPECTED_BRIDGE_NAME" from "$EXPECTED_SUBNET" to any port "$DOCKER_ENGINE_PORT" proto tcp
}

# ---- Enforce deterministic exposure rules ----

ensure_allow_from_cidr_to_port_v4() {
  local cidr="$1"
  local port="$2"
  local tag="$3"
  local human="$4"

  local want_re="^${port}/tcp[[:space:]]+ALLOW IN[[:space:]]+${cidr}([[:space:]]|$)"

  if ufw_rule_present_with_tag "$want_re" "$tag"; then
    log "UFW: OK (tagged allow ${port}/tcp from ${cidr})"
    return 0
  fi

  # Replace untagged (or wrong-tagged) matching rule
  if ufw_normalized_numbered_lines | grep -Eq "$want_re"; then
    log "UFW: allow ${port}/tcp from ${cidr} exists but is untagged/wrong-tagged -> replacing"
    delete_ufw_rules_matching_line_regex "$want_re"
  fi

  # Remove any previous managed variants under this tag
  delete_ufw_rules_by_tag "$tag"

  log "UFW: ensuring tagged allow ${port}/tcp from ${cidr}"
  ufw_allow_with_comment "$tag" "$human" allow from "$cidr" to any port "$port" proto tcp
}

ensure_deny_anywhere_for_port() {
  local port="$1"
  local tag="$2"
  local human="$3"

  local want_v4 want_v6
  want_v4="^${port}/tcp[[:space:]]+DENY IN[[:space:]]+Anywhere([[:space:]]|$)"
  # Accept both formats:
  # - "9428/tcp DENY IN Anywhere (v6)"
  # - "9428/tcp (v6) DENY IN Anywhere (v6)"
  want_v6="^${port}/tcp([[:space:]]+\\(v6\\))?[[:space:]]+DENY IN[[:space:]]+Anywhere \\(v6\\)([[:space:]]|$)"

  if ufw_rule_present_with_tag "$want_v4" "$tag"; then
    log "UFW: OK (tagged deny ${port}/tcp Anywhere)"
  else
    if ufw_normalized_numbered_lines | grep -Eq "$want_v4"; then
      log "UFW: deny ${port}/tcp Anywhere exists but untagged/wrong-tagged -> replacing"
      delete_ufw_rules_matching_line_regex "$want_v4"
    fi
    delete_ufw_rules_by_tag "$tag"
    log "UFW: ensuring tagged deny ${port}/tcp Anywhere"
    ufw_deny_with_comment "$tag" "$human" deny "${port}/tcp"
  fi

  if ufw_rule_present_with_tag "$want_v6" "$tag"; then
    log "UFW: OK (tagged deny ${port}/tcp Anywhere (v6))"
  else
    if ufw_normalized_numbered_lines | grep -Eq "$want_v6"; then
      log "UFW: deny ${port}/tcp Anywhere (v6) exists but untagged/wrong-tagged -> replacing"
      delete_ufw_rules_matching_line_regex "$want_v6"
    fi
    # same tag: deny rules are separate v4/v6 internally; enforce again (idempotent)
    log "UFW: ensuring tagged deny ${port}/tcp Anywhere (v6)"
    ufw_deny_with_comment "$tag" "$human" deny "${port}/tcp"
  fi
}

remove_unwanted_rules_for_port() {
  local port="$1"

  # Remove any broad allows:
  # - ALLOW IN Anywhere (v4)
  # - ALLOW IN Anywhere (v6)
  # - ALLOW IN 2000::/3
  # - ALLOW IN fe80::/10
  delete_ufw_rules_matching_line_regex "^${port}/tcp[[:space:]]+ALLOW IN[[:space:]]+Anywhere(\\s|$)"
  delete_ufw_rules_matching_line_regex "^${port}/tcp[[:space:]]+ALLOW IN[[:space:]]+Anywhere \\(v6\\)([[:space:]]|$)"
  delete_ufw_rules_matching_line_regex "^${port}/tcp[[:space:]]+ALLOW IN[[:space:]]+2000::/3([[:space:]]|$)"
  delete_ufw_rules_matching_line_regex "^${port}/tcp[[:space:]]+ALLOW IN[[:space:]]+fe80::/10([[:space:]]|$)"
}

remove_prometheus_alertmanager_exposure() {
  log "UFW: removing Prometheus/Alertmanager exposure rules (ports ${PROMETHEUS_PORT}, ${ALERTMANAGER_PORT})"
  delete_ufw_rules_matching_line_regex "^${PROMETHEUS_PORT}/tcp[[:space:]]+ALLOW IN[[:space:]].*"
  delete_ufw_rules_matching_line_regex "^${ALERTMANAGER_PORT}/tcp[[:space:]]+ALLOW IN[[:space:]].*"
}

maybe_remove_docker0_anywhere_rule() {
  if [ "$KEEP_DOCKER0_ANYWHERE_RULE" -eq 1 ]; then
    log "UFW: keeping docker0 anywhere rule (KEEP_DOCKER0_ANYWHERE_RULE=1)"
    return 0
  fi
  log "UFW: removing broad docker0 allow rules (not part of desired exposure set)"
  delete_ufw_rules_matching_line_regex "^Anywhere on docker0[[:space:]]+ALLOW IN[[:space:]]+Anywhere([[:space:]]|$)"
}

enforce_inbound_exposure_policy() {
  # 1) Remove unwanted legacy exposures
  remove_prometheus_alertmanager_exposure
  maybe_remove_docker0_anywhere_rule

  # 2) Remove unwanted broad/IPv6 allows for managed ports
  remove_unwanted_rules_for_port "$GRAFANA_PORT"
  remove_unwanted_rules_for_port "$VLOGS_UI_PORT"
  remove_unwanted_rules_for_port "$SSH_PORT"

  # Also remove IPv6 global/unknown SSH allows (e.g. 2000::/3 or fe80::/10)
  delete_ufw_rules_matching_line_regex "^${SSH_PORT}/tcp[[:space:]]+ALLOW IN[[:space:]]+2000::/3([[:space:]]|$)"
  delete_ufw_rules_matching_line_regex "^${SSH_PORT}/tcp[[:space:]]+ALLOW IN[[:space:]]+fe80::/10([[:space:]]|$)"
  delete_ufw_rules_matching_line_regex "^${SSH_PORT}/tcp[[:space:]]+ALLOW IN[[:space:]]+Anywhere \\(v6\\)([[:space:]]|$)"
  delete_ufw_rules_matching_line_regex "^${SSH_PORT}/tcp[[:space:]]+ALLOW IN[[:space:]]+Anywhere([[:space:]]|$)"

  # 3) Ensure desired IPv4 allows (tagged)
  ensure_allow_from_cidr_to_port_v4 "$LAN_CIDR" "$GRAFANA_PORT" "grafana-lan" "Grafana UI from LAN"
  ensure_allow_from_cidr_to_port_v4 "$LAN_CIDR" "$VLOGS_UI_PORT" "victorialogs-ui-lan" "VictoriaLogs UI from LAN"

  ensure_allow_from_cidr_to_port_v4 "$ADMIN_IPV4" "$SSH_PORT" "ssh-admin" "SSH admin IPv4"
  ensure_allow_from_cidr_to_port_v4 "$LAN_CIDR" "$SSH_PORT" "ssh-lan" "SSH LAN IPv4"

  # 4) Ensure explicit deny-anywhere for Grafana/VLogs to avoid accidental future broad allow (tagged)
  ensure_deny_anywhere_for_port "$GRAFANA_PORT" "deny-grafana-anywhere" "Block Grafana except LAN"
  ensure_deny_anywhere_for_port "$VLOGS_UI_PORT" "deny-vlogs-ui-anywhere" "Block VictoriaLogs UI except LAN"
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
  require_env LAN_CIDR
  require_env ADMIN_IPV4

  # (2) Normalize ADMIN_IPV4 to /32 if not already CIDR
  if ! echo "$ADMIN_IPV4" | grep -q '/'; then
    ADMIN_IPV4="${ADMIN_IPV4}/32"
  fi

  command -v docker >/dev/null 2>&1 || die "docker not found"
  command -v ufw >/dev/null 2>&1 || die "ufw not found"

  if ufw_supports_comment; then
    UFW_HAS_COMMENT=1
  else
    UFW_HAS_COMMENT=0
    log "ufw: WARN 'comment' not supported; managed rules will be enforced but untagged"
  fi

  log "mode: $( [ "$APPLY" -eq 1 ] && echo APPLY || echo DRY-RUN )"
  log "exposure: LAN_CIDR=${LAN_CIDR} ADMIN_IPV4=${ADMIN_IPV4}"

  # Docker checks for monitoring network (needed for 9323 rule)
  log "docker: verifying monitoring network '${MONITORING_NET_NAME}'"
  docker_network_exists "$MONITORING_NET_NAME" || die "Docker network '${MONITORING_NET_NAME}' not found. Start the stack first."

  local bridge subnet gateway
  bridge="$(docker_network_bridge_name "$MONITORING_NET_NAME")"
  subnet="$(docker_network_subnet "$MONITORING_NET_NAME")"
  gateway="$(docker_network_gateway "$MONITORING_NET_NAME")"

  [ "$bridge" = "$EXPECTED_BRIDGE_NAME" ] || die "Monitoring network bridge mismatch: expected '${EXPECTED_BRIDGE_NAME}', got '${bridge}'."
  [ "$subnet" = "$EXPECTED_SUBNET" ] || die "Monitoring network subnet mismatch: expected '${EXPECTED_SUBNET}', got '${subnet}'."
  log "docker: OK network=${MONITORING_NET_NAME} bridge=${bridge} subnet=${subnet} gateway=${gateway}"

  # Docker cleanup: remove stale networks if unused and foreign (optional)
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

  # UFW reconcile
  if ! ufw_is_active; then
    die "ufw: inactive (expected active). Enable UFW before running this script."
  fi

  log "ufw: active; backing up and reconciling rules"
  backup_ufw_status

  # Clean stale iface-based rules first (safe)
  cleanup_stale_ufw_iface_rules

  # Enforce deterministic inbound exposure rules
  enforce_inbound_exposure_policy

  # Ensure docker engine metrics allow rule exists
  ensure_ufw_rule_for_docker_engine_metrics

  log "done"
  if [ "$APPLY" -eq 0 ]; then
    log "No changes were made. Re-run with --apply to perform actions."
  fi
}

main "$@"
