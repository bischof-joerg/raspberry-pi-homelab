"""What must not be on the Pi: development and diagnostic tools (F66 part B, F67).

The Pi is a deploy target only (.claude/CLAUDE.md §1). Each pattern is matched against the whole
Debian package name; every entry names the finding whose evidence put it here. A new entry needs
a known example and, if it is broad, a package it must not match — both in
tests/guards/test_59_host_denylist.py, which proves the patterns before postdeploy relies on them.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

# (pattern, reason). Optional `-<arch>-linux-gnu` suffix: Debian splits compilers per architecture.
PACKAGE_DENYLIST: tuple[tuple[str, str], ...] = (
    (r"bpftrace", "F66: tracing tool installed for R1.19 and left behind"),
    (r"bpfcc-tools", "F66: tracing tool"),
    (r"build-essential", "F67: compiler meta package"),
    (r"(gcc|g\+\+|cpp)(-\d+)?(-[a-z0-9_]+-linux-gnu)?", "F67: compiler chain"),
    (r"dkms", "F67: builds kernel modules on the host"),
    (r"linux-headers-.+", "F67: kernel headers, only needed to build modules"),
    (r"python3-(dev|pip|venv)", "F67: Python development; the Pi runs no virtualenv"),
)

# IDE remote servers, installed into a home directory by the first remote connection (F67).
IDE_SERVER_DIRS: tuple[str, ...] = (".vscode-server", ".vscode-server-insiders", ".cursor-server")

# dpkg states in which no files of the package are left except its configuration.
_ABSENT_STATES = {"not-installed", "config-files"}

_COMPILED = [(re.compile(pattern), reason) for pattern, reason in PACKAGE_DENYLIST]


def present_packages(dpkg_output: str) -> list[str]:
    """Parse `dpkg-query -W -f '${db:Status-Status} ${Package}\\n'` into present package names."""
    present = []
    for line in dpkg_output.splitlines():
        state, _, package = line.strip().partition(" ")
        if package and state not in _ABSENT_STATES:
            present.append(package)
    return present


def denied(packages: Iterable[str]) -> dict[str, str]:
    """Map every denylisted package to the reason of the first pattern that matches it."""
    hits = {}
    for package in packages:
        for pattern, reason in _COMPILED:
            if pattern.fullmatch(package):
                hits[package] = reason
                break
    return hits


def ide_server_dirs(homes: Iterable[Path]) -> list[Path]:
    """Every IDE server directory that exists in one of `homes`."""
    return [home / name for home in homes for name in IDE_SERVER_DIRS if (home / name).exists()]
