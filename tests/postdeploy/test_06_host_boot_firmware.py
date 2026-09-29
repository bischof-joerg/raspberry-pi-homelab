# tests/postdeploy/test_06_host_boot_firmware.py
#
# Finding F60 (R1.15): deploy.sh installs the APT hook that remounts the read-only /boot/firmware
# read-write only while dpkg runs (scripts/host/ensure-apt-boot-firmware-hook.sh). These checks prove
# on the Pi that the installed files equal the repository, are root-owned, and that the partition
# is read-only again after the deploy. The static contract is tests/guards/test_55_boot_firmware_hook.py.

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from tests._helpers import REPO_ROOT, run

pytestmark = pytest.mark.postdeploy

ENSURE = REPO_ROOT / "scripts/host/ensure-apt-boot-firmware-hook.sh"
MOUNTPOINT = "/boot/firmware"
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
