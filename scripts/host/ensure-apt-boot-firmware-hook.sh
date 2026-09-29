#!/usr/bin/env bash
# Install the APT hook for the read-only /boot/firmware (F60, ADR-0013). deploy.sh runs `apply`;
# tests/postdeploy/test_06_host_boot_firmware.py runs `check`.
#
#   apply  install the helper, then the apt.conf snippet, when content, mode or owner differ
#   check  exit 2 on any drift from the repository
#
# The helper is installed first, so the snippet never calls a missing file.
set -euo pipefail

log() { echo "[$(date -Is)] $*"; }
die() {
  echo "ERROR: $*" >&2
  exit 2
}

# scripts/host/ensure-apt-boot-firmware-hook.sh -> REPO_ROOT is 2 levels up
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

HELPER_SRC="${HELPER_SRC:-$REPO_ROOT/scripts/host/homelab-boot-firmware.sh}"
HELPER_DST="${HELPER_DST:-/usr/local/sbin/homelab-boot-firmware}"
APT_HOOK_SRC="${APT_HOOK_SRC:-$REPO_ROOT/stacks/core/apt/99homelab-boot-firmware}"
APT_HOOK_DST="${APT_HOOK_DST:-/etc/apt/apt.conf.d/99homelab-boot-firmware}"

# Test override (tests/guards/test_55): no root check and no ownership, but only when every
# destination resolves to a path inside the sandbox directory.
SANDBOX="${HOMELAB_TEST_SANDBOX:-}"

guard_destinations() {
  if [[ -z "$SANDBOX" ]]; then
    [[ "${EUID:-$(id -u)}" -eq 0 ]] || die "Please run with sudo/root"
    return 0
  fi
  [[ -d "$SANDBOX" ]] || die "HOMELAB_TEST_SANDBOX is not a directory: $SANDBOX"
  local root dst
  root="$(realpath -e -- "$SANDBOX")"
  [[ "$root" != "/" ]] || die "HOMELAB_TEST_SANDBOX must not be /"
  for dst in "$HELPER_DST" "$APT_HOOK_DST"; do
    [[ "$(realpath -m -- "$dst")" == "$root"/* ]] ||
      die "destination outside HOMELAB_TEST_SANDBOX: $dst"
  done
}

# in_sync <src> <dst> <mode>
in_sync() {
  local src="$1" dst="$2" mode="$3"
  [[ -f "$dst" ]] || return 1
  cmp -s "$src" "$dst" || return 1
  [[ "$(stat -c %a "$dst")" == "$mode" ]] || return 1
  if [[ -z "$SANDBOX" ]]; then
    [[ "$(stat -c %u:%g "$dst")" == "0:0" ]] || return 1
  fi
  return 0
}

pairs() {
  printf '%s\n' "$HELPER_SRC|$HELPER_DST|755" "$APT_HOOK_SRC|$APT_HOOK_DST|644"
}

require_sources() {
  [[ -f "$HELPER_SRC" ]] || die "source missing: $HELPER_SRC"
  [[ -f "$APT_HOOK_SRC" ]] || die "source missing: $APT_HOOK_SRC"
}

apply() {
  guard_destinations
  require_sources
  local src dst mode changed=0
  local owner=(-o root -g root)
  [[ -z "$SANDBOX" ]] || owner=()
  while IFS='|' read -r src dst mode; do
    in_sync "$src" "$dst" "$mode" && continue
    log "apt-boot-firmware: installing $dst (mode $mode) from $src"
    [[ -d "$(dirname "$dst")" ]] || install -d -m 755 "$(dirname "$dst")"
    install -m "$mode" "${owner[@]}" "$src" "$dst"
    changed=1
  done < <(pairs)
  if [[ "$changed" -eq 0 ]]; then
    log "apt-boot-firmware: OK (no changes)"
  else
    log "apt-boot-firmware: updated"
  fi
}

check() {
  require_sources
  local src dst mode
  while IFS='|' read -r src dst mode; do
    in_sync "$src" "$dst" "$mode" ||
      die "apt-boot-firmware: DRIFT detected: $dst differs from $src (content, mode $mode or owner)"
  done < <(pairs)
  log "apt-boot-firmware: OK (in sync)"
}

usage() {
  cat <<EOF
Usage: $(basename "$0") <apply|check>

Env overrides:
  HELPER_SRC, HELPER_DST, APT_HOOK_SRC, APT_HOOK_DST
  HOMELAB_TEST_SANDBOX (tests only; every destination must lie inside it)
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
