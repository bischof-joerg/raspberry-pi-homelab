# tests/postdeploy/test_09_host_no_dev_tools.py
#
# Findings F66 part B and F67 (R1.21): the Pi is a deploy target only (.claude/CLAUDE.md §1). No
# development or diagnostic tool may stay installed after a measurement, and no IDE remote server
# may sit in a home directory. The denylist and its proof are tests/_lib/host_denylist.py and
# tests/guards/test_59_host_denylist.py. A tool a measurement needs is installed and removed as
# separate, proven steps (IN18) — never left for this check to find.

from __future__ import annotations

import os
import pwd
from pathlib import Path

import pytest

from tests._helpers import REPO_ROOT, run
from tests._lib.host_denylist import denied, ide_server_dirs, present_packages

pytestmark = pytest.mark.postdeploy


def test_no_denylisted_package_is_installed() -> None:
    res = run(["dpkg-query", "-W", "-f", "${db:Status-Status} ${Package}\\n"])
    assert res.returncode == 0, f"❌ dpkg-query failed:\n{res.stderr}"
    packages = present_packages(res.stdout)
    assert packages, (
        f"❌ dpkg-query listed no package; the parser does not fit:\n{res.stdout[:500]}"
    )
    hits = denied(packages)
    assert not hits, (
        "❌ Development or diagnostic tools are installed on the Pi (F66, F67):\n"
        + "\n".join(f" - {pkg}: {reason}" for pkg, reason in sorted(hits.items()))
        + f"\nFix: sudo apt-get -s purge --autoremove {' '.join(sorted(hits))} (simulate first), "
        "then without -s; a tool a measurement needs is removed before the deploy (IN18)."
    )


def test_no_ide_server_in_a_home_directory() -> None:
    if os.geteuid() != 0:
        pytest.skip("needs root to read /root; postdeploy runs as root through deploy.sh")
    owner_home = Path(pwd.getpwuid(REPO_ROOT.stat().st_uid).pw_dir)
    found = ide_server_dirs([owner_home, Path("/root")])
    assert not found, (
        f"❌ IDE remote servers on the Pi (F67): {[str(p) for p in found]}\n"
        "Development happens in WSL only.\nFix: sudo rm -rf " + " ".join(map(str, found))
    )
