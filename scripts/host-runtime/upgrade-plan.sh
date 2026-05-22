#!/usr/bin/env bash
# Build a host runtime update plan without upgrading installed packages.
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

section "GitOps checkout"
show_git_state

section "Refresh APT metadata"
sudo_required apt-get update

section "Upgradable packages"
print_upgradable_packages

section "Simulated full-upgrade"
apt-get -s full-upgrade

section "Package holds"
print_apt_holds

section "Docker package state"
print_docker_package_state

section "Raspberry Pi EEPROM"
if command_exists rpi-eeprom-update; then
  sudo_required rpi-eeprom-update || true
else
  warn "rpi-eeprom-update is not available"
fi

section "Reboot status"
print_reboot_status

section "Next actions"
echo "Apply host package updates with: make host-upgrade-apply"
echo "Apply EEPROM bootloader updates explicitly with: make host-eeprom-apply"
echo "After any required reboot, run: make postdeploy"
