"""
F23: every test is collected by at least one gate. A test that no gate selects is dead code that
looks like coverage — the four `lint`-marked files in tests/precommit were (F23, F25), and the
cadvisor doctor check that always skipped was the same class (F47).

Each gate is collected with the selection its Makefile target passes to pytest.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = REPO_ROOT / "Makefile"
PYPROJECT = REPO_ROOT / "pyproject.toml"

# Makefile target → the pytest selection it runs, verbatim.
GATES = {
    "precommit": "tests/precommit -m precommit",
    "test": 'tests -m "not postdeploy" --ignore=tests/postdeploy --ignore=tests/precommit',
    "postdeploy": "tests/postdeploy -m postdeploy",
}
GATE_ARGS = {
    "precommit": ["tests/precommit", "-m", "precommit"],
    "test": [
        "tests",
        "-m",
        "not postdeploy",
        "--ignore=tests/postdeploy",
        "--ignore=tests/precommit",
    ],
    "postdeploy": ["tests/postdeploy", "-m", "postdeploy"],
}


def _collect(args: list[str]) -> set[str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "--collect-only", "-q", *args],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, (
        f"❌ pytest --collect-only {' '.join(args)} failed (rc={proc.returncode}):\n"
        f"{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}"
    )
    return {line.strip() for line in proc.stdout.splitlines() if "::" in line}


def test_gate_selections_match_the_makefile() -> None:
    # Guards the guard: GATES must be what the Makefile really runs.
    makefile = MAKEFILE.read_text(encoding="utf-8")
    missing = {gate: sel for gate, sel in GATES.items() if sel not in makefile}
    assert not missing, (
        f"❌ The Makefile no longer runs these pytest selections: {missing}\n"
        "Fix: update GATES and GATE_ARGS in this file to the Makefile targets."
    )


def test_every_test_is_collected_by_a_gate() -> None:
    every = _collect(["tests", "-m", ""])
    assert every, "❌ pytest collected no tests at all."
    gated = set().union(*(_collect(args) for args in GATE_ARGS.values()))
    orphans = sorted(every - gated)
    assert not orphans, (
        f"❌ {len(orphans)} tests run in no gate (F23):\n"
        + "\n".join(f" - {nodeid}" for nodeid in orphans)
        + "\nFix: give each a marker and directory that a gate selects (tests/precommit + "
        "`precommit`, tests/guards, tests/doctor, tests/postdeploy + `postdeploy`), or delete it."
    )


def test_every_registered_marker_is_used() -> None:
    # A registered marker that no test carries invites a test that no gate selects.
    declared = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["tool"]["pytest"][
        "ini_options"
    ]["markers"]
    names = [entry.split(":", 1)[0].strip() for entry in declared]
    sources = "\n".join(
        path.read_text(encoding="utf-8") for path in (REPO_ROOT / "tests").rglob("*.py")
    )
    unused = [name for name in names if not re.search(rf"\bmark\.{re.escape(name)}\b", sources)]
    assert not unused, (
        f"❌ Markers registered in pyproject.toml but used by no test: {unused}\n"
        "Fix: remove the marker from [tool.pytest.ini_options] markers."
    )
