#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=scripts/backup/common.sh
source "${SCRIPT_DIR}/common.sh"

BACKUP_ID="${BACKUP_ID:-$(date -u +'%Y-%m-%dT%H%M%SZ')}"
CREATED_AT_UTC="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
BACKUP_DIR="${BACKUP_DIR:-${BACKUP_ROOT}/${BACKUP_ID}}"
LOG_FILE="${BACKUP_DIR}/logs/backup.log"
STACK_STOPPED=0
MANIFEST_TMP="${BACKUP_DIR}/.manifest-tmp"

restart_stack_if_needed() {
  local rc=0
  if [[ "$STACK_STOPPED" == "1" ]]; then
    log "Restarting/reconciling stack after backup attempt"
    if [[ "${HOMELAB_SKIP_DEPLOY_RESTART:-0}" == "1" ]]; then
      warn "HOMELAB_SKIP_DEPLOY_RESTART=1 set; not running deploy.sh"
      printf '%s\n' "HOMELAB_SKIP_DEPLOY_RESTART=1 set; stack restart skipped" >>"${MANIFEST_TMP}/notes.txt" 2>/dev/null || true
    elif [[ -x "${REPO_ROOT}/deploy.sh" ]]; then
      if ! sudo_run "${REPO_ROOT}/deploy.sh"; then
        warn "deploy.sh failed while restarting stack"
        printf '%s\n' "deploy.sh failed while restarting stack" >>"${MANIFEST_TMP}/notes.txt" 2>/dev/null || true
        rc="$EX_DEPLOY"
      fi
    else
      warn "deploy.sh is not executable or missing: ${REPO_ROOT}/deploy.sh"
      printf '%s\n' "deploy.sh is not executable or missing; stack may require manual reconciliation" >>"${MANIFEST_TMP}/notes.txt" 2>/dev/null || true
      rc="$EX_DEPLOY"
    fi
    STACK_STOPPED=0
  fi
  return "$rc"
}

on_exit() {
  local rc="$?"
  if [[ "$STACK_STOPPED" == "1" ]]; then
    if ! restart_stack_if_needed; then
      rc="$EX_DEPLOY"
    fi
  fi
  exit "$rc"
}
trap on_exit EXIT

add_line() {
  local file="$1"
  shift
  printf '%s\n' "$*" >>"$file"
}

record_note() {
  add_line "${MANIFEST_TMP}/notes.txt" "$*"
}

record_included_path() {
  add_line "${MANIFEST_TMP}/included_paths.txt" "$*"
}

record_excluded_path() {
  add_line "${MANIFEST_TMP}/excluded_paths.txt" "$*"
}

record_archive() {
  add_line "${MANIFEST_TMP}/archives.txt" "$*"
  add_line "${MANIFEST_TMP}/encrypted_archives.txt" "$*"
}

record_host_export() {
  add_line "${MANIFEST_TMP}/host_exports.txt" "$*"
}

member_list_file_for() {
  local rel_output="$1"
  local safe
  safe="$(printf '%s' "$rel_output" | tr '/ ' '__')"
  printf '%s/%s.members' "${MANIFEST_TMP}/members" "$safe"
}

generate_member_list() {
  local base="$1"
  local rel_output="$2"
  shift 2
  local out
  out="$(member_list_file_for "$rel_output")"
  : >"$out"
  local member
  for member in "$@"; do
    if ! sudo_test -e "${base%/}/${member}"; then
      continue
    fi
    printf '%s\n' "$member" >>"$out"
    if sudo_test -d "${base%/}/${member}"; then
      sudo_run find -P "${base%/}/${member}" -xdev -mindepth 1 -printf "${member}/%P\n" >>"$out"
    fi
  done
  sort -u "$out" -o "$out"
  validate_member_list_file "$out" || die "$EX_ARCHIVE" "unsafe archive member detected for $rel_output"
  printf '%s\t%s\n' "$rel_output" "$out" >>"${MANIFEST_TMP}/archive_members_index.tsv"
}

