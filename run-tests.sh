#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECRETS_FILE="${SECRETS_FILE:-/etc/raspberry-pi-homelab/secrets.env}"

# Check for sudo availability
command -v sudo >/dev/null 2>&1 || { echo "ERROR: sudo not found"; exit 2; }
sudo -n true >/dev/null 2>&1 || true

# Default: avoid root writing .pytest_cache into the repo (especially when running via sudo)
PYTEST_CACHE_OPTS=()
if [[ "${PYTEST_DISABLE_CACHE:-1}" == "1" ]]; then
  PYTEST_CACHE_OPTS=(-p no:cacheprovider)
fi

# Hardening defaults (can be overridden/extended via PYTEST_OPTS)
DEFAULT_PYTEST_OPTS=(--strict-markers --maxfail=1)
# Allow user to add/override options, e.g. PYTEST_OPTS="-vv --maxfail=2"
USER_PYTEST_OPTS=()
if [[ -n "${PYTEST_OPTS:-}" ]]; then
  # shellcheck disable=SC2206
  USER_PYTEST_OPTS=(${PYTEST_OPTS})
fi

cd "$REPO_ROOT"

# Helper: check if args indicate postdeploy or grafana test likely needs creds
needs_grafana_creds() {
  # If user explicitly runs postdeploy marker or postdeploy tests folder, require creds.
  for a in "$@"; do
    [[ "$a" == "-m" ]] && return 0
    [[ "$a" == *"postdeploy"* ]] && return 0
  done
  return 1
}

# We enforce secrets only when they are actually needed.
# If you run "all tests", postdeploy is included -> credentials needed.
REQUIRE_SECRETS=0
if [[ $# -eq 0 ]]; then
  # no args => run all tests => includes postdeploy
  REQUIRE_SECRETS=1
else
  # if args mention postdeploy anywhere, assume secrets required
  if printf "%s\n" "$*" | grep -qi "postdeploy"; then
    REQUIRE_SECRETS=1
  fi
fi

# Ensure we run inside a git repo (helps avoid confusing "rootdir" behavior)
if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "ERROR: Not inside a git repository. Run this script from within the repo." >&2
  exit 2
fi

run_pytest_as_root_with_secrets() {
  sudo -E bash -c "
    set -euo pipefail
    set -a
    source '$SECRETS_FILE'
    set +a
    cd '$REPO_ROOT'
    pytest ${DEFAULT_PYTEST_OPTS[*]} ${PYTEST_CACHE_OPTS[*]} ${USER_PYTEST_OPTS[*]} \"\$@\"
  " -- "$@"
}

run_pytest_plain() {
  pytest "${DEFAULT_PYTEST_OPTS[@]}" "${PYTEST_CACHE_OPTS[@]}" "${USER_PYTEST_OPTS[@]}" "$@"
}

# If secrets are required, enforce a safe path:
if ! sudo test -f "$SECRETS_FILE"; then
  echo "ERROR: Secrets file not found: $SECRETS_FILE" >&2
  echo "Create it (root-only) e.g.:" >&2
  echo "  sudo install -d -m 700 /etc/raspberry-pi-homelab" >&2
  echo "  sudo nano $SECRETS_FILE" >&2
  echo "  sudo chmod 600 $SECRETS_FILE" >&2
  exit 2
fi

  # Verify it is readable by root (not necessarily by current user)
  if ! sudo test -r "$SECRETS_FILE"; then
    echo "ERROR: Secrets file exists but is not readable by root: $SECRETS_FILE" >&2
    exit 2
  fi

  # Optional: Fail fast if required vars are missing in the secrets file.
  # This avoids confusing test failures later.
  if ! sudo -E bash -c "set -a; source '$SECRETS_FILE'; set +a; [[ -n \"\${GRAFANA_ADMIN_USER:-}\" && -n \"\${GRAFANA_ADMIN_PASSWORD:-}\" ]]" ; then
    echo "ERROR: Missing GRAFANA_ADMIN_USER or GRAFANA_ADMIN_PASSWORD in $SECRETS_FILE" >&2
    exit 2
  fi

  run_pytest_as_root_with_secrets "$@"
else
  run_pytest_plain "$@"
fi
