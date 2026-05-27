# shellcheck shell=bash
# shellcheck disable=SC2034
# Common functions for homelab backup, verification, and restore scripts.
# This file is intended to be sourced, not executed directly.

if [[ -n "${HOMELAB_BACKUP_COMMON_SH_INCLUDED:-}" ]]; then
  return 0
fi
HOMELAB_BACKUP_COMMON_SH_INCLUDED=1

# Stable exit codes from ADR-009.
readonly EX_USAGE=2
readonly EX_VERIFY=3
readonly EX_RESTORE_GUARD=4
readonly EX_GPG=5
readonly EX_ARCHIVE=6
readonly EX_DEPLOY=7

COMMON_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

# Repository and runtime defaults.
REPO_ROOT="${REPO_ROOT:-$(cd "${COMMON_SCRIPT_DIR}/../.." && pwd -P)}"
BACKUP_ROOT="${BACKUP_ROOT:-/srv/backups/homelab}"
DATA_ROOT="${DATA_ROOT:-/srv/data/stacks}"
STACK_NAME="${STACK_NAME:-monitoring}"
STACK_DATA_ROOT="${STACK_DATA_ROOT:-${DATA_ROOT}/${STACK_NAME}}"
COMPOSE_FILE="${COMPOSE_FILE:-${REPO_ROOT}/stacks/${STACK_NAME}/compose/docker-compose.yml}"
SECRETS_FILE="${SECRETS_FILE:-/etc/raspberry-pi-homelab/monitoring.env}"
HOST_SECRETS_DIR="${HOST_SECRETS_DIR:-/etc/raspberry-pi-homelab}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
BACKUP_SIZE_THRESHOLD_BYTES="${BACKUP_SIZE_THRESHOLD_BYTES:-536870912000}"
BACKUP_MAX_AGE_HOURS="${BACKUP_MAX_AGE_HOURS:-36}"
BACKUP_QUIESCE="${BACKUP_QUIESCE:-1}"
BACKUP_INCLUDE_METRICS="${BACKUP_INCLUDE_METRICS:-1}"
BACKUP_INCLUDE_LOGS="${BACKUP_INCLUDE_LOGS:-1}"
BACKUP_INCLUDE_SSH_HOST_KEYS="${BACKUP_INCLUDE_SSH_HOST_KEYS:-1}"
GPG_HOME="${GPG_HOME:-/var/lib/homelab-backup/gnupg}"
GPG_PUBLIC_KEY_FILE="${GPG_PUBLIC_KEY_FILE:-${REPO_ROOT}/config/backup/homelab-backup-recovery-public.asc}"
GPG_FINGERPRINT_FILE="${GPG_FINGERPRINT_FILE:-${REPO_ROOT}/config/backup/homelab-backup-recovery-public.fingerprint}"
GPG_PRIVATE_KEY_DIR="${GPG_PRIVATE_KEY_DIR:-${REPO_ROOT}/secrets/backup/gpg}"
LOCK_FILE="${LOCK_FILE:-/run/lock/homelab-backup.lock}"

RESTORE_APPLY="${RESTORE_APPLY:-0}"
RESTORE_COMPONENTS="${RESTORE_COMPONENTS:-all}"
RESTORE_SECRETS="${RESTORE_SECRETS:-1}"
RESTORE_DATA="${RESTORE_DATA:-1}"
RESTORE_SSH_HOST_KEYS="${RESTORE_SSH_HOST_KEYS:-0}"
RESTORE_MACHINE_ID="${RESTORE_MACHINE_ID:-0}"
RESTORE_REMOTE_REPO_ROOT="${RESTORE_REMOTE_REPO_ROOT:-~/iac/raspberry-pi-homelab}"

