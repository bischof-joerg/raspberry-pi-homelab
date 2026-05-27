#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=scripts/backup/common.sh
source "${SCRIPT_DIR}/common.sh"

BACKUP_VERIFY_DECRYPT="${BACKUP_VERIFY_DECRYPT:-0}"
BACKUP_VERIFY_PRUNE="${BACKUP_VERIFY_PRUNE:-0}"
BACKUP_VERIFY_ENFORCE_FRESHNESS="${BACKUP_VERIFY_ENFORCE_FRESHNESS:-0}"
WARNINGS_FILE=""
ERRORS_FILE=""
SELECTED_BACKUP_DIR=""
VERIFY_LOG=""

add_warning() {
  printf '%s\n' "$*" >>"$WARNINGS_FILE"
  warn "$*"
}

add_error() {
  printf '%s\n' "$*" >>"$ERRORS_FILE"
  printf 'ERROR: %s\n' "$*" >&2
}

usage() {
  cat <<'USAGE'
Usage: backup-verify.sh [--decrypt] [--artifact-only]

Environment:
  BACKUP_DIR=/path/to/backup       Verify this backup directory.
  RESTORE_BACKUP=/path/or/id       Verify this restore source.
  BACKUP_VERIFY_DECRYPT=1          Decrypt, decompress, and list archives. Requires private key.
  BACKUP_VERIFY_PRUNE=1            Prune old backups after successful verification.
USAGE
}

parse_args() {
  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      --decrypt)
        BACKUP_VERIFY_DECRYPT=1
        ;;
      --artifact-only)
        BACKUP_VERIFY_DECRYPT=0
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "$EX_USAGE" "unknown argument: $1"
        ;;
    esac
    shift
  done
}

validate_manifest() {
  local manifest="${SELECTED_BACKUP_DIR}/manifest.json"
  [[ -f "$manifest" ]] || { add_error "manifest.json missing"; return 1; }
  if ! python3 -m json.tool "$manifest" >/dev/null; then
    add_error "manifest.json is not valid JSON"
    return 1
  fi
  if ! python3 - "$manifest" <<'PY'
import json
import sys
from pathlib import Path

required = [
    "schema_version",
    "created_at_utc",
    "hostname",
    "backup_root",
    "backup_id",
    "secrets_file",
    "data_root",
    "archives",
    "encrypted_archives",
]
manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
missing = [key for key in required if key not in manifest]
if missing:
    print("missing required manifest keys: " + ", ".join(missing), file=sys.stderr)
    sys.exit(1)
if not isinstance(manifest.get("archives"), list) or not isinstance(manifest.get("encrypted_archives"), list):
    print("manifest archives fields must be arrays", file=sys.stderr)
    sys.exit(1)
PY
  then
    add_error "manifest.json failed required-key validation"
    return 1
  fi
}

validate_checksums() {
  [[ -f "${SELECTED_BACKUP_DIR}/checksums.sha256" ]] || { add_error "checksums.sha256 missing"; return 1; }
  if ! (cd "$SELECTED_BACKUP_DIR" && sha256sum -c checksums.sha256); then
    add_error "checksum validation failed"
    return 1
  fi
}

manifest_encrypted_archives() {
  python3 - "${SELECTED_BACKUP_DIR}/manifest.json" <<'PY'
import json
import sys
from pathlib import Path
manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for item in manifest.get("encrypted_archives", []):
    print(item)
PY
}

validate_archive_members_json() {
  local members_json="${SELECTED_BACKUP_DIR}/host/archive-members.json"
  if [[ ! -f "$members_json" ]]; then
    add_warning "host/archive-members.json missing; cannot validate pre-encryption member inventory"
    return 0
  fi
  if ! python3 - "$members_json" <<'PY'
import json
import pathlib
import sys

payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
errors = []
for artifact, members in payload.items():
    if not isinstance(members, list):
        errors.append(f"{artifact}: member list is not an array")
        continue
    for member in members:
        if not isinstance(member, str) or not member:
            errors.append(f"{artifact}: empty or non-string archive member")
            continue
        p = pathlib.PurePosixPath(member)
        if member.startswith("/"):
            errors.append(f"{artifact}: absolute archive member: {member}")
        if ".." in p.parts:
            errors.append(f"{artifact}: path traversal archive member: {member}")
if errors:
    print("\n".join(errors), file=sys.stderr)
    sys.exit(1)
PY
  then
    add_error "unsafe archive member detected in host/archive-members.json"
    return 1
  fi
}

