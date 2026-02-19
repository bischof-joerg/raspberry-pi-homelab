#!/usr/bin/env bash
#
# Initialize permissions for monitoring data directories.
# Must run as root.
#
# Supports:
#   --check  : exit 0 if permissions OK; exit 1 if changes needed
#   (default): apply changes idempotently
#
# Notes:
# - Grafana official image runs as UID/GID 472.
# - Vector is configured to run as a non-root UID/GID (e.g. 65532:65532) and needs a writable data_dir
#   at /var/lib/vector (we bind-mount this from $BASE_DIR/vector).
# - VictoriaMetrics / VictoriaLogs storage dirs are persisted via bind mounts.
#   Their runtime UID/GID may vary by image/tag; default here is root:root, but can be overridden via:
#     VICTORIAMETRICS_UID / VICTORIAMETRICS_GID
#     VICTORIALOGS_UID   / VICTORIALOGS_GID
#

set -euo pipefail

BASE_DIR="${BASE_DIR:-/srv/data/stacks/monitoring}"

log(){ echo "[$(date -Is)] $*"; }
die(){ echo "ERROR: $*" >&2; exit 2; }

require_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    die "Run as root: sudo bash stacks/monitoring/compose/init-permissions.sh"
  fi
}

# Resolve expected users/groups on this host (numeric ids for determinism)
prom_user="nobody"
prom_group="nogroup"
prom_uid=""
prom_gid=""

graf_uid="472"
graf_gid="472"

# Vector runs as non-root (configured in compose via user: "65532:65532")
vector_uid="65532"
vector_gid="65532"

# VictoriaMetrics / VictoriaLogs (defaults are conservative: root)
victoriametrics_uid="${VICTORIAMETRICS_UID:-0}"
victoriametrics_gid="${VICTORIAMETRICS_GID:-0}"
victorialogs_uid="${VICTORIALOGS_UID:-0}"
victorialogs_gid="${VICTORIALOGS_GID:-0}"

resolve_nobody_ids() {
  # Resolve UID
  if getent passwd "$prom_user" >/dev/null 2>&1; then
    prom_uid="$(getent passwd "$prom_user" | awk -F: '{print $3}')"
  fi
  [[ -n "$prom_uid" ]] || die "Unable to resolve UID for user '$prom_user'"

  # Resolve GID: prefer explicit group name if present, else use user's primary group id
  if getent group "$prom_group" >/dev/null 2>&1; then
    prom_gid="$(getent group "$prom_group" | awk -F: '{print $3}')"
  else
    prom_gid="$(getent passwd "$prom_user" | awk -F: '{print $4}')"
  fi
  [[ -n "$prom_gid" ]] || die "Unable to resolve GID for user '$prom_user'"
}

ensure_dir() {
  local path="$1"
  mkdir -p "$path"
}

check_one() {
  local path="$1" want_uid="$2" want_gid="$3" want_mode="$4"

  [[ -d "$path" ]] || return 1

  local have_uid have_gid have_mode
  have_uid="$(stat -c '%u' "$path")"
  have_gid="$(stat -c '%g' "$path")"
  have_mode="$(stat -c '%a' "$path")"

  [[ "$have_uid" == "$want_uid" ]] || return 1
  [[ "$have_gid" == "$want_gid" ]] || return 1
  [[ "$have_mode" == "$want_mode" ]] || return 1

  return 0
}

main() {
  require_root
  resolve_nobody_ids

  local mode="apply"
  if [[ "${1:-}" == "--check" ]]; then
    mode="check"
  elif [[ -n "${1:-}" ]]; then
    die "Unknown argument: ${1}. Supported: --check"
  fi

  local grafana_dir="$BASE_DIR/grafana"
  local alertmanager_dir="$BASE_DIR/alertmanager"
  local alertmanager_cfg_dir="$BASE_DIR/alertmanager-config"
  local vector_dir="$BASE_DIR/vector"
  local victoriametrics_dir="$BASE_DIR/victoriametrics"
  local victorialogs_dir="$BASE_DIR/victorialogs"

  if [[ "$mode" == "check" ]]; then
    local ok=0
    check_one "$grafana_dir" "$graf_uid" "$graf_gid" "750" || ok=1
    check_one "$alertmanager_dir" "$prom_uid" "$prom_gid" "750" || ok=1
    check_one "$alertmanager_cfg_dir" "0" "0" "755" || ok=1
    check_one "$vector_dir" "$vector_uid" "$vector_gid" "750" || ok=1
    check_one "$victoriametrics_dir" "$victoriametrics_uid" "$victoriametrics_gid" "750" || ok=1
    check_one "$victorialogs_dir" "$victorialogs_uid" "$victorialogs_gid" "750" || ok=1

    if [[ "$ok" -eq 0 ]]; then
      log "init-permissions(check): OK"
      exit 0
    fi
    log "init-permissions(check): needs changes"
    exit 1
  fi

  log "init-permissions(apply): base=$BASE_DIR"

  ensure_dir "$grafana_dir"
  ensure_dir "$alertmanager_dir"
  ensure_dir "$alertmanager_cfg_dir"
  ensure_dir "$vector_dir"
  ensure_dir "$victoriametrics_dir"
  ensure_dir "$victorialogs_dir"

  # Grafana runs as UID/GID 472 in official image.
  chown -R "${graf_uid}:${graf_gid}" "$grafana_dir"
  chmod 0750 "$grafana_dir"
  chmod -R u+rwX,go-rwx "$grafana_dir"

  # Alertmanager runs as nobody:nogroup (or nobody:<primary-group> on some distros).
  chown -R "${prom_uid}:${prom_gid}" "$alertmanager_dir"
  chmod 0750 "$alertmanager_dir"
  chmod -R u+rwX,go-rwx "$alertmanager_dir"

  # Rendered Alertmanager config directory (written by config-render job as root, mounted RO into alertmanager).
  chown -R 0:0 "$alertmanager_cfg_dir"
  chmod 0755 "$alertmanager_cfg_dir"

  # Vector data_dir (/var/lib/vector) bind-mounted from $BASE_DIR/vector.
  # Must be writable for non-root Vector (journald checkpoints/state, etc.).
  chown -R "${vector_uid}:${vector_gid}" "$vector_dir"
  chmod 0750 "$vector_dir"
  chmod -R u+rwX,go-rwx "$vector_dir"

  # VictoriaMetrics TSDB dir (bind-mounted to /victoria-metrics-data).
  # Default owner root:root; override via VICTORIAMETRICS_UID/GID if you run the container non-root.
  chown -R "${victoriametrics_uid}:${victoriametrics_gid}" "$victoriametrics_dir"
  chmod 0750 "$victoriametrics_dir"
  chmod -R u+rwX,go-rwx "$victoriametrics_dir"

  # VictoriaLogs storage dir (bind-mounted to /vlogs).
  # Default owner root:root; override via VICTORIALOGS_UID/GID if you run the container non-root.
  chown -R "${victorialogs_uid}:${victorialogs_gid}" "$victorialogs_dir"
  chmod 0750 "$victorialogs_dir"
  chmod -R u+rwX,go-rwx "$victorialogs_dir"

  log "init-permissions(apply): done"
}

main "$@"