archive_encrypt_members() {
  local base="$1"
  local rel_output="$2"
  shift 2
  local output="${BACKUP_DIR}/${rel_output}"
  local output_dir
  output_dir="$(dirname "$output")"
  mkdir -p "$output_dir"

  if [[ "$#" -eq 0 ]]; then
    warn "no archive members supplied for $rel_output; skipping"
    record_note "Skipped empty archive: $rel_output"
    return 0
  fi

  generate_member_list "$base" "$rel_output" "$@"

  log "Creating encrypted archive: $rel_output"
  if ! sudo_run tar --create --numeric-owner --one-file-system -C "$base" "$@" \
      | zstd -T0 -19 \
      | gpg_encrypt_stdin_to_file "$output"; then
    die "$EX_ARCHIVE" "failed to create encrypted archive: $rel_output"
  fi

  [[ -s "$output" ]] || die "$EX_ARCHIVE" "encrypted archive is empty: $rel_output"
  record_archive "$rel_output"
}

archive_encrypt_existing_path() {
  local absolute_path="$1"
  local rel_output="$2"
  if ! sudo_test -e "$absolute_path"; then
    warn "source path missing; skipping archive: $absolute_path"
    record_note "Skipped missing source path: $absolute_path"
    return 0
  fi
  local base
  local member
  base="$(dirname "$absolute_path")"
  member="$(basename "$absolute_path")"
  record_included_path "$absolute_path"
  archive_encrypt_members "$base" "$rel_output" "$member"
}

capture_host_output() {
  local rel_output="$1"
  shift
  local output="${BACKUP_DIR}/${rel_output}"
  mkdir -p "$(dirname "$output")"
  log "Writing host export: $rel_output"
  if "$@" >"$output" 2>&1; then
    :
  else
    warn "host export command failed for $rel_output"
    printf '\nWARN: host export command failed: %s\n' "$*" >>"$output"
    record_note "Host export command failed: $rel_output"
  fi
  chmod 0640 "$output" 2>/dev/null || true
  record_host_export "$rel_output"
}

redact_sensitive_file() {
  local input="$1"
  local output="$2"
  python3 - "$input" "$output" <<'PY'
import re
import sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
keywords = re.compile(r"(?i)(password|passwd|secret|token|credential|api[_-]?key|access[_-]?key|private[_-]?key|smtp|ghcr|auth)")
redacted = []
for line in src.read_text(encoding="utf-8", errors="replace").splitlines():
    candidate = line.strip()
    if keywords.search(candidate):
        if ":" in line:
            prefix = line.split(":", 1)[0]
            indent = line[: len(line) - len(line.lstrip())]
            redacted.append(f"{indent}{prefix.strip()}: REDACTED")
        elif "=" in line:
            prefix = line.split("=", 1)[0]
            indent = line[: len(line) - len(line.lstrip())]
            redacted.append(f"{indent}{prefix.strip()}=REDACTED")
        else:
            redacted.append("REDACTED")
    else:
        redacted.append(line)
dst.write_text("\n".join(redacted) + "\n", encoding="utf-8")
PY
}

capture_compose_rendered_redacted() {
  local tmp="${BACKUP_DIR}/host/docker-compose-rendered.yml.tmp"
  local out="${BACKUP_DIR}/host/docker-compose-rendered.yml"
  mkdir -p "${BACKUP_DIR}/host"
  if have_cmd docker && [[ -f "$COMPOSE_FILE" ]]; then
    if docker compose --env-file "$SECRETS_FILE" -f "$COMPOSE_FILE" config >"$tmp" 2>"${tmp}.err"; then
      redact_sensitive_file "$tmp" "$out"
      rm -f "$tmp" "${tmp}.err"
    else
      warn "docker compose config failed; writing diagnostic output"
      {
        echo "WARN: docker compose config failed"
        cat "${tmp}.err" 2>/dev/null || true
      } >"$out"
      rm -f "$tmp" "${tmp}.err"
      record_note "docker compose config failed during host export"
    fi
  else
    echo "WARN: docker compose unavailable or compose file missing" >"$out"
    record_note "docker compose rendered export skipped"
  fi
  chmod 0640 "$out" 2>/dev/null || true
  record_host_export "host/docker-compose-rendered.yml"
}

