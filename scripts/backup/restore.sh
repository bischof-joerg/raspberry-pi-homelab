#!/usr/bin/env bash
# Remote restore commands intentionally use locally validated values before SSH.
# shellcheck disable=SC2029
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=scripts/backup/common.sh
source "${SCRIPT_DIR}/common.sh"

RESTORE_PRE_RESTORE_ID="${RESTORE_PRE_RESTORE_ID:-$(date -u +'%Y-%m-%dT%H%M%SZ')}"
SELECTED_BACKUP_DIR=""
RESTORE_LOG=""

usage() {
  cat <<'USAGE'
Usage: restore.sh

Required:
  RESTORE_BACKUP=/path/to/backup-or-backup-id

Default mode is dry-run. To apply a restore:
  RESTORE_APPLY=1 RESTORE_CONFIRM=RESTORE_HOMELAB_DATA RESTORE_TARGET=admin@rpi-hub make restore

Common controls:
  RESTORE_COMPONENTS=all|grafana,alertmanager,vector,victoriametrics,victorialogs
  RESTORE_SECRETS=1|0
  RESTORE_DATA=1|0
  RESTORE_SSH_HOST_KEYS=1|0
  RESTORE_MACHINE_ID=1|0
  RESTORE_TARGET=user@host       Standard WSL/Admin-to-Pi restore target.
USAGE
}

parse_args() {
  if [[ "$#" -eq 0 ]]; then
    return 0
  fi

  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "$EX_USAGE" "unknown argument: $1"
      ;;
  esac
}

confirm_restore_guards() {
  [[ -n "${RESTORE_BACKUP:-}" ]] || die "$EX_USAGE" "RESTORE_BACKUP is required"
  if [[ "$RESTORE_APPLY" == "1" ]]; then
    [[ "${RESTORE_CONFIRM:-}" == "RESTORE_HOMELAB_DATA" ]] \
      || die "$EX_RESTORE_GUARD" "destructive restore requires RESTORE_CONFIRM=RESTORE_HOMELAB_DATA"
    if [[ -z "${RESTORE_TARGET:-}" && "${HOMELAB_ALLOW_LOCAL_RESTORE:-0}" != "1" ]]; then
      die "$EX_RESTORE_GUARD" "local apply restore requires HOMELAB_ALLOW_LOCAL_RESTORE=1; standard path is RESTORE_TARGET=user@pi"
    fi
  fi
}

component_selected() {
  local component="$1"
  if [[ "$RESTORE_COMPONENTS" == "all" ]]; then
    return 0
  fi
  local item
  IFS=',' read -r -a parts <<<"$RESTORE_COMPONENTS"
  for item in "${parts[@]}"; do
    item="$(printf '%s' "$item" | xargs)"
    [[ "$item" == "$component" ]] && return 0
  done
  return 1
}

artifact_for_component() {
  local component="$1"
  printf '%s/data/%s-%s.tar.zst.gpg\n' "$SELECTED_BACKUP_DIR" "$STACK_NAME" "$component"
}

verify_artifact_decryptable() {
  local artifact="$1"
  local list_file
  [[ -s "$artifact" ]] || die "$EX_ARCHIVE" "restore artifact missing or empty: $artifact"
  list_file="$(mktemp)"
  if ! gpg --batch --decrypt "$artifact" | zstd -d | tar -tf - >"$list_file"; then
    rm -f "$list_file"
    die "$EX_GPG" "decrypt/decompress/tar-list failed for restore artifact: $artifact"
  fi
  validate_member_list_file "$list_file" || {
    rm -f "$list_file"
    die "$EX_ARCHIVE" "unsafe archive members in restore artifact: $artifact"
  }
  rm -f "$list_file"
}

planned_components() {
  local candidates=(alertmanager grafana vector victoriametrics victorialogs)
  local component artifact
  for component in "${candidates[@]}"; do
    if component_selected "$component"; then
      artifact="$(artifact_for_component "$component")"
      [[ -f "$artifact" ]] && printf '%s\n' "$component"
    fi
  done
}

run_remote() {
  local command="$1"
  # shellcheck disable=SC2029
  ssh "$RESTORE_TARGET" "$command"
}

remote_quote() {
  shell_quote "$1"
}

restore_secrets_remote() {
  local artifact="${SELECTED_BACKUP_DIR}/secrets/etc-raspberry-pi-homelab.tar.zst.gpg"
  verify_artifact_decryptable "$artifact"
  log "Restoring host-only secrets to remote target: $RESTORE_TARGET"
  gpg --batch --decrypt "$artifact" \
    | zstd -d \
    | ssh "$RESTORE_TARGET" 'sudo tar --extract --preserve-permissions --numeric-owner --file - --directory /etc'
  run_remote 'sudo chown root:root /etc/raspberry-pi-homelab/*.env && sudo chmod 600 /etc/raspberry-pi-homelab/*.env'
}

