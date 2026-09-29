#!/usr/bin/env bash
# Remount /boot/firmware read-write or read-only around one dpkg run (F60, ADR-0013).
#
# scripts/host/ensure-apt-boot-firmware-hook.sh installs this file as a root-owned copy at
# /usr/local/sbin/homelab-boot-firmware; /etc/apt/apt.conf.d/99homelab-boot-firmware calls it:
#   DPkg::Pre-Invoke  -> rw
#   DPkg::Post-Invoke -> ro
# APT runs both as root, so the hook must never point into the checkout, which admin owns.
#
# Exit codes:
#   0  target state reached or already set; no firmware mount; `ro` failed (warned, see below)
#   1  `rw` failed: APT stops before dpkg instead of leaving a package half-configured
#   2  usage error
set -euo pipefail

MOUNTPOINT="${FIRMWARE_MOUNTPOINT:-/boot/firmware}"
FINDMNT_BIN="${FINDMNT_BIN:-/usr/bin/findmnt}"
MOUNT_BIN="${MOUNT_BIN:-/usr/bin/mount}"
LOGGER_BIN="${LOGGER_BIN:-/usr/bin/logger}"
TAG="homelab-boot-firmware"

log() {
  "$LOGGER_BIN" -t "$TAG" -p "user.$1" -- "$2" || true
}

usage() {
  echo "Usage: $(basename "$0") <rw|ro>" >&2
  exit 2
}

main() {
  [[ $# -eq 1 ]] || usage
  local target="$1"
  [[ "$target" == "rw" || "$target" == "ro" ]] || usage

  local options
  if ! options="$("$FINDMNT_BIN" -no OPTIONS "$MOUNTPOINT" 2>/dev/null)"; then
    return 0 # not mounted: nothing to open or to protect
  fi
  local current="${options%%,*}"
  if [[ "$current" == "$target" ]]; then
    return 0
  fi

  if "$MOUNT_BIN" -o "remount,$target" "$MOUNTPOINT"; then
    log info "remounted $MOUNTPOINT $target (was $current)"
    return 0
  fi

  if [[ "$target" == "rw" ]]; then
    log err "cannot remount $MOUNTPOINT rw; APT stops before dpkg runs (F60)"
    echo "$TAG: ERROR: cannot remount $MOUNTPOINT rw" >&2
    return 1
  fi

  # A failing DPkg::Post-Invoke fails the whole APT run - the F60 symptom. Warn instead; the
  # partition stays rw until the next APT run or reboot, and postdeploy test_06 reports it.
  log warning "cannot remount $MOUNTPOINT ro (busy?); it stays rw until the next APT run or reboot"
  echo "$TAG: WARNING: $MOUNTPOINT stays rw" >&2
  return 0
}

main "$@"