preflight() {
  require_pi_or_override
  require_cmd flock
  require_cmd tar
  require_cmd zstd
  require_cmd gpg
  require_cmd sha256sum
  require_cmd python3
  require_cmd find
  require_cmd awk
  require_cmd sed
  require_cmd date
  require_cmd hostname
  require_cmd du
  require_cmd df
  require_cmd git

  [[ -d "$REPO_ROOT" ]] || die "$EX_USAGE" "repository root missing: $REPO_ROOT"
  git -C "$REPO_ROOT" rev-parse HEAD >/dev/null || die "$EX_USAGE" "not a valid Git checkout: $REPO_ROOT"
  [[ ! -f "${REPO_ROOT}/.env" ]] || die "$EX_USAGE" "repo-root .env is forbidden by policy: ${REPO_ROOT}/.env"
  [[ -f "$COMPOSE_FILE" ]] || die "$EX_USAGE" "compose file missing: $COMPOSE_FILE"

  if [[ -f "${REPO_ROOT}/stacks/${STACK_NAME}/compose/.env" ]]; then
    warn "non-authoritative compose .env exists: ${REPO_ROOT}/stacks/${STACK_NAME}/compose/.env"
    record_note "Non-authoritative compose .env exists and should be migrated/removed"
  fi

  sudo_test -f "$SECRETS_FILE" || die "$EX_USAGE" "secrets file missing: $SECRETS_FILE"
  local mode owner group
  mode="$(sudo_stat '%a' "$SECRETS_FILE")"
  owner="$(sudo_stat '%U' "$SECRETS_FILE")"
  group="$(sudo_stat '%G' "$SECRETS_FILE")"
  [[ "$mode" == "600" ]] || die "$EX_USAGE" "secrets file must have mode 600; actual mode is $mode: $SECRETS_FILE"
  if [[ "${HOMELAB_ALLOW_NON_PI:-0}" != "1" ]]; then
    [[ "$owner" == "root" && "$group" == "root" ]] || die "$EX_USAGE" "secrets file must be root:root; actual owner is ${owner}:${group}: $SECRETS_FILE"
  fi

  sudo_test -d "$HOST_SECRETS_DIR" || die "$EX_USAGE" "host secrets directory missing: $HOST_SECRETS_DIR"
  sudo_test -d "$STACK_DATA_ROOT" || die "$EX_USAGE" "stack data root missing: $STACK_DATA_ROOT"

  if [[ "$BACKUP_QUIESCE" == "1" ]]; then
    require_cmd docker
    [[ -x "${REPO_ROOT}/deploy.sh" || "${HOMELAB_SKIP_DEPLOY_RESTART:-0}" == "1" ]] \
      || die "$EX_DEPLOY" "deploy.sh must be executable when BACKUP_QUIESCE=1: ${REPO_ROOT}/deploy.sh"
  fi

  ensure_gpg_public_key_installed

  local estimate available
  estimate="$(sudo_run du -sb "$STACK_DATA_ROOT" "$HOST_SECRETS_DIR" 2>/dev/null | awk '{ s += $1 } END { print s + 0 }')"
  available="$(df -PB1 "$BACKUP_ROOT" 2>/dev/null | awk 'NR == 2 { print $4 + 0 }')"
  if [[ -n "$available" && "$available" -gt 0 && "$available" -le "$estimate" && "${BACKUP_SKIP_SPACE_CHECK:-0}" != "1" ]]; then
    die "$EX_USAGE" "insufficient free space under $BACKUP_ROOT; available=${available} estimated_source_bytes=${estimate}"
  fi
}