validate_gpg_packets_and_recipients() {
  local expected_keyids=()
  if [[ -f "$GPG_PUBLIC_KEY_FILE" ]]; then
    mapfile -t expected_keyids < <(gpg_public_keyids_from_file "$GPG_PUBLIC_KEY_FILE" | sort -u)
  fi

  local rel artifact packets matched keyid
  while IFS= read -r rel; do
    [[ -n "$rel" ]] || continue
    artifact="${SELECTED_BACKUP_DIR}/${rel}"
    if [[ ! -s "$artifact" ]]; then
      add_error "encrypted artifact missing or empty: $rel"
      continue
    fi
    packets="$(if [[ -d "$GPG_HOME" ]]; then sudo_env_run GNUPGHOME="$GPG_HOME" gpg --batch --list-packets "$artifact" 2>&1 || true; else gpg --batch --list-packets "$artifact" 2>&1 || true; fi)"
    if ! grep -Eiq 'pubkey enc packet|encrypted data packet' <<<"$packets"; then
      add_error "OpenPGP packet validation failed: $rel"
      continue
    fi

    if [[ "${#expected_keyids[@]}" -gt 0 ]]; then
      matched=0
      for keyid in "${expected_keyids[@]}"; do
        if grep -qi "keyid ${keyid}" <<<"$packets"; then
          matched=1
          break
        fi
      done
      if [[ "$matched" == "0" ]]; then
        add_warning "could not match visible packet key ID to pinned public key for $rel; full fingerprint is not always exposed in packet metadata"
      fi
    fi
  done < <(manifest_encrypted_archives)
}

validate_decrypt_and_tar_lists() {
  require_gpg_secret_key_available
  local rel artifact list_file
  while IFS= read -r rel; do
    [[ -n "$rel" ]] || continue
    artifact="${SELECTED_BACKUP_DIR}/${rel}"
    list_file="$(mktemp)"
    if ! gpg --batch --decrypt "$artifact" | zstd -d | tar -tf - >"$list_file"; then
      rm -f "$list_file"
      add_error "decrypt/decompress/tar-list failed: $rel"
      continue
    fi
    if ! validate_member_list_file "$list_file"; then
      rm -f "$list_file"
      add_error "unsafe archive member after decrypt/list: $rel"
      continue
    fi
    rm -f "$list_file"
  done < <(manifest_encrypted_archives)
}

validate_size_threshold() {
  local size
  size="$(du -sb "$BACKUP_ROOT" 2>/dev/null | awk '{ print $1 + 0 }')"
  if [[ -n "$size" && "$size" -gt "$BACKUP_SIZE_THRESHOLD_BYTES" ]]; then
    add_error "backup root exceeds threshold: size=${size} threshold=${BACKUP_SIZE_THRESHOLD_BYTES} path=${BACKUP_ROOT}"
  fi
}

