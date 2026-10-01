# tests/guards/test_59_host_denylist.py
#
# Findings F66 part B and F67 (R1.21): postdeploy fails when a development or diagnostic tool is
# installed on the Pi, or an IDE remote server sits in a home directory
# (tests/postdeploy/test_09_host_no_dev_tools.py). The denylist lives in tests/_lib/host_denylist.py.
# These checks prove each pattern against a known package before postdeploy relies on it, and
# against the packages the Pi must keep: a pattern that is too broad would fail every deploy, one
# that is too narrow would pass with the tool still installed.

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests._lib.host_denylist import (
    IDE_SERVER_DIRS,
    PACKAGE_DENYLIST,
    denied,
    ide_server_dirs,
    present_packages,
)

# Installed on the Pi until 2026-10-01 (F66, F67 evidence) — each must be caught.
KNOWN_DENIED = (
    "bpftrace",
    "build-essential",
    "gcc",
    "g++",
    "cpp",
    "gcc-14",
    "g++-14",
    "cpp-14",
    "gcc-14-aarch64-linux-gnu",
    "cpp-14-aarch64-linux-gnu",
    "linux-headers-rpi-2712",
    "linux-headers-rpi-v8",
    "linux-headers-6.12.47+rpt-common-rpi",
    "python3-dev",
    "python3-pip",
    "python3-venv",
    "dkms",
    "bpfcc-tools",  # never on the Pi; the BCC counterpart of bpftrace for the same traces
)

# Kept on purpose (F67 "Kept on purpose") or runtime libraries a compiler pattern must not reach.
MUST_KEEP = (
    "python3",
    "python3-pytest",
    "python3-pip-whl",
    "libpython3.13",
    "git",
    "make",
    "gcc-14-base",
    "libgcc-s1",
    "libstdc++6",
    "cpp-doc",
    "linux-image-rpi-2712",
    "raspberrypi-kernel-headers-doc",
    "docker-ce",
)


@pytest.mark.parametrize("package", KNOWN_DENIED)
def test_known_tool_is_denied(package: str) -> None:
    assert package in denied([package]), (
        f"❌ {package} is not caught by PACKAGE_DENYLIST (F66, F67).\n"
        "Fix: extend the matching pattern in tests/_lib/host_denylist.py."
    )


@pytest.mark.parametrize("package", MUST_KEEP)
def test_kept_package_is_not_denied(package: str) -> None:
    assert package not in denied([package]), (
        f"❌ {package} matches the denylist ({denied([package])[package]}) but must stay on the "
        "Pi.\nFix: anchor or narrow the pattern; patterns match the whole package name."
    )


def test_every_pattern_catches_a_known_tool() -> None:
    # Guards the guard: a pattern without a known example is untested.
    unproven = [
        pattern
        for pattern, _ in PACKAGE_DENYLIST
        if not any(re.fullmatch(pattern, package) for package in KNOWN_DENIED)
    ]
    assert not unproven, (
        f"❌ Denylist patterns without an example in KNOWN_DENIED: {unproven}\n"
        "Fix: add the package that put the pattern there."
    )


def test_every_entry_names_a_finding() -> None:
    unsourced = [pattern for pattern, reason in PACKAGE_DENYLIST if not reason.startswith("F")]
    assert not unsourced, f"❌ Denylist entries without a finding: {unsourced}"


def test_present_packages_ignores_removed_and_purged() -> None:
    output = (
        "installed bpftrace\n"
        "config-files gcc-14\n"
        "not-installed python3-pip\n"
        "unpacked dkms\n"
        "half-configured cpp\n"
        "installed git\n"
    )
    assert present_packages(output) == ["bpftrace", "dkms", "cpp", "git"]


def test_ide_server_dirs_finds_only_existing(tmp_path: Path) -> None:
    admin, root = tmp_path / "admin", tmp_path / "root"
    admin.mkdir()
    root.mkdir()
    (admin / IDE_SERVER_DIRS[0]).mkdir()
    (admin / ".vscode").mkdir()  # a client settings dir is not a server
    assert ide_server_dirs([admin, root]) == [admin / IDE_SERVER_DIRS[0]]
