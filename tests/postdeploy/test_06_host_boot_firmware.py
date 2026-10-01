# tests/postdeploy/test_06_host_boot_firmware.py
#
# Finding F60 (R1.15): deploy.sh installs the APT hook that remounts the read-only /boot/firmware
# read-write only while dpkg runs (scripts/host/ensure-apt-boot-firmware-hook.sh). These checks prove
# on the Pi that the installed files equal the repository, are root-owned, and that the partition
# is read-only again after the deploy. The static contract is tests/guards/test_55_boot_firmware_hook.py.
#
# R1.17 adds the state F60 left behind unnoticed: dpkg has no half-configured package, and the boot
# files in /boot/firmware are those of the running kernel. The check is strict: after a kernel
# update it fails until the reboot (docs/operations/runtime-updates.md §1.5). The classification
# is proven by tests/guards/test_56_boot_firmware_files.py.

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from tests._helpers import REPO_ROOT, run
from tests._lib.boot_firmware import FIRMWARE_FILES, check_boot_files, flavour

pytestmark = pytest.mark.postdeploy

ENSURE = REPO_ROOT / "scripts/host/ensure-apt-boot-firmware-hook.sh"
MOUNTPOINT = "/boot/firmware"
BOOT = Path("/boot")
INSTALLED = {
    Path("/etc/apt/apt.conf.d/99homelab-boot-firmware"): 0o644,
    Path("/usr/local/sbin/homelab-boot-firmware"): 0o755,
}


def test_apt_hook_matches_the_repository() -> None:
    res = run([str(ENSURE), "check"])
    assert res.returncode == 0, (
        f"❌ The APT boot-firmware hook on the Pi differs from the repository (F60):\n"
        f"{res.stdout}{res.stderr}\nFix: sudo ./deploy.sh (it runs `{ENSURE.name} apply`)."
    )


@pytest.mark.parametrize("path", list(INSTALLED), ids=lambda p: p.name)
def test_installed_hook_file_is_root_owned(path: Path) -> None:
    st = path.stat()
    mode = stat.S_IMODE(st.st_mode)
    assert (st.st_uid, st.st_gid, mode) == (0, 0, INSTALLED[path]), (
        f"❌ {path}: owner {st.st_uid}:{st.st_gid} mode {mode:o}, expected 0:0 "
        f"{INSTALLED[path]:o} (F60). APT runs the hook as root; a file another user can write is "
        "a path to root.\nFix: sudo ./deploy.sh."
    )


def test_boot_firmware_is_read_only_after_deploy() -> None:
    if not os.path.ismount(MOUNTPOINT):
        pytest.fail(f"❌ {MOUNTPOINT} is not mounted (F60); the Pi cannot boot-update without it.")
    res = run(["findmnt", "-no", "OPTIONS", MOUNTPOINT])
    assert res.returncode == 0, f"❌ findmnt {MOUNTPOINT} failed:\n{res.stderr}"
    first = res.stdout.strip().split(",")[0]
    assert first == "ro", (
        f"❌ {MOUNTPOINT} is mounted '{first}', expected 'ro' (F60, /etc/fstab).\n"
        "An APT run probably ended without its DPkg::Post-Invoke (see "
        "`journalctl -t homelab-boot-firmware`).\nFix: sudo mount -o remount,ro /boot/firmware "
        "once no process writes to it."
    )


def test_dpkg_audit_is_empty() -> None:
    res = run(["dpkg", "--audit"])
    assert res.returncode == 0 and not res.stdout.strip(), (
        f"❌ `dpkg --audit` reports packages in an unfinished state (F60), exit {res.returncode}:\n"
        f"{res.stdout}{res.stderr}\nEvery further APT run fails until they are configured.\n"
        "Fix: sudo apt-get -f install (never `dpkg --configure`: dpkg alone bypasses the "
        "/boot/firmware hook, ADR-0013)."
    )


@pytest.mark.parametrize("name", list(FIRMWARE_FILES["2712"]))
def test_firmware_boot_file_matches_running_kernel(name: str) -> None:
    release = os.uname().release
    try:
        flavour(release)
    except ValueError as e:
        pytest.fail(f"❌ {e} (F60); this check knows only the Pi 5 kernel.")
    s = check_boot_files(BOOT, Path(MOUNTPOINT), release)[name]
    if s.state == "reboot-pending":
        detail = (
            f"{s.firmware} holds the {name} of {s.other_release}, but {release} is running.\n"
            "A kernel update is waiting for its reboot; the new boot path is untested.\n"
            "Fix: sudo reboot, then make postdeploy."
        )
    elif s.state == "copy-failed":
        detail = (
            f"{s.firmware} equals neither {s.expected} nor any other installed {name}.\n"
            "The copy into /boot/firmware failed or was changed by hand. Check the hook "
            "(test_apt_hook_matches_the_repository, `journalctl -t homelab-boot-firmware`).\n"
            "Fix: reinstall the kernel package with apt-get, after a reviewed host-upgrade plan."
        )
    elif s.state == "missing":
        detail = f"{s.missing} does not exist.\nFix: check the kernel packages before a reboot."
    else:
        return
    pytest.fail(f"❌ Boot file '{name}' does not match the running kernel (F60):\n{detail}")