validate_freshness() {
  local explicit=0
  [[ -n "${RESTORE_BACKUP:-}" || -n "${BACKUP_DIR:-}" ]] && explicit=1
  if [[ "$explicit" == "1" && "$BACKUP_VERIFY_ENFORCE_FRESHNESS" != "1" ]]; then
    add_warning "freshness threshold not enforced for explicitly selected backup; set BACKUP_VERIFY_ENFORCE_FRESHNESS=1 to enforce"
    return 0
  fi
  if ! python3 - "${SELECTED_BACKUP_DIR}/manifest.json" "$BACKUP_MAX_AGE_HOURS" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
max_hours = float(sys.argv[2])
created = manifest.get("created_at_utc", "")
try:
    dt = datetime.strptime(created, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
except Exception as exc:
    print(f"cannot parse created_at_utc: {created}: {exc}", file=sys.stderr)
    sys.exit(1)
age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
if age_hours > max_hours:
    print(f"backup too old: age_hours={age_hours:.2f} threshold={max_hours:.2f}", file=sys.stderr)
    sys.exit(1)
PY
  then
    add_error "backup freshness validation failed"
  fi
}

prune_old_backups() {
  [[ "$BACKUP_VERIFY_PRUNE" == "1" ]] || return 0
  local count
  count="$(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -name '20*T*Z' | wc -l | awk '{ print $1 + 0 }')"
  if [[ "$count" -le 1 ]]; then
    log "Retention prune skipped; only one backup exists"
    return 0
  fi
  log "Pruning backups older than ${BACKUP_RETENTION_DAYS} days; keeping at least latest verified backup"
  find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -name '20*T*Z' -mtime "+${BACKUP_RETENTION_DAYS}" -print \
    | sort \
    | while IFS= read -r old; do
        if [[ "$old" == "$SELECTED_BACKUP_DIR" ]]; then
          continue
        fi
        rm -rf -- "$old"
      done
}

main() {
  parse_args "$@"
  acquire_lock
  SELECTED_BACKUP_DIR="$(select_backup_dir)"
  [[ -d "$SELECTED_BACKUP_DIR" ]] || die "$EX_USAGE" "backup directory missing: $SELECTED_BACKUP_DIR"
  VERIFY_LOG="${SELECTED_BACKUP_DIR}/logs/backup-verify.log"
  mkdir -p "$(dirname "$VERIFY_LOG")"

  local tmp_dir
  tmp_dir="$(mktemp -d)"
  WARNINGS_FILE="${tmp_dir}/warnings.txt"
  ERRORS_FILE="${tmp_dir}/errors.txt"
  : >"$WARNINGS_FILE"
  : >"$ERRORS_FILE"

  exec 3>&1 4>&2
  exec > >(tee -a "$VERIFY_LOG" >&3) 2> >(tee -a "$VERIFY_LOG" >&4)

  log "Starting backup verification: $SELECTED_BACKUP_DIR"
  validate_manifest || true
  validate_checksums || true
  validate_archive_members_json || true
  validate_gpg_packets_and_recipients || true
  validate_size_threshold || true
  validate_freshness || true

  if [[ "$BACKUP_VERIFY_DECRYPT" == "1" ]]; then
    log "Running decrypt/list verification; private key is required on this host"
    validate_decrypt_and_tar_lists || true
  else
    add_warning "artifact-only verification mode; decrypt/list verification was not performed"
    if is_raspberry_pi || [[ -d "$GPG_HOME" ]]; then
      ensure_no_secret_keys_in_backup_gpg_home || add_error "Pi-side GPG_HOME contains secret keys"
    fi
  fi

  local result="ok"
  local code=0
  if [[ -s "$ERRORS_FILE" ]]; then
    result="failure"
    code="$EX_VERIFY"
  fi

  write_status_json "$SELECTED_BACKUP_DIR" "$result" "$WARNINGS_FILE" "$ERRORS_FILE"

  if [[ "$code" == "0" ]]; then
    prune_old_backups
    log "Backup verification succeeded: $SELECTED_BACKUP_DIR"
  else
    log "Backup verification failed: $SELECTED_BACKUP_DIR"
  fi

  exec >&3 2>&4
  rm -rf "$tmp_dir"
  if [[ "$code" == "0" ]]; then
    printf 'OK: backup verification succeeded: %s\n' "$SELECTED_BACKUP_DIR"
  else
    printf 'FAIL: backup verification failed: %s\n' "$SELECTED_BACKUP_DIR" >&2
  fi
  exit "$code"
}

main "$@"
