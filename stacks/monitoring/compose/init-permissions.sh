#!/usr/bin/env bash
#
# Initialize permissions for monitoring data directories.
# Must run as root.
#
# Supports:
#   --check  : exit 0 if permissions OK; exit 1 if changes needed
#   (default): apply changes idempotently

set -euo pipefail

BASE_DIR="${BASE_DIR:-/srv/data/stacks/monitoring}"

log(){ echo "[$(date -Is)] $*"; }
die(){ echo "ERROR: $*" >&2; exit 2; }

require_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    die "Run as root: sudo bash stacks/monitoring/compose/init-permissions.sh"
  fi
}

# Resolve expected users/groups on this host
prom_user="nobody"
prom_group="nogroup"

graf_uid="472"
graf_gid="472"

# Some distros might not have nogroup; fall back to nobody's primary group.
resolve_nobody_group() {
  if getent group "$prom_group" >/dev/null 2>&1; then
    return 0
  fi
  prom_group="$(getent passwd "$prom_user" | awk -F: '{print $4}')"
  [[ -n "$prom_group" ]] || die "Unable to resolve group for user '$prom_user'"
}

ensure_dir() {
  local path="$1"
  mkdir -p "$path"
}

check_one() {
  local path="$1" want_user="$2" want_group="$3" want_mode="$4"

  [[ -d "$path" ]] || return 1

  local have_user have_group have_mode
  have_user="$(stat -c '%U' "$path")"
  have_group="$(stat -c '%G' "$path")"
  have_mode="$(stat -c '%a' "$path")"

  [[ "$have_user" == "$want_user" ]] || return 1
  [[ "$have_group" == "$want_group" ]] || return 1
  [[ "$have_mode" == "$want_mode" ]] || return 1

  return 0
}

main() {
  require_root
  resolve_nobody_group

  local mode="apply"
  if [[ "${1:-}" == "--check" ]]; then
    mode="check"
  elif [[ -n "${1:-}" ]]; then
    die "Unknown argument: ${1}. Supported: --check"
  fi

  local grafana_dir="$BASE_DIR/grafana"
  local alertmanager_dir="$BASE_DIR/alertmanager"
  local alertmanager_cfg_dir="$BASE_DIR/alertmanager-config"

  if [[ "$mode" == "check" ]]; then
    local ok=0
    check_one "$grafana_dir" "$graf_uid" "$graf_gid" "750" || ok=1
    check_one "$alertmanager_dir" "$prom_user" "$prom_group" "750" || ok=1
    check_one "$alertmanager_cfg_dir" "root" "root" "755" || ok=1

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

  # Grafana runs as UID/GID 472 in official image.
  chown -R "${graf_uid}:${graf_gid}" "$grafana_dir"
  chmod 0750 "$grafana_dir"
  chmod -R u+rwX,go-rwx "$grafana_dir"

  chown -R "${prom_user}:${prom_group}" "$alertmanager_dir"
  chmod 0750 "$alertmanager_dir"
  chmod -R u+rwX,go-rwx "$alertmanager_dir"

  # Rendered Alertmanager config directory (written by config-render job as root, mounted RO into alertmanager).
  chown -R root:root "$alertmanager_cfg_dir"
  chmod 0755 "$alertmanager_cfg_dir"

  log "init-permissions(apply): done"
}

main "$@"
