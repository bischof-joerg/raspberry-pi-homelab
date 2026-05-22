#!/usr/bin/env bash
# Apply Raspberry Pi host runtime package updates through the GitOps checkout.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/host-runtime/common.sh
if [ -f "$SCRIPT_DIR/common.sh" ]; then
  source "$SCRIPT_DIR/common.sh"
else
  echo "Error: common.sh not found in $SCRIPT_DIR" >&2
  exit 1
fi

require_pi
require_command apt-get
require_clean_git_tree

section "Preflight"
echo "Git work tree is clean."
if command_exists rpi-update; then
  echo "INFO: rpi-update is installed, but this workflow intentionally does not call it."
fi

section "APT full-upgrade"
export DEBIAN_FRONTEND=noninteractive
sudo_required apt-get update
sudo_required apt-get -y full-upgrade
sudo_required apt-get -y autoremove --purge
sudo_required apt-get -y autoclean

section "Package holds"
print_apt_holds

section "Docker package state"
print_docker_package_state

section "Runtime versions"
uname -a
print_docker_versions

section "Raspberry Pi EEPROM status"
if command_exists rpi-eeprom-update; then
  sudo_optional rpi-eeprom-update || true
else
  warn "rpi-eeprom-update is not available"
fi

section "Reboot status"
print_reboot_status

echo "Host package update completed. If a reboot is required, run: sudo reboot"
echo "After reboot, run: make postdeploy"
