# tests/guards/test_42_ensure_venv.py
#
# Finding F21: `make venv` must install a pinned pip and be idempotent. Every quality-gate target
# depends on `venv`, so one `make ci` used to upgrade pip, unpinned, seven times.
#
# scripts/dev/ensure-venv.sh runs here against a stub python in tmp_path: the stub records every
# call and creates a stub venv, so nothing touches the network or the repository .venv.

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ENSURE_VENV = REPO_ROOT / "scripts/dev/ensure-venv.sh"

STUB_PYTHON = """#!/bin/sh
echo "$*" >> "$STUB_LOG"
if [ "$1" = "-m" ] && [ "$2" = "venv" ]; then
  mkdir -p "$3/bin" && cp "$0" "$3/bin/python"
  exit 0
fi
if [ "$1" = "--version" ]; then
  echo "Python ${STUB_PY_VERSION:-3.12.3}"
  exit 0
fi
if [ "$1" = "-m" ] && [ "$2" = "pip" ]; then
  exit "${STUB_PIP_EXIT:-0}"
fi
exit 0
"""


@pytest.fixture
def sandbox(tmp_path: Path) -> dict[str, Path]:
    python = tmp_path / "bin/python3"
    python.parent.mkdir()
    python.write_text(STUB_PYTHON, encoding="utf-8")
    python.chmod(python.stat().st_mode | stat.S_IXUSR)
    requirements = tmp_path / "requirements-dev.txt"
    requirements.write_text("-c constraints-dev.txt\npytest==8.4.2\n", encoding="utf-8")
    constraints = tmp_path / "constraints-dev.txt"
    constraints.write_text("pip==26.2.1\npluggy==1.6.0\n", encoding="utf-8")
    return {
        "python": python,
        "venv": tmp_path / "venv",
        "requirements": requirements,
        "constraints": constraints,
        "log": tmp_path / "calls.log",
    }


def _run(box: dict[str, Path], **extra: str) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(box["venv"].parent),
        "PYTHON": str(box["python"]),
        "VENV_DIR": str(box["venv"]),
        "REQUIREMENTS_FILE": str(box["requirements"]),
        "CONSTRAINTS_FILE": str(box["constraints"]),
        "STUB_LOG": str(box["log"]),
        **extra,
    }
    return subprocess.run(
        [str(ENSURE_VENV)], cwd=REPO_ROOT, env=env, text=True, capture_output=True, check=False
    )


def _pip_calls(box: dict[str, Path]) -> list[str]:
    if not box["log"].exists():
        return []
    return [
        line for line in box["log"].read_text(encoding="utf-8").splitlines() if "-m pip" in line
    ]


def test_first_run_installs_pinned_pip_then_requirements(sandbox: dict[str, Path]) -> None:
    proc = _run(sandbox)
    assert proc.returncode == 0, f"❌ ensure-venv.sh failed:\n{proc.stdout}{proc.stderr}"
    assert (sandbox["venv"] / "bin/python").exists(), "❌ No venv was created."
    calls = _pip_calls(sandbox)
    expected = [
        f"-m pip install -c {sandbox['constraints']} pip",
        f"-m pip install -r {sandbox['requirements']}",
    ]
    assert [" ".join(c.split()) for c in calls] == expected, (
        f"❌ pip calls were {calls} (F21).\n"
        f"Expected, in order: {expected}\n"
        "Fix: install pip under the constraints file first, then only requirements-dev.txt."
    )


def test_second_run_calls_no_pip(sandbox: dict[str, Path]) -> None:
    assert _run(sandbox).returncode == 0
    first = len(_pip_calls(sandbox))
    proc = _run(sandbox)
    assert proc.returncode == 0, f"❌ Second run failed:\n{proc.stdout}{proc.stderr}"
    assert len(_pip_calls(sandbox)) == first, (
        f"❌ The second run called pip again (F21): {_pip_calls(sandbox)[first:]}\n"
        "Fix: skip the install when the stamp matches the pin files and the Python version."
    )
    assert "up to date" in proc.stdout, f"❌ No 'up to date' message:\n{proc.stdout}"


@pytest.mark.parametrize("change", ["constraints", "requirements", "python"])
def test_a_changed_input_triggers_a_reinstall(sandbox: dict[str, Path], change: str) -> None:
    assert _run(sandbox).returncode == 0
    first = len(_pip_calls(sandbox))
    extra = {}
    if change == "python":
        extra["STUB_PY_VERSION"] = "3.12.9"
    else:
        sandbox[change].write_text(
            sandbox[change].read_text(encoding="utf-8") + "# changed\n", encoding="utf-8"
        )
    assert _run(sandbox, **extra).returncode == 0
    assert len(_pip_calls(sandbox)) == first + 2, (
        f"❌ Changing the {change} did not reinstall (F21).\n"
        "Fix: the stamp must cover requirements-dev.txt, constraints-dev.txt and the Python version."
    )


def test_failed_install_leaves_no_stamp(sandbox: dict[str, Path]) -> None:
    proc = _run(sandbox, STUB_PIP_EXIT="1")
    assert proc.returncode != 0, "❌ ensure-venv.sh exited 0 although pip failed."
    first = len(_pip_calls(sandbox))
    assert _run(sandbox).returncode == 0
    assert len(_pip_calls(sandbox)) > first, (
        "❌ After a failed install the next run skipped pip (F21).\n"
        "Fix: write the stamp only after both installs succeeded."
    )
