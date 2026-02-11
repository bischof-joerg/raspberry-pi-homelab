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
  # Robust enough for Raspberry Pi OS
  grep -qi raspberry /proc/device-tree/model 2>/dev/null
}

pick_python() {
  # 1) Prefer active venv if explicitly activated
  if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
    echo "${VIRTUAL_ENV}/bin/python"
    return 0
  fi

  # 2) On Raspberry Pi: never use repo-local .venv (deploy target only)
  if is_pi; then
    command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not found"; exit 2; }
    echo "python3"
    return 0
  fi

  # 3) On dev/CI hosts: prefer repo-local venv if present
  if [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
    echo "${REPO_ROOT}/.venv/bin/python"
    return 0
  fi

  # 4) Fallback
  command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not found"; exit 2; }
  echo "python3"
}

PYTHON_BIN="$(pick_python)"

# pytest options (keep behavior deterministic)
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

needs_root_for_postdeploy() {
  [[ $# -gt 0 ]] && printf "%s\n" "$*" | grep -qi "postdeploy"
}

run_pytest_plain() {
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

  # Compose the full pytest argv in the caller shell (correct splitting).
  local -a argv
  argv=(
    "$PYTHON_BIN" -m pytest
    "${DEFAULT_PYTEST_OPTS[@]}"
    "${PYTEST_CACHE_OPTS[@]}"
    "${USER_PYTEST_OPTS[@]}"
    "$@"
  )

  # Non-interactive sudo (-n) to avoid hangs in CI/automation.
  # Keep env (-E) so POSTDEPLOY_ON_TARGET / VM_EXPECT_* survive.
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
  ' bash "${argv[@]}" || {
    rc=$?
    if [[ $rc -eq 1 || $rc -eq 2 || $rc -eq 127 ]]; then
      # fall through; these are normal "command failed" cases
      :
    fi
    echo "ERROR: postdeploy requires sudo privileges (non-interactive sudo failed)." >&2
    echo "HINT: run once on the Pi: sudo -v  (then retry)  OR run as a user with Docker socket access." >&2
    exit $rc
  }
}


if needs_root_for_postdeploy "$@"; then
  run_pytest_as_root "$@"
else
  run_pytest_plain "$@"
fi