stop_stack() {
  if [[ "$BACKUP_QUIESCE" != "1" ]]; then
    log "BACKUP_QUIESCE=0; not stopping stack"
    record_note "BACKUP_QUIESCE=0; stack was not stopped before backup"
    return 0
  fi
  log "Stopping stack for quiesced backup: $STACK_NAME"
  sudo_run docker compose --env-file "$SECRETS_FILE" -f "$COMPOSE_FILE" down
  STACK_STOPPED=1
}

backup_host_exports() {
  mkdir -p "${BACKUP_DIR}/host"
  capture_host_output "host/os-release.txt" bash -c 'cat /etc/os-release 2>/dev/null || true'
  capture_host_output "host/uname.txt" uname -a
  if have_cmd docker; then
    capture_host_output "host/docker-version.txt" docker version
    capture_host_output "host/docker-info.txt" docker info
    capture_host_output "host/docker-compose-version.txt" docker compose version
    capture_host_output "host/docker-networks.txt" docker network ls
  else
    capture_host_output "host/docker-version.txt" bash -c 'echo "WARN: docker not installed"'
    record_note "Docker host exports skipped because docker is unavailable"
  fi
  capture_compose_rendered_redacted
  if have_cmd ufw; then
    capture_host_output "host/ufw-status-numbered.txt" sudo_run ufw status numbered
    capture_host_output "host/ufw-status-verbose.txt" sudo_run ufw status verbose
  else
    capture_host_output "host/ufw-status-numbered.txt" bash -c 'echo "WARN: ufw not installed"'
    capture_host_output "host/ufw-status-verbose.txt" bash -c 'echo "WARN: ufw not installed"'
    record_note "UFW status exports skipped because ufw is unavailable"
  fi
  if sudo_test -f /etc/docker/daemon.json; then
    sudo_run cat /etc/docker/daemon.json >"${BACKUP_DIR}/host/docker-daemon.json"
    chmod 0640 "${BACKUP_DIR}/host/docker-daemon.json" 2>/dev/null || true
    record_host_export "host/docker-daemon.json"
  else
    record_note "/etc/docker/daemon.json missing; host export skipped"
  fi
  if sudo_test -f /etc/machine-id; then
    sudo_run cat /etc/machine-id >"${BACKUP_DIR}/host/machine-id.txt"
    chmod 0640 "${BACKUP_DIR}/host/machine-id.txt" 2>/dev/null || true
    record_host_export "host/machine-id.txt"
  fi
  if have_cmd dpkg-query; then
    capture_host_output "host/package-list.txt" dpkg-query -W
  else
    capture_host_output "host/package-list.txt" bash -c 'echo "WARN: dpkg-query not installed"'
  fi

  if sudo_test -d /etc/ufw; then
    archive_encrypt_members "/" "host/etc-ufw.tar.zst.gpg" "etc/ufw"
    record_host_export "host/etc-ufw.tar.zst.gpg"
  else
    record_note "/etc/ufw missing; encrypted host archive skipped"
  fi

  if [[ "$BACKUP_INCLUDE_SSH_HOST_KEYS" == "1" ]]; then
    local ssh_members=()
    if sudo_test -d /etc/ssh; then
      if should_use_sudo; then
        mapfile -t ssh_members < <(sudo find /etc/ssh -maxdepth 1 -type f -name 'ssh_host_*' -printf 'etc/ssh/%f\n' | sort)
      else
        mapfile -t ssh_members < <(find /etc/ssh -maxdepth 1 -type f -name 'ssh_host_*' -printf 'etc/ssh/%f\n' | sort)
      fi
    fi
    if [[ "${#ssh_members[@]}" -gt 0 ]]; then
      archive_encrypt_members "/" "host/ssh-host-keys.tar.zst.gpg" "${ssh_members[@]}"
      record_host_export "host/ssh-host-keys.tar.zst.gpg"
    else
      record_note "No SSH host keys found for encrypted backup"
    fi
  else
    record_excluded_path "/etc/ssh/ssh_host_*"
    record_note "BACKUP_INCLUDE_SSH_HOST_KEYS=0; SSH host keys excluded"
  fi
}

