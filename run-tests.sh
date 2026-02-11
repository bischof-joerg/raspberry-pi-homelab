#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_ENV_FILE="${STACK_ENV_FILE:-/etc/raspberry-pi-homelab/monitoring.env}"

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

cd "$REPO_ROOT"

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "ERROR: Not inside a git repository. Run this script from within the repo." >&2
  exit 2
fi

pick_python() {
  # Prefer active venv
  if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
    echo "${VIRTUAL_ENV}/bin/python"
    return 0
  fi

  # Prefer repo-local venv
  if [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
    echo "${REPO_ROOT}/.venv/bin/python"
    return 0
  fi

  # Fallback
  command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not found"; exit 2; }
  command -v python3
}

PYTHON_BIN="$(pick_python)"

needs_root_for_postdeploy() {
  # If args mention postdeploy marker or folder, assume docker access needed.
  if [[ $# -eq 0 ]]; then
    return 1
  fi
  if printf "%s\n" "$*" | grep -qi "postdeploy"; then
    return 0
  fi
  return 1
}

run_pytest_plain() {
  "$PYTHON_BIN" -m pytest \
    "${DEFAULT_PYTEST_OPTS[@]}" \
    "${PYTEST_CACHE_OPTS[@]}" \
    "${USER_PYTEST_OPTS[@]}" \
    "$@"
}

run_pytest_as_root() {
  command -v sudo >/dev/null 2>&1 || { echo "ERROR: sudo not found (required for postdeploy)"; exit 2; }

  # Keep env (-E) so POSTDEPLOY_ON_TARGET / VM_EXPECT_* etc. survive.
  # Use absolute python path so we don't rely on PATH containing venv.
  sudo -E bash -c '
    set -euo pipefail

    if [[ -f "'"$STACK_ENV_FILE"'" ]]; then
      set -a
      source "'"$STACK_ENV_FILE"'"
      set +a
    fi

    cd "'"$REPO_ROOT"'"

    "'"$PYTHON_BIN"'" -m pytest \
      '"${DEFAULT_PYTEST_OPTS[*]}"' \
      '"${PYTEST_CACHE_OPTS[*]}"' \
      '"${USER_PYTEST_OPTS[*]}"' \
      "$@"
  ' -- "$@"
}

if needs_root_for_postdeploy "$@"; then
  run_pytest_as_root "$@"
else
  run_pytest_plain "$@"
fi
