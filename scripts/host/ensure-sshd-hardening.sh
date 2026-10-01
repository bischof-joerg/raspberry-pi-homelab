#!/usr/bin/env bash
# Install the sshd hardening drop-in (F67). deploy.sh runs `apply`;
# tests/postdeploy/test_08_host_sshd_hardening.py runs `check`.
#
#   apply  install the drop-in when content, mode or owner differ; validate the whole sshd
#          configuration with `sshd -t` and restore the previous state if it fails; only then
#          reload ssh.service (a reload keeps every open session)
#   check  exit 2 on any drift from the repository; never reloads anything
#
# Exit codes: 0 in sync or updated, 2 drift, usage error, refused destination or rejected config.
set -euo pipefail

log() { echo "[$(date -Is)] $*"; }
die() {
  echo "ERROR: $*" >&2
  exit 2
}

# scripts/host/ensure-sshd-hardening.sh -> REPO_ROOT is 2 levels up
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

DROPIN_SRC="${DROPIN_SRC:-$REPO_ROOT/stacks/core/ssh/10-homelab-hardening.conf}"
DROPIN_DST="${DROPIN_DST:-/etc/ssh/sshd_config.d/10-homelab-hardening.conf}"
SSHD_BIN="${SSHD_BIN:-/usr/sbin/sshd}"
SYSTEMCTL_BIN="${SYSTEMCTL_BIN:-/usr/bin/systemctl}"
SSH_UNIT="ssh.service"
MODE=644

# Test override (tests/guards/test_61): no root check and no ownership, but only when the
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
    log "sshd-hardening: OK (no changes)"
    return 0
  fi
  [[ -x "$SSHD_BIN" ]] || die "sshd not found: $SSHD_BIN"

  local backup had_previous=0
  backup="$(mktemp -d)"
  # shellcheck disable=SC2064 # expand now: the trap must remove this directory
  trap "rm -rf -- '$backup'" EXIT
  if [[ -e "$DROPIN_DST" ]]; then
    cp -p -- "$DROPIN_DST" "$backup/previous"
    had_previous=1
  fi

  local owner=(-o root -g root)
  [[ -z "$SANDBOX" ]] || owner=()
  log "sshd-hardening: installing $DROPIN_DST (mode $MODE) from $DROPIN_SRC"
  [[ -d "$(dirname "$DROPIN_DST")" ]] || install -d -m 755 "$(dirname "$DROPIN_DST")"
  install -m "$MODE" "${owner[@]}" "$DROPIN_SRC" "$DROPIN_DST"

  # Never reload with a configuration sshd rejects: a broken sshd locks the operator out.
  if ! "$SSHD_BIN" -t; then
    if [[ "$had_previous" -eq 1 ]]; then
      cp -p -- "$backup/previous" "$DROPIN_DST"
    else
      rm -f -- "$DROPIN_DST"
    fi
    die "sshd-hardening: sshd -t rejected the configuration; previous state restored, nothing reloaded"
  fi

  if "$SYSTEMCTL_BIN" is-active --quiet "$SSH_UNIT"; then
    log "sshd-hardening: reloading $SSH_UNIT"
    "$SYSTEMCTL_BIN" reload "$SSH_UNIT"
  else
    log "sshd-hardening: $SSH_UNIT not active; the next sshd start reads the drop-in"
  fi
  log "sshd-hardening: updated"
}

check() {
  require_source
  in_sync ||
    die "sshd-hardening: DRIFT detected: $DROPIN_DST differs from $DROPIN_SRC (content, mode $MODE or owner)"
  log "sshd-hardening: OK (in sync)"
}

usage() {
  cat <<EOF
Usage: $(basename "$0") <apply|check>

Env overrides:
  DROPIN_SRC, DROPIN_DST, SSHD_BIN, SYSTEMCTL_BIN
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