restore_component_remote() {
  local component="$1"
  local artifact
  artifact="$(artifact_for_component "$component")"
  verify_artifact_decryptable "$artifact"
  local stack_root_q pre_root_q tmp_q component_q
  stack_root_q="$(remote_quote "$STACK_DATA_ROOT")"
  pre_root_q="$(remote_quote "${BACKUP_ROOT}/pre-restore/${RESTORE_PRE_RESTORE_ID}")"
  tmp_q="$(remote_quote "${STACK_DATA_ROOT}/.restore-tmp-${component}-${RESTORE_PRE_RESTORE_ID}")"
  component_q="$(remote_quote "$component")"

  log "Restoring data component to remote target: $component"
  # shellcheck disable=SC2029
  gpg --batch --decrypt "$artifact" \
    | zstd -d \
    | ssh "$RESTORE_TARGET" "set -euo pipefail; \
        sudo mkdir -p ${stack_root_q} ${pre_root_q}; \
        sudo rm -rf ${tmp_q}; \
        sudo mkdir -p ${tmp_q}; \
        sudo tar --extract --preserve-permissions --numeric-owner --file - --directory ${tmp_q}; \
        if [ -L ${stack_root_q}/${component_q} ]; then echo 'Refusing symlink target' >&2; exit 4; fi; \
        if [ -e ${stack_root_q}/${component_q} ]; then sudo mv ${stack_root_q}/${component_q} ${pre_root_q}/${component_q}; fi; \
        sudo mv ${tmp_q}/${component_q} ${stack_root_q}/${component_q}; \
        sudo rm -rf ${tmp_q}"
}

restore_ssh_host_keys_remote() {
  local artifact="${SELECTED_BACKUP_DIR}/host/ssh-host-keys.tar.zst.gpg"
  [[ -s "$artifact" ]] || die "$EX_ARCHIVE" "SSH host key artifact missing: $artifact"
  verify_artifact_decryptable "$artifact"
  log "Restoring SSH host keys to remote target"
  gpg --batch --decrypt "$artifact" \
    | zstd -d \
    | ssh "$RESTORE_TARGET" 'sudo tar --extract --preserve-permissions --numeric-owner --file - --directory /'
}

restore_machine_id_remote() {
  local file="${SELECTED_BACKUP_DIR}/host/machine-id.txt"
  [[ -s "$file" ]] || die "$EX_ARCHIVE" "machine-id export missing: $file"
  log "Restoring /etc/machine-id to remote target"
  ssh "$RESTORE_TARGET" 'sudo tee /etc/machine-id >/dev/null && sudo chmod 444 /etc/machine-id' <"$file"
}