backup_data_archives() {
  local components=(alertmanager grafana vector)
  if [[ "$BACKUP_INCLUDE_METRICS" == "1" ]]; then
    components+=(victoriametrics)
  else
    record_excluded_path "${STACK_DATA_ROOT}/victoriametrics"
    record_note "BACKUP_INCLUDE_METRICS=0; victoriametrics excluded"
  fi
  if [[ "$BACKUP_INCLUDE_LOGS" == "1" ]]; then
    components+=(victorialogs)
  else
    record_excluded_path "${STACK_DATA_ROOT}/victorialogs"
    record_note "BACKUP_INCLUDE_LOGS=0; victorialogs excluded"
  fi

  local component
  for component in "${components[@]}"; do
    if sudo_test -e "${STACK_DATA_ROOT}/${component}"; then
      record_included_path "${STACK_DATA_ROOT}/${component}"
      archive_encrypt_members "$STACK_DATA_ROOT" "data/${STACK_NAME}-${component}.tar.zst.gpg" "$component"
    else
      warn "data component missing; skipping: ${STACK_DATA_ROOT}/${component}"
      record_note "Skipped missing data component: ${component}"
    fi
  done

  if sudo_test -e "${STACK_DATA_ROOT}/alertmanager-config"; then
    record_included_path "${STACK_DATA_ROOT}/alertmanager-config"
    archive_encrypt_members "$STACK_DATA_ROOT" "generated/${STACK_NAME}-alertmanager-config.tar.zst.gpg" "alertmanager-config"
  else
    record_note "Generated alertmanager-config directory missing; diagnostic archive skipped"
  fi
}

write_archive_members_json() {
  local out="${BACKUP_DIR}/host/archive-members.json"
  python3 - "${MANIFEST_TMP}/archive_members_index.tsv" "$out" <<'PY'
import json
import pathlib
import sys

index = pathlib.Path(sys.argv[1])
out = pathlib.Path(sys.argv[2])
payload = {}
if index.exists():
    for line in index.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        artifact, member_file = line.split("\t", 1)
        payload[artifact] = pathlib.Path(member_file).read_text(encoding="utf-8").splitlines()
out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  chmod 0640 "$out" 2>/dev/null || true
  record_host_export "host/archive-members.json"
}

write_manifest() {
  local manifest="${BACKUP_DIR}/manifest.json"
  local git_commit git_status_clean hostname compose_rel
  git_commit="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
  if [[ -z "$(git -C "$REPO_ROOT" status --porcelain 2>/dev/null || true)" ]]; then
    git_status_clean="true"
  else
    git_status_clean="false"
    record_note "Git work tree was not clean at backup time"
  fi
  hostname="$(hostname -s 2>/dev/null || hostname)"
  compose_rel="$(safe_relpath "$COMPOSE_FILE" "$REPO_ROOT")"

  python3 - \
    "$manifest" \
    "${MANIFEST_TMP}/included_paths.txt" \
    "${MANIFEST_TMP}/excluded_paths.txt" \
    "${MANIFEST_TMP}/archives.txt" \
    "${MANIFEST_TMP}/encrypted_archives.txt" \
    "${MANIFEST_TMP}/host_exports.txt" \
    "${MANIFEST_TMP}/notes.txt" \
    <<PY
import json
import pathlib
import sys

out = pathlib.Path(sys.argv[1])
files = [pathlib.Path(p) for p in sys.argv[2:]]

def lines(path):
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line]

