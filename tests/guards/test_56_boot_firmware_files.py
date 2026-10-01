# tests/guards/test_56_boot_firmware_files.py
#
# Finding F60 (R1.17): postdeploy checks that the boot files in /boot/firmware are those of the
# running kernel (tests/postdeploy/test_06_host_boot_firmware.py). On a healthy Pi every file
# matches, so the classification is exercised here against fake /boot and /boot/firmware trees
# under tmp_path. Hashes measured on the Pi (F60): after R1.15 initramfs_2712 changed while
# kernel_2712.img did not - each file is judged on its own.

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.xfail(
    strict=True, reason="R1.17 (F60): boot-file classification not implemented yet"
)

RUNNING = "6.18.29+rpt-rpi-2712"
NEWER = "6.18.30+rpt-rpi-2712"


def _check(boot: Path, firmware: Path, release: str = RUNNING):
    from tests._lib.boot_firmware import check_boot_files

    return check_boot_files(boot, firmware, release)


def _tree(tmp_path: Path) -> tuple[Path, Path]:
    """A /boot with the running kernel and a /boot/firmware holding exactly its files."""
    boot = tmp_path / "boot"
    firmware = boot / "firmware"
    firmware.mkdir(parents=True)
    (boot / f"vmlinuz-{RUNNING}").write_bytes(b"kernel running")
    (boot / f"initrd.img-{RUNNING}").write_bytes(b"initramfs running")
    (firmware / "kernel_2712.img").write_bytes(b"kernel running")
    (firmware / "initramfs_2712").write_bytes(b"initramfs running")
    return boot, firmware


def test_flavour_is_read_from_the_release_suffix() -> None:
    from tests._lib.boot_firmware import flavour

    assert flavour(RUNNING) == "2712"


@pytest.mark.parametrize("release", ["6.18.29+rpt-rpi-v7", "6.1.0-generic"])
def test_unknown_release_is_refused_by_name(release: str) -> None:
    from tests._lib.boot_firmware import flavour

    with pytest.raises(ValueError, match=release.replace("+", r"\+")):
        flavour(release)


def test_files_of_the_running_kernel_match(tmp_path: Path) -> None:
    status = _check(*_tree(tmp_path))
    assert {name: s.state for name, s in status.items()} == {
        "kernel": "match",
        "initramfs": "match",
    }


def test_files_of_another_installed_kernel_mean_reboot_pending(tmp_path: Path) -> None:
    boot, firmware = _tree(tmp_path)
    (boot / f"vmlinuz-{NEWER}").write_bytes(b"kernel newer")
    (boot / f"initrd.img-{NEWER}").write_bytes(b"initramfs newer")
    (firmware / "kernel_2712.img").write_bytes(b"kernel newer")
    (firmware / "initramfs_2712").write_bytes(b"initramfs newer")
    status = _check(boot, firmware)
    assert {name: (s.state, s.other_release) for name, s in status.items()} == {
        "kernel": ("reboot-pending", NEWER),
        "initramfs": ("reboot-pending", NEWER),
    }


def test_files_of_no_installed_kernel_mean_copy_failed(tmp_path: Path) -> None:
    boot, firmware = _tree(tmp_path)
    (firmware / "kernel_2712.img").write_bytes(b"stale kernel")
    status = _check(boot, firmware)
    assert (status["kernel"].state, status["kernel"].other_release) == ("copy-failed", None)


@pytest.mark.parametrize(
    "remove", ["firmware/kernel_2712.img", f"initrd.img-{RUNNING}"], ids=["firmware", "boot"]
)
def test_missing_file_is_a_named_finding(tmp_path: Path, remove: str) -> None:
    boot, firmware = _tree(tmp_path)
    (boot / remove).unlink()
    status = _check(boot, firmware)
    [missing] = [s for s in status.values() if s.state == "missing"]
    assert missing.missing == boot / remove


def test_kernel_and_initramfs_are_judged_separately(tmp_path: Path) -> None:
    boot, firmware = _tree(tmp_path)
    (boot / f"initrd.img-{NEWER}").write_bytes(b"initramfs newer")
    (firmware / "initramfs_2712").write_bytes(b"initramfs newer")
    status = _check(boot, firmware)
    assert (status["kernel"].state, status["initramfs"].state) == ("match", "reboot-pending")
