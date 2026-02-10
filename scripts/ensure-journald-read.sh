#!/usr/bin/env bash
set -euo pipefail

# Ensure stable journald read access for a non-root principal.
# Idempotent: safe to run on every deploy.

TARGET_USER="${TARGET_USER:-vector}"   # host user to grant journal read access
MODE="${1:-apply}"                     # apply|check

die(){ echo "ERROR: $*" >&2; exit 2; }
log(){ echo "[ensure-journald-read] $*" >&2; }

require_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    die "Run as root (sudo)."
  fi
}

ensure_group_exists() {
  if ! getent group systemd-journal >/dev/null; then
    log "group systemd-journal missing; creating as system group"
    groupadd --system systemd-journal
  fi
}

journal_gid() {
  getent group systemd-journal | awk -F: '{print $3}'
}

user_exists() {
  id -u "$TARGET_USER" >/dev/null 2>&1
}

user_in_group() {
  id -nG "$TARGET_USER" | tr ' ' '\n' | grep -qx systemd-journal
}

fix_journal_dir_perms() {
  # journald uses /run/log/journal (volatile) and /var/log/journal (persistent) if it exists at boot
  # We only adjust perms if these dirs exist (don’t force persistence here).
  local d
  for d in /run/log/journal /var/log/journal; do
    [[ -d "$d" ]] || continue

    # Ensure expected group ownership and readable/enterable by group.
    # Keep it conservative: don't open write perms.
    chgrp -R systemd-journal "$d" || true
    chmod g+rx "$d" || true
    find "$d" -type d -exec chmod g+rx {} + || true
  done
}

check_only() {
  local gid
  gid="$(journal_gid)"

  [[ -n "$gid" ]] || die "Could not determine systemd-journal GID"
  user_exists || die "User not found: TARGET_USER=$TARGET_USER"
  user_in_group || die "User $TARGET_USER is NOT in group systemd-journal"

  # If present, ensure dirs are traversable by group (minimum for reads).
  for d in /run/log/journal /var/log/journal; do
    [[ -d "$d" ]] || continue
    local g m
    g="$(stat -c '%G' "$d")"
    m="$(stat -c '%a' "$d")"
    [[ "$g" == "systemd-journal" ]] || die "$d group is $g (expected systemd-journal)"
    # require at least group execute bit so group members can traverse
    [[ "$m" =~ [0-7][0-7][1-7]$ ]] || die "$d mode=$m does not allow group traverse"
  done

  echo "SYSTEMD_JOURNAL_GID=$gid"
}

apply() {
  ensure_group_exists
  local gid
  gid="$(journal_gid)"
  [[ -n "$gid" ]] || die "Could not determine systemd-journal GID"

  user_exists || die "User not found: TARGET_USER=$TARGET_USER"

  if user_in_group; then
    log "user $TARGET_USER already in systemd-journal"
  else
    log "adding user $TARGET_USER to systemd-journal"
    usermod -a -G systemd-journal "$TARGET_USER"
  fi

  fix_journal_dir_perms

  echo "SYSTEMD_JOURNAL_GID=$gid"
}

main() {
  require_root
  case "$MODE" in
    check) check_only ;;
    apply) apply ;;
    *) die "Usage: $0 [apply|check] (or set MODE via arg). Got: $MODE" ;;
  esac
}

main
