#!/usr/bin/env bash
# Install the persistent-journal drop-in (F62). deploy.sh runs `apply`;
# tests/postdeploy/test_07_host_journald_persistent.py runs `check`.
#
#   apply  install the drop-in when content, mode or owner differ; only then restart journald and
#          flush the runtime journal to /var/log/journal
#   check  exit 2 on any drift from the repository; never restarts anything
#
# Exit codes: 0 in sync or updated, 2 drift, usage error or refused destination.
set -euo pipefail

log() { echo "[$(date -Is)] $*"; }
die() {
  echo "ERROR: $*" >&2
  exit 2
}

# scripts/host/ensure-journald-persistent.sh -> REPO_ROOT is 2 levels up
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

DROPIN_SRC="${DROPIN_SRC:-$REPO_ROOT/stacks/core/journald/60-homelab-persistent.conf}"
DROPIN_DST="${DROPIN_DST:-/etc/systemd/journald.conf.d/60-homelab-persistent.conf}"
SYSTEMCTL_BIN="${SYSTEMCTL_BIN:-/usr/bin/systemctl}"
JOURNALCTL_BIN="${JOURNALCTL_BIN:-/usr/bin/journalctl}"
MODE=644

# Test override (tests/guards/test_57): no root check and no ownership, but only when the
# destination resolves to a path inside the sandbox directory.
SANDBOX="${HOMELAB_TEST_SANDBOX:-}"

guard_destination() {
  if [[ -z "$SANDBOX" ]]; then
    [[ "${EUID:-$(id -u)}" -eq 0 ]] || die "Please run with sudo/root"
    return 0
  fi
  [[ -d "$SANDBOX" ]] || die "HOMELAB_TEST_SANDBOX is not a directory: $SANDBOX"
  local root
  root="$(realpath -e -- "$SANDBOX")"
  [[ "$root" != "/" ]] || die "HOMELAB_TEST_SANDBOX must not be /"
  [[ "$(realpath -m -- "$DROPIN_DST")" == "$root"/* ]] ||
    die "destination outside HOMELAB_TEST_SANDBOX: $DROPIN_DST"
}

in_sync() {
  [[ -f "$DROPIN_DST" ]] || return 1
  cmp -s "$DROPIN_SRC" "$DROPIN_DST" || return 1
  [[ "$(stat -c %a "$DROPIN_DST")" == "$MODE" ]] || return 1
  if [[ -z "$SANDBOX" ]]; then
    [[ "$(stat -c %u:%g "$DROPIN_DST")" == "0:0" ]] || return 1
  fi
  return 0
}

require_source() {
  [[ -f "$DROPIN_SRC" ]] || die "source missing: $DROPIN_SRC"
}

apply() {
  guard_destination
  require_source
  if in_sync; then
    log "journald-persistent: OK (no changes)"
    return 0
  fi
  local owner=(-o root -g root)
  [[ -z "$SANDBOX" ]] || owner=()
  log "journald-persistent: installing $DROPIN_DST (mode $MODE) from $DROPIN_SRC"
  [[ -d "$(dirname "$DROPIN_DST")" ]] || install -d -m 755 "$(dirname "$DROPIN_DST")"
  install -m "$MODE" "${owner[@]}" "$DROPIN_SRC" "$DROPIN_DST"
  # journald reads its configuration only at start; the flush moves the runtime journal from
  # /run/log/journal to /var/log/journal, so the current boot is kept as well.
  log "journald-persistent: restarting systemd-journald"
  "$SYSTEMCTL_BIN" restart systemd-journald
  "$JOURNALCTL_BIN" --flush
  log "journald-persistent: updated"
}

check() {
  require_source
  in_sync ||
    die "journald-persistent: DRIFT detected: $DROPIN_DST differs from $DROPIN_SRC (content, mode $MODE or owner)"
  log "journald-persistent: OK (in sync)"
}

usage() {
  cat <<EOF
Usage: $(basename "$0") <apply|check>

Env overrides:
  DROPIN_SRC, DROPIN_DST, SYSTEMCTL_BIN, JOURNALCTL_BIN
  HOMELAB_TEST_SANDBOX (tests only; the destination must lie inside it)
EOF
}

main() {
  case "${1:-}" in
    apply) apply ;;
    check) check ;;
    *)
      usage
      exit 2
      ;;
  esac
}

main "$@"
