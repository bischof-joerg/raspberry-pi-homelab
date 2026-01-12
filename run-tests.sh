#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load secrets as root if available (root-only perms are fine)
SECRETS_FILE="/etc/raspberry-pi-homelab/secrets.env"

if [[ -f "$SECRETS_FILE" ]]; then
  # Run pytest in a root subshell so it can read the secrets file.
  # Environment is exported only for the duration of this command.
  sudo -E bash -c "
    set -a
    source '$SECRETS_FILE'
    set +a
    cd '$REPO_ROOT'
    pytest \"$@\"
  "
else
  cd "$REPO_ROOT"
  pytest "$@"
fi
