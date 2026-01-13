# Script to initialize permissions for monitoring data directories

# Note: The script must be run as root to change ownership of directories: 
#       In generals, this is established by being called from the sudo context of deploy.sh

#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="${BASE_DIR:-/srv/data/monitoring}"

log(){ echo "[$(date -Is)] $*"; }
die(){ echo "ERROR: $*" >&2; exit 2; }

# Ensure the script is run as root
require_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    die "Run as root: sudo bash monitoring/compose/init-permissions.sh"
  fi
}

main() {
  require_root

  log "Initializing permissions under: $BASE_DIR"

  mkdir -p \
    "$BASE_DIR/grafana" \
    "$BASE_DIR/prometheus" \
    "$BASE_DIR/alertmanager"

  # UIDs used by images (matches comments/intent)
  # - Grafana typically runs as 472
  # - Prometheus/Alertmanager often run as nobody (65534)
  chown -R 472:472 "$BASE_DIR/grafana"
  chown -R 65534:65534 "$BASE_DIR/prometheus"
  chown -R 65534:65534 "$BASE_DIR/alertmanager"

  chmod -R u+rwX,go-rwx "$BASE_DIR"

  log "Permissions initialized under $BASE_DIR"
}

main "$@"