restore_secrets_local() {
  local artifact="${SELECTED_BACKUP_DIR}/secrets/etc-raspberry-pi-homelab.tar.zst.gpg"
  verify_artifact_decryptable "$artifact"
  log "Restoring host-only secrets locally"
  gpg --batch --decrypt "$artifact" | zstd -d | sudo_run tar --extract --preserve-permissions --numeric-owner --file - --directory /etc
  sudo_run chown root:root /etc/raspberry-pi-homelab/*.env
  sudo_run chmod 600 /etc/raspberry-pi-homelab/*.env
}

restore_component_local() {
  local component="$1"
  local artifact
  artifact="$(artifact_for_component "$component")"
  verify_artifact_decryptable "$artifact"
  local pre_root="${BACKUP_ROOT}/pre-restore/${RESTORE_PRE_RESTORE_ID}"
  local tmp="${STACK_DATA_ROOT}/.restore-tmp-${component}-${RESTORE_PRE_RESTORE_ID}"
  sudo_run mkdir -p "$STACK_DATA_ROOT" "$pre_root"
  sudo_run rm -rf "$tmp"
  sudo_run mkdir -p "$tmp"
  log "Restoring data component locally: $component"
  gpg --batch --decrypt "$artifact" | zstd -d | sudo_run tar --extract --preserve-permissions --numeric-owner --file - --directory "$tmp"
  if sudo_test -L "${STACK_DATA_ROOT}/${component}"; then
    die "$EX_RESTORE_GUARD" "refusing to restore over symlink target: ${STACK_DATA_ROOT}/${component}"
  fi
  if sudo_test -e "${STACK_DATA_ROOT}/${component}"; then
    sudo_run mv "${STACK_DATA_ROOT}/${component}" "${pre_root}/${component}"
  fi
  sudo_run mv "${tmp}/${component}" "${STACK_DATA_ROOT}/${component}"
  sudo_run rm -rf "$tmp"
}

stop_remote_stack() {
  local repo_q
  repo_q="$(remote_quote "$RESTORE_REMOTE_REPO_ROOT")"
  log "Stopping remote stack before restore"
  run_remote "cd ${repo_q} && sudo docker compose --env-file $(remote_quote "$SECRETS_FILE") -f $(remote_quote "$COMPOSE_FILE") down"
}

reconcile_remote_stack() {
  local repo_q
  repo_q="$(remote_quote "$RESTORE_REMOTE_REPO_ROOT")"
  log "Reconciling remote host through deploy.sh"
  run_remote "cd ${repo_q} && sudo ./deploy.sh"
  if [[ "${RESTORE_RUN_POSTDEPLOY:-1}" == "1" ]]; then
    log "Running remote postdeploy validation"
    run_remote "cd ${repo_q} && make postdeploy"
  fi
  if [[ "${RESTORE_RUN_BACKUP_VERIFY:-1}" == "1" ]]; then
    log "Running remote artifact verification after restore"
    run_remote "cd ${repo_q} && make backup_verify"
  fi
}

stop_local_stack() {
  log "Stopping local stack before restore"
  sudo_run docker compose --env-file "$SECRETS_FILE" -f "$COMPOSE_FILE" down
}

reconcile_local_stack() {
  log "Reconciling local host through deploy.sh"
  sudo_run "${REPO_ROOT}/deploy.sh"
  if [[ "${RESTORE_RUN_POSTDEPLOY:-1}" == "1" ]]; then
    make -C "$REPO_ROOT" postdeploy
  fi
  if [[ "${RESTORE_RUN_BACKUP_VERIFY:-1}" == "1" ]]; then
    make -C "$REPO_ROOT" backup_verify
  fi
}

dry_run_plan() {
  echo "Restore dry-run"
  echo "  backup:            $SELECTED_BACKUP_DIR"
  echo "  apply:             $RESTORE_APPLY"
  echo "  target:            ${RESTORE_TARGET:-local}"
  echo "  restore secrets:   $RESTORE_SECRETS"
  echo "  restore data:      $RESTORE_DATA"
  echo "  components:        $RESTORE_COMPONENTS"
  echo "  ssh host keys:     $RESTORE_SSH_HOST_KEYS"
  echo "  machine-id:        $RESTORE_MACHINE_ID"
  echo
  echo "Artifacts that would be restored:"
  if [[ "$RESTORE_SECRETS" == "1" ]]; then
    echo "  secrets/etc-raspberry-pi-homelab.tar.zst.gpg -> /etc/raspberry-pi-homelab"
  fi
  if [[ "$RESTORE_DATA" == "1" ]]; then
    local component
    while IFS= read -r component; do
      echo "  data/${STACK_NAME}-${component}.tar.zst.gpg -> ${STACK_DATA_ROOT}/${component}"
    done < <(planned_components)
  fi
  if [[ "$RESTORE_SSH_HOST_KEYS" == "1" ]]; then
    echo "  host/ssh-host-keys.tar.zst.gpg -> /etc/ssh/ssh_host_*"
  fi
  if [[ "$RESTORE_MACHINE_ID" == "1" ]]; then
    echo "  host/machine-id.txt -> /etc/machine-id"
  fi
  echo
  echo "No files, services, ownerships, or permissions were changed."
}

apply_restore() {
  require_gpg_secret_key_available

  if [[ -n "${RESTORE_TARGET:-}" ]]; then
    stop_remote_stack
    if [[ "$RESTORE_SECRETS" == "1" ]]; then
      restore_secrets_remote
    fi
    if [[ "$RESTORE_DATA" == "1" ]]; then
      local component
      while IFS= read -r component; do
        restore_component_remote "$component"
      done < <(planned_components)
    fi
    if [[ "$RESTORE_SSH_HOST_KEYS" == "1" ]]; then
      restore_ssh_host_keys_remote
    fi
    if [[ "$RESTORE_MACHINE_ID" == "1" ]]; then
      restore_machine_id_remote
    fi
    reconcile_remote_stack
  else
    stop_local_stack
    if [[ "$RESTORE_SECRETS" == "1" ]]; then
      restore_secrets_local
    fi
    if [[ "$RESTORE_DATA" == "1" ]]; then
      local component
      while IFS= read -r component; do
        restore_component_local "$component"
      done < <(planned_components)
    fi
    reconcile_local_stack
  fi
}

main() {
  parse_args "$@"
  confirm_restore_guards
  acquire_lock
  SELECTED_BACKUP_DIR="$(select_backup_dir)"
  [[ -d "$SELECTED_BACKUP_DIR" ]] || die "$EX_USAGE" "backup directory missing: $SELECTED_BACKUP_DIR"
  RESTORE_LOG="${SELECTED_BACKUP_DIR}/logs/restore.log"
  mkdir -p "$(dirname "$RESTORE_LOG")"

  exec 3>&1 4>&2
  exec > >(tee -a "$RESTORE_LOG" >&3) 2> >(tee -a "$RESTORE_LOG" >&4)

  log "Starting restore workflow: $SELECTED_BACKUP_DIR"
  BACKUP_DIR="$SELECTED_BACKUP_DIR" BACKUP_VERIFY_DECRYPT=1 BACKUP_VERIFY_ENFORCE_FRESHNESS=0 "${SCRIPT_DIR}/backup-verify.sh" --decrypt

  if [[ "$RESTORE_APPLY" != "1" ]]; then
    dry_run_plan
    exec >&3 2>&4
    printf 'OK: restore dry-run completed for %s\n' "$SELECTED_BACKUP_DIR"
    return 0
  fi

  apply_restore
  log "Restore completed: $SELECTED_BACKUP_DIR"
  exec >&3 2>&4
  printf 'OK: restore applied from %s\n' "$SELECTED_BACKUP_DIR"
}

main "$@"