payload = {
    "schema_version": 1,
    "created_at_utc": "${CREATED_AT_UTC}",
    "hostname": "${hostname}",
    "repo_root": "${REPO_ROOT}",
    "git_commit": "${git_commit}",
    "git_status_clean": "${git_status_clean}" == "true",
    "backup_root": "${BACKUP_ROOT}",
    "backup_id": "${BACKUP_ID}",
    "compose_file": "${compose_rel}",
    "secrets_file": "${SECRETS_FILE}",
    "data_root": "${STACK_DATA_ROOT}",
    "included_paths": lines(files[0]),
    "excluded_paths": lines(files[1]),
    "archives": lines(files[2]),
    "encrypted_archives": lines(files[3]),
    "host_exports": lines(files[4]),
    "options": {
        "backup_quiesce": "${BACKUP_QUIESCE}" == "1",
        "include_metrics": "${BACKUP_INCLUDE_METRICS}" == "1",
        "include_logs": "${BACKUP_INCLUDE_LOGS}" == "1",
        "include_ssh_host_keys": "${BACKUP_INCLUDE_SSH_HOST_KEYS}" == "1"
    },
    "gpg": {
        "encryption_model": "OpenPGP public-key encryption with GnuPG",
        "recipient_fingerprint": "${GPG_RECIPIENT_FINGERPRINT}",
        "public_key_file": "${GPG_PUBLIC_KEY_FILE}",
        "pi_private_key_policy": "private key must not be installed on the Pi"
    },
    "notes": lines(files[5]),
}
out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  chmod 0640 "$manifest" 2>/dev/null || true
}

generate_checksums() {
  local tmp="${BACKUP_DIR}/checksums.sha256.tmp"
  (
    cd "$BACKUP_DIR"
    find manifest.json data generated secrets host logs \
      -type f \
      ! -name 'backup-verify.log' \
      -print0 2>/dev/null \
      | sort -z \
      | xargs -0 sha256sum
  ) >"$tmp"
  mv "$tmp" "${BACKUP_DIR}/checksums.sha256"
  chmod 0640 "${BACKUP_DIR}/checksums.sha256" 2>/dev/null || true
}

main() {
  ensure_runner_dir "$BACKUP_ROOT" 0750
  acquire_lock

  mkdir -p "${BACKUP_DIR}/data" "${BACKUP_DIR}/generated" "${BACKUP_DIR}/secrets" "${BACKUP_DIR}/host" "${BACKUP_DIR}/logs" "${MANIFEST_TMP}/members"
  : >"${MANIFEST_TMP}/included_paths.txt"
  : >"${MANIFEST_TMP}/excluded_paths.txt"
  : >"${MANIFEST_TMP}/archives.txt"
  : >"${MANIFEST_TMP}/encrypted_archives.txt"
  : >"${MANIFEST_TMP}/host_exports.txt"
  : >"${MANIFEST_TMP}/notes.txt"
  : >"${MANIFEST_TMP}/archive_members_index.tsv"

  exec 3>&1 4>&2
  exec > >(tee -a "$LOG_FILE" >&3) 2> >(tee -a "$LOG_FILE" >&4)

  log "Starting homelab backup: ${BACKUP_ID}"
  preflight
  backup_host_exports

  stop_stack
  backup_data_archives
  archive_encrypt_existing_path "$HOST_SECRETS_DIR" "secrets/etc-raspberry-pi-homelab.tar.zst.gpg"
  restart_stack_if_needed

  write_archive_members_json
  write_manifest
  rm -rf "$MANIFEST_TMP"

  log "Backup artifacts complete; finalizing checksums"
  exec >&3 2>&4
  generate_checksums

  printf 'OK: backup created: %s\n' "$BACKUP_DIR"
  printf 'Next: BACKUP_DIR=%q make backup_verify\n' "$BACKUP_DIR"
}

main "$@"