log() {
  printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

warn() {
  printf '[%s] WARN: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" >&2
}

die() {
  local code="$1"
  shift
  printf 'ERROR: %s\n' "$*" >&2
  exit "$code"
}

require_cmd() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 || die "$EX_USAGE" "required command not found: $cmd"
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

is_raspberry_pi() {
  grep -qi raspberry /proc/device-tree/model 2>/dev/null
}

is_wsl() {
  grep -qi microsoft /proc/version 2>/dev/null
}

require_pi_or_override() {
  if is_raspberry_pi; then
    return 0
  fi
  if [[ "${HOMELAB_ALLOW_NON_PI:-0}" == "1" ]]; then
    warn "HOMELAB_ALLOW_NON_PI=1 set; allowing non-Pi execution for tests"
    return 0
  fi
  die "$EX_USAGE" "this operation must run on the Raspberry Pi unless HOMELAB_ALLOW_NON_PI=1 is set"
}

should_use_sudo() {
  if [[ "${HOMELAB_ALLOW_NON_PI:-0}" == "1" && "${BACKUP_USE_SUDO:-0}" != "1" ]]; then
    return 1
  fi
  [[ "${EUID}" -ne 0 ]] && have_cmd sudo
}

sudo_run() {
  if should_use_sudo; then
    sudo "$@"
  else
    "$@"
  fi
}

sudo_env_run() {
  if should_use_sudo; then
    sudo env "$@"
  else
    env "$@"
  fi
}

sudo_test() {
  if should_use_sudo; then
    sudo test "$@"
  else
    test "$@"
  fi
}

sudo_stat() {
  local fmt="$1"
  local path="$2"
  if should_use_sudo; then
    sudo stat -c "$fmt" -- "$path"
  else
    stat -c "$fmt" -- "$path"
  fi
}

ensure_runner_dir() {
  local dir="$1"
  local mode="${2:-0750}"
  if mkdir -p "$dir" 2>/dev/null; then
    chmod "$mode" "$dir" 2>/dev/null || true
    return 0
  fi
  if ! have_cmd sudo; then
    die "$EX_USAGE" "cannot create directory and sudo is unavailable: $dir"
  fi
  sudo install -d -m "$mode" -o "$(id -u)" -g "$(id -g)" "$dir"
}

normalize_artifact_permissions() {
  local path="$1"
  chmod 0640 "$path" 2>/dev/null || true
  if [[ "${EUID}" -eq 0 ]]; then
    return 0
  fi
  if should_use_sudo; then
    sudo chown "$(id -u):$(id -g)" "$path" 2>/dev/null || true
    sudo chmod 0640 "$path" 2>/dev/null || true
  fi
}

acquire_lock() {
  if [[ "${BACKUP_SKIP_LOCK:-0}" == "1" || "${HOMELAB_BACKUP_LOCK_HELD:-0}" == "1" ]]; then
    return 0
  fi
  require_cmd flock
  local lock_file="$LOCK_FILE"
  local lock_dir
  lock_dir="$(dirname "$lock_file")"
  if [[ ! -d "$lock_dir" ]]; then
    if [[ "${HOMELAB_ALLOW_NON_PI:-0}" == "1" ]]; then
      lock_file="${BACKUP_ROOT}/.homelab-backup.lock"
      lock_dir="$(dirname "$lock_file")"
      mkdir -p "$lock_dir"
    else
      die "$EX_USAGE" "lock directory missing: $lock_dir"
    fi
  fi
  exec 200>"$lock_file" || die "$EX_USAGE" "cannot open lock file: $lock_file"
  flock -n 200 || die "$EX_USAGE" "another backup, verification, or restore process is active: $lock_file"
  export HOMELAB_BACKUP_LOCK_HELD=1
}

normalize_fingerprint() {
  printf '%s' "$1" | tr -d '[:space:]' | tr '[:lower:]' '[:upper:]'
}

load_gpg_recipient_fingerprint() {
  if [[ -z "${GPG_RECIPIENT_FINGERPRINT:-}" && -f "$GPG_FINGERPRINT_FILE" ]]; then
    GPG_RECIPIENT_FINGERPRINT="$(normalize_fingerprint "$(cat "$GPG_FINGERPRINT_FILE")")"
  else
    GPG_RECIPIENT_FINGERPRINT="$(normalize_fingerprint "${GPG_RECIPIENT_FINGERPRINT:-}")"
  fi
  if [[ ! "$GPG_RECIPIENT_FINGERPRINT" =~ ^[0-9A-F]{40}$ ]]; then
    die "$EX_GPG" "GPG_RECIPIENT_FINGERPRINT must be a full 40-hex OpenPGP fingerprint"
  fi
  export GPG_RECIPIENT_FINGERPRINT
}

gpg_public_key_fingerprint_from_file() {
  local key_file="$1"
  gpg --batch --show-keys --with-colons "$key_file" 2>/dev/null \
    | awk -F: '$1 == "fpr" { print toupper($10); exit }'
}

gpg_public_keyids_from_file() {
  local key_file="$1"
  gpg --batch --show-keys --with-colons --keyid-format LONG "$key_file" 2>/dev/null \
    | awk -F: '$1 == "pub" || $1 == "sub" { print toupper($5) }'
}

ensure_gpg_public_key_installed() {
  require_cmd gpg
  load_gpg_recipient_fingerprint

  [[ -f "$GPG_PUBLIC_KEY_FILE" ]] || die "$EX_GPG" "GPG public key file missing: $GPG_PUBLIC_KEY_FILE"

  local actual_fpr
  actual_fpr="$(gpg_public_key_fingerprint_from_file "$GPG_PUBLIC_KEY_FILE")"
  if [[ "$actual_fpr" != "$GPG_RECIPIENT_FINGERPRINT" ]]; then
    die "$EX_GPG" "backup public key fingerprint mismatch; expected $GPG_RECIPIENT_FINGERPRINT, actual ${actual_fpr:-missing}"
  fi

  if should_use_sudo; then
    sudo install -d -m 0700 -o root -g root "$GPG_HOME"
  else
    install -d -m 0700 "$GPG_HOME"
  fi

  sudo_env_run GNUPGHOME="$GPG_HOME" gpg --batch --import "$GPG_PUBLIC_KEY_FILE" >/dev/null

  local imported_fpr
  imported_fpr="$(sudo_env_run GNUPGHOME="$GPG_HOME" gpg --batch --with-colons --fingerprint "$GPG_RECIPIENT_FINGERPRINT" 2>/dev/null \
    | awk -F: '$1 == "fpr" { print toupper($10); exit }')"
  if [[ "$imported_fpr" != "$GPG_RECIPIENT_FINGERPRINT" ]]; then
    die "$EX_GPG" "pinned backup public key not present in GPG_HOME: $GPG_HOME"
  fi

  ensure_no_secret_keys_in_backup_gpg_home
}

ensure_no_secret_keys_in_backup_gpg_home() {
  local secret_count
  secret_count="$(sudo_env_run GNUPGHOME="$GPG_HOME" gpg --batch --with-colons --list-secret-keys 2>/dev/null \
    | awk -F: '$1 == "sec" || $1 == "ssb" { c++ } END { print c + 0 }')"
  if [[ "$secret_count" != "0" ]]; then
    die "$EX_GPG" "GPG_HOME must contain public keys only; secret keys found in $GPG_HOME"
  fi
}

gpg_encrypt_stdin_to_file() {
  local output_file="$1"
  load_gpg_recipient_fingerprint
  sudo_env_run GNUPGHOME="$GPG_HOME" gpg \
    --batch \
    --yes \
    --trust-model always \
    --encrypt \
    --recipient "$GPG_RECIPIENT_FINGERPRINT" \
    --output "$output_file"
  normalize_artifact_permissions "$output_file"
}

gpg_list_packets() {
  local artifact="$1"
  if [[ -d "$GPG_HOME" ]]; then
    sudo_env_run GNUPGHOME="$GPG_HOME" gpg --batch --list-packets "$artifact" >/dev/null
  else
    gpg --batch --list-packets "$artifact" >/dev/null
  fi
}

gpg_decrypt_to_tar_list() {
  local artifact="$1"
  gpg --batch --decrypt "$artifact" | zstd -d | tar -tf -
}

require_gpg_secret_key_available() {
  load_gpg_recipient_fingerprint
  if ! gpg --batch --with-colons --list-secret-keys "$GPG_RECIPIENT_FINGERPRINT" 2>/dev/null \
      | awk -F: '$1 == "sec" || $1 == "ssb" { found = 1 } END { exit found ? 0 : 1 }'; then
    die "$EX_GPG" "private backup key not available in the current user's GnuPG keyring for fingerprint $GPG_RECIPIENT_FINGERPRINT"
  fi
}

validate_member_list_file() {
  local list_file="$1"
  python3 - "$list_file" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
errors = []
for idx, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
    name = raw.strip()
    if not name:
        errors.append(f"line {idx}: empty archive member")
        continue
    p = pathlib.PurePosixPath(name)
    if name.startswith("/"):
        errors.append(f"line {idx}: absolute archive member: {name}")
    if ".." in p.parts:
        errors.append(f"line {idx}: path traversal archive member: {name}")
if errors:
    print("\n".join(errors), file=sys.stderr)
    sys.exit(1)
PY
}

json_array_from_file() {
  local file="$1"
  python3 - "$file" <<'PY'
import json
import pathlib
import sys
path = pathlib.Path(sys.argv[1])
if not path.exists():
    print("[]")
else:
    print(json.dumps(path.read_text(encoding="utf-8").splitlines()))
PY
}

select_backup_dir() {
  if [[ -n "${RESTORE_BACKUP:-}" ]]; then
    if [[ -d "$RESTORE_BACKUP" ]]; then
      printf '%s\n' "$RESTORE_BACKUP"
      return 0
    fi
    if [[ -d "${BACKUP_ROOT}/${RESTORE_BACKUP}" ]]; then
      printf '%s\n' "${BACKUP_ROOT}/${RESTORE_BACKUP}"
      return 0
    fi
    die "$EX_USAGE" "RESTORE_BACKUP does not identify a backup directory: $RESTORE_BACKUP"
  fi

  if [[ -n "${BACKUP_DIR:-}" ]]; then
    if [[ -d "$BACKUP_DIR" ]]; then
      printf '%s\n' "$BACKUP_DIR"
      return 0
    fi
    die "$EX_USAGE" "BACKUP_DIR does not identify a backup directory: $BACKUP_DIR"
  fi

  [[ -d "$BACKUP_ROOT" ]] || die "$EX_USAGE" "backup root does not exist: $BACKUP_ROOT"
  local latest
  latest="$(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -name '20*T*Z' -printf '%f\n' 2>/dev/null | sort | tail -n 1)"
  [[ -n "$latest" ]] || die "$EX_USAGE" "no timestamped backup directories found under $BACKUP_ROOT"
  printf '%s\n' "${BACKUP_ROOT}/${latest}"
}

safe_relpath() {
  local path="$1"
  local root="$2"
  python3 - "$path" "$root" <<'PY'
import os
import sys
print(os.path.relpath(sys.argv[1], sys.argv[2]))
PY
}

shell_quote() {
  printf '%q' "$1"
}

write_status_json() {
  local backup_dir="$1"
  local result="$2"
  local warnings_file="$3"
  local errors_file="$4"
  local status_dir="${BACKUP_ROOT}/status"
  ensure_runner_dir "$status_dir" 0750

  local latest_json="${status_dir}/latest.json"
  python3 - "$backup_dir" "$result" "$warnings_file" "$errors_file" "$latest_json" <<'PY'
import json
import pathlib
import sys
from datetime import datetime, timezone

backup_dir = pathlib.Path(sys.argv[1])
result = sys.argv[2]
warnings_file = pathlib.Path(sys.argv[3])
errors_file = pathlib.Path(sys.argv[4])
out = pathlib.Path(sys.argv[5])
manifest_path = backup_dir / "manifest.json"
backup_id = backup_dir.name
if manifest_path.exists():
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        backup_id = manifest.get("backup_id", backup_id)
    except Exception:
        pass

def lines(path: pathlib.Path) -> list[str]:
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line]

payload = {
    "checked_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "backup_id": backup_id,
    "backup_dir": str(backup_dir),
    "result": result,
    "warnings": lines(warnings_file),
    "errors": lines(errors_file),
}
out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

  cp "$latest_json" "${status_dir}/latest-${result}.json"
  if [[ "$result" == "ok" ]]; then
    cp "$latest_json" "${status_dir}/latest-success.json"
  else
    cp "$latest_json" "${status_dir}/latest-failure.json"
  fi
}
