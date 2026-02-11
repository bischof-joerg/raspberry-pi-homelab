#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_ENV_FILE="${STACK_ENV_FILE:-/etc/raspberry-pi-homelab/monitoring.env}"

cd "$REPO_ROOT"

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "ERROR: Not inside a git repository. Run this script from within the repo." >&2
  exit 2
fi

is_pi() {
  grep -qi raspberry /proc/device-tree/model 2>/dev/null
}

pick_python() {
  if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
    echo "${VIRTUAL_ENV}/bin/python"
    return 0
  fi

  if is_pi; then
    command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not found"; exit 2; }
    echo "python3"
    return 0
  fi

  if [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
    echo "${REPO_ROOT}/.venv/bin/python"
    return 0
  fi

  command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not found"; exit 2; }
  echo "python3"
}

PYTHON_BIN="$(pick_python)"

PYTEST_CACHE_OPTS=()
if [[ "${PYTEST_DISABLE_CACHE:-1}" == "1" ]]; then
  PYTEST_CACHE_OPTS=(-p no:cacheprovider)
fi

DEFAULT_PYTEST_OPTS=(--strict-markers --maxfail=1)

USER_PYTEST_OPTS=()
if [[ -n "${PYTEST_OPTS:-}" ]]; then
  # shellcheck disable=SC2206
  USER_PYTEST_OPTS=(${PYTEST_OPTS})
fi

args_mention_postdeploy() {
  [[ $# -gt 0 ]] && printf "%s\n" "$*" | grep -qi "postdeploy"
}

docker_usable_without_sudo() {
  command -v docker >/dev/null 2>&1 || return 1
  docker ps >/dev/null 2>&1
}

needs_root_for_postdeploy() {
  # Root escalation is only relevant on the Raspberry Pi target host.
  if ! is_pi; then
    return 1
  fi

  # Only consider postdeploy marker/path as a root candidate.
  if ! args_mention_postdeploy "$@"; then
    return 1
  fi

  # If monitoring.env exists but isn't readable, we must escalate to load creds/secrets.
  if [[ -f "$STACK_ENV_FILE" && ! -r "$STACK_ENV_FILE" ]]; then
    return 0
  fi

  return 0
}

run_pytest_plain() {
  # Best-effort: load STACK_ENV_FILE if readable (important on Pi when running without sudo).
  if [[ -f "$STACK_ENV_FILE" && -r "$STACK_ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$STACK_ENV_FILE"
    set +a
  fi

  "$PYTHON_BIN" -m pytest \
    "${DEFAULT_PYTEST_OPTS[@]}" \
    "${PYTEST_CACHE_OPTS[@]}" \
    "${USER_PYTEST_OPTS[@]}" \
    "$@"
}


run_pytest_as_root() {
  command -v sudo >/dev/null 2>&1 || {
    echo "ERROR: sudo not found (required for postdeploy)" >&2
    exit 2
  }

  # Preflight: fail fast if sudo would prompt (prevents "hangs").
  if ! sudo -n true 2>/dev/null; then
    echo "ERROR: postdeploy requires sudo privileges but sudo is not authenticated (non-interactive sudo failed)." >&2
    echo "HINT: run once on the Pi: sudo -v  (then retry)  OR add your user to the docker group so docker works without sudo." >&2
    exit 2
  fi

  local -a argv
  argv=(
    "$PYTHON_BIN" -m pytest
    "${DEFAULT_PYTEST_OPTS[@]}"
    "${PYTEST_CACHE_OPTS[@]}"
    "${USER_PYTEST_OPTS[@]}"
    "$@"
  )

  sudo -nE env STACK_ENV_FILE="$STACK_ENV_FILE" REPO_ROOT="$REPO_ROOT" bash -lc '
    set -euo pipefail
    if [[ -f "$STACK_ENV_FILE" ]]; then
      set -a
      # shellcheck disable=SC1090
      source "$STACK_ENV_FILE"
      set +a
    fi
    cd "$REPO_ROOT"
    exec "$@"
  ' bash "${argv[@]}"
}

if needs_root_for_postdeploy "$@"; then
  run_pytest_as_root "$@"
else
  run_pytest_plain "$@"
fi
