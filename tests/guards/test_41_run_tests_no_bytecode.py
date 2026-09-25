# tests/guards/test_41_run_tests_no_bytecode.py
#
# Finding F49: deploy.sh runs the postdeploy suite as root, and run-tests.sh escalates to root
# on the Pi by itself, so pytest wrote root-owned __pycache__ files into the checkout. Every
# test target goes through scripts/tests/run-tests.sh, so that is where bytecode is disabled.
#
# 1) Behaviour, plain path: a fake python (via VIRTUAL_ENV) reports the variable it receives.
# 2) Contract, root path: the sudo invocation sets the variable explicitly, independent of
#    whether sudo keeps the caller's environment. That path only runs on the Pi.

from __future__ import annotations

import os
import re
import stat
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_TESTS = REPO_ROOT / "scripts/tests/run-tests.sh"


def test_plain_path_disables_bytecode(tmp_path: Path) -> None:
    fake_python = tmp_path / "venv/bin/python"
    fake_python.parent.mkdir(parents=True)
    fake_python.write_text(
        '#!/bin/sh\necho "PYTHONDONTWRITEBYTECODE=${PYTHONDONTWRITEBYTECODE:-unset}"\n',
        encoding="utf-8",
    )
    fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)

    # A fresh environment: nothing inherited from the caller (make ci may export the variable),
    # and STACK_ENV_FILE points at a file that does not exist, so no real env file is read (C3).
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(tmp_path),
        "VIRTUAL_ENV": str(tmp_path / "venv"),
        "STACK_ENV_FILE": str(tmp_path / "absent.env"),
    }
    proc = subprocess.run(
        [str(RUN_TESTS), "--version"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, f"❌ run-tests.sh failed:\n{proc.stderr}"
    assert "PYTHONDONTWRITEBYTECODE=1" in proc.stdout, (
        f"❌ pytest would run with {proc.stdout.strip()!r} (F49).\n"
        "Fix: export PYTHONDONTWRITEBYTECODE=1 in scripts/tests/run-tests.sh."
    )


def test_root_path_sets_the_variable_explicitly() -> None:
    text = RUN_TESTS.read_text(encoding="utf-8")
    sudo_lines = [line for line in text.splitlines() if re.search(r"\bsudo\s+-\w*\s+env\b", line)]
    assert sudo_lines, "❌ No `sudo … env …` invocation found in run-tests.sh; update this test."
    missing = [line.strip() for line in sudo_lines if "PYTHONDONTWRITEBYTECODE=1" not in line]
    assert not missing, (
        f"❌ The root path of run-tests.sh does not set PYTHONDONTWRITEBYTECODE=1 (F49): {missing}\n"
        "Fix: add PYTHONDONTWRITEBYTECODE=1 to the `sudo … env` assignments."
    )
