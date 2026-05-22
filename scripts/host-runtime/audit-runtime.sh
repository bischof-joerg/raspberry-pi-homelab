#!/usr/bin/env bash
# Audit the Raspberry Pi host runtime without changing installed packages.
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

section "Host identity"
if [ -r /proc/device-tree/model ]; then
  tr -d '\0' </proc/device-tree/model
  printf '\n'
fi
cat /etc/os-release
uname -a
uptime || true

section "GitOps checkout"
show_git_state

section "APT state"
print_upgradable_packages
print_apt_holds
print_reboot_status

section "Raspberry Pi EEPROM"
if command_exists rpi-eeprom-update; then
  sudo_optional rpi-eeprom-update || true
else
  warn "rpi-eeprom-update is not available"
fi

section "Docker runtime"
print_docker_versions
if command_exists docker; then
  docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' || true
  docker compose ls || true
  docker network ls || true
fi

section "Systemd health"
systemctl --failed --no-pager || true
journalctl -p err -b -n 50 --no-pager || true

section "Storage and memory"
df -h
free -h
for mountpoint in / /boot /boot/firmware /srv; do
  if findmnt "$mountpoint" >/dev/null 2>&1; then
    findmnt -no SOURCE,TARGET,FSTYPE,OPTIONS "$mountpoint" || true
  fi
done

section "Firewall"
if command_exists ufw; then
  sudo_optional ufw status verbose || true
else
  warn "ufw is not available"
fi
