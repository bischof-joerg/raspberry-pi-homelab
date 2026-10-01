from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

# Per flavour: file in /boot/firmware -> prefix of the matching file in /boot (F60, measured on
# the Pi 5 on 2026-09-29). Only flavours measured on this host are listed.
FIRMWARE_FILES: dict[str, dict[str, tuple[str, str]]] = {
    "2712": {
        "kernel": ("kernel_2712.img", "vmlinuz-"),
        "initramfs": ("initramfs_2712", "initrd.img-"),
    },
}

_FLAVOUR = re.compile(r"-rpi-([0-9a-z]+)$")


@dataclass(frozen=True)
class BootFileStatus:
    """state: match | reboot-pending | copy-failed | missing."""

    state: str
    firmware: Path
    expected: Path
    other_release: str | None = None
    missing: Path | None = None


def flavour(release: str) -> str:
    m = _FLAVOUR.search(release)
    if not m or m.group(1) not in FIRMWARE_FILES:
        raise ValueError(
            f"Kernel release {release!r} has no known Raspberry Pi flavour "
            f"(known: {', '.join(sorted(FIRMWARE_FILES))})"
        )
    return m.group(1)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _status(boot: Path, firmware_file: Path, prefix: str, release: str, flav: str):
    expected = boot / f"{prefix}{release}"
    for path in (firmware_file, expected):
        if not path.is_file():
            return BootFileStatus("missing", firmware_file, expected, missing=path)
    digest = _sha256(firmware_file)
    if digest == _sha256(expected):
        return BootFileStatus("match", firmware_file, expected)
    for other in sorted(boot.glob(f"{prefix}*-rpi-{flav}")):
        if other != expected and other.is_file() and _sha256(other) == digest:
            other_release = other.name.removeprefix(prefix)
            return BootFileStatus("reboot-pending", firmware_file, expected, other_release)
    return BootFileStatus("copy-failed", firmware_file, expected)


def check_boot_files(boot: Path, firmware: Path, release: str) -> dict[str, BootFileStatus]:
    """
    Compare the boot files in `firmware` with those of the running kernel `release` in `boot`.
    Read-only: hashes files, never writes.
    """
    flav = flavour(release)
    return {
        name: _status(boot, firmware / fw_name, prefix, release, flav)
        for name, (fw_name, prefix) in FIRMWARE_FILES[flav].items()
    }
