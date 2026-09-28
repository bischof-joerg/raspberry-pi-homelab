#!/usr/bin/env bash
# scripts/dev/ensure-venv.sh - create or update the dev venv from the pins (WSL and CI only).
#
# Idempotent (F21): a stamp in the venv records a hash of requirements-dev.txt,
# constraints-dev.txt and the venv's Python version. If it matches, nothing is installed.
# Otherwise pip is installed at its pinned version first, then requirements-dev.txt (the only
# dev dependency source, F22), and the stamp is written only after both succeeded.
#
# pip never removes packages; after a dependency is dropped, run `make venv-clean venv`.
#
# Environment (defaults in brackets; overridden by tests/guards/test_42_ensure_venv.py):
#   VENV_DIR [<repo>/.venv]  PYTHON [python3]
#   REQUIREMENTS_FILE [<repo>/requirements-dev.txt]  CONSTRAINTS_FILE [<repo>/constraints-dev.txt]
#
# Exit codes: 0 ok, 2 refused or input missing, other: the failing command's code.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="${VENV_DIR:-$REPO_ROOT/.venv}"
PYTHON="${PYTHON:-python3}"
REQUIREMENTS_FILE="${REQUIREMENTS_FILE:-$REPO_ROOT/requirements-dev.txt}"
CONSTRAINTS_FILE="${CONSTRAINTS_FILE:-$REPO_ROOT/constraints-dev.txt}"
STAMP="$VENV_DIR/.toolchain-stamp"

if grep -qi raspberry /proc/device-tree/model 2>/dev/null; then
  echo "[venv] refused: the Pi is a deploy target and has no dev venv" >&2
  exit 2
fi

for file in "$REQUIREMENTS_FILE" "$CONSTRAINTS_FILE"; do
  [[ -f "$file" ]] || { echo "FAIL: $file missing (dev dependency pins, F21/F22)" >&2; exit 2; }
done

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "[venv] creating $VENV_DIR"
  "$PYTHON" -m venv "$VENV_DIR"
fi

wanted="$(
  {
    sha256sum <"$REQUIREMENTS_FILE"
    sha256sum <"$CONSTRAINTS_FILE"
    "$VENV_DIR/bin/python" --version
  } | sha256sum | cut -d' ' -f1
)"

if [[ -f "$STAMP" && "$(cat "$STAMP")" == "$wanted" ]]; then
  echo "[venv] up to date"
  exit 0
fi

rm -f "$STAMP"
echo "[venv] installing pinned pip"
"$VENV_DIR/bin/python" -m pip install -c "$CONSTRAINTS_FILE" pip >/dev/null
echo "[venv] installing $(basename "$REQUIREMENTS_FILE")"
"$VENV_DIR/bin/python" -m pip install -r "$REQUIREMENTS_FILE"
printf '%s\n' "$wanted" >"$STAMP"
echo "[venv] done"
