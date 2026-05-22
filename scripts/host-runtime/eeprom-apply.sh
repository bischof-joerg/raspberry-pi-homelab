#!/usr/bin/env bash
# Apply Raspberry Pi EEPROM bootloader updates explicitly.
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
require_command rpi-eeprom-update
require_clean_git_tree

section "Current EEPROM state"
sudo_required rpi-eeprom-update || true

section "Apply EEPROM update"
sudo_required rpi-eeprom-update -a

section "EEPROM state after apply command"
sudo_required rpi-eeprom-update || true

section "Reboot status"
print_reboot_status

echo "EEPROM apply command completed. Reboot the Pi to activate a pending bootloader update."
echo "After reboot, run: make postdeploy"
