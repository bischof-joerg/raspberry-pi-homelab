"""Guard tests for write/read operand classification (patch of section 5.4.5, C1 row).

Covers the cases the first guard version got wrong: `cp`/`mv`/`ln`/`install` write only to
their last operand, `sed -i` takes a script before its file operands, `dd` writes only to
`of=`, and self-protected paths must report self-protection rather than a plain C1 violation.

The guard is invoked as a subprocess against a temporary fixture repository, so no file of
the real repository is touched.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests._helpers import REPO_ROOT

GUARD = REPO_ROOT / ".claude" / "hooks" / "guard.py"
CONFIG = REPO_ROOT / ".claude" / "hooks" / "guard-config.json"

PASS = 0
BLOCK = 2


@pytest.fixture(scope="module")
def fixture_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Minimal repository layout the guard resolves paths against."""
    root = tmp_path_factory.mktemp("guard-fixture")
    for directory in (
        ".claude/scratch",
        ".claude/hooks",
        "docs",
        "secrets/backup/gpg",
        "stacks/monitoring/compose",
    ):
        (root / directory).mkdir(parents=True, exist_ok=True)
    for file in (
        "README.md",
        "Makefile",
        "secrets/backup/gpg/key.asc",
        "stacks/monitoring/compose/.env",
        "stacks/monitoring/compose/.env.example",
        ".claude/scratch/a.md",
    ):
        (root / file).write_text("x\n", encoding="utf-8")
    return root


def write_config(tmp_path: Path, **overrides: object) -> Path:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    config.update(overrides)
    target = tmp_path / "guard-config.json"
    target.write_text(json.dumps(config), encoding="utf-8")
    return target


def run_guard(
    repo: Path, tool: str, tool_input: dict, config: Path | None = None
) -> tuple[int, str]:
    event = {"tool_name": tool, "tool_input": tool_input, "cwd": str(repo)}
    argv = [sys.executable, str(GUARD)]
    if config is not None:
        argv += ["--config", str(config)]
    result = subprocess.run(
        argv,
        input=json.dumps(event),
        capture_output=True,
        text=True,
        cwd=str(repo),
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(repo), "PYTHONDONTWRITEBYTECODE": "1"},
        timeout=30,
        check=False,
    )
    return result.returncode, result.stderr.strip()


def bash(repo: Path, command: str, config: Path | None = None) -> tuple[int, str]:
    return run_guard(repo, "Bash", {"command": command}, config)


@pytest.mark.precommit
@pytest.mark.parametrize(
    ("command", "expected"),
    [
        # sources may live anywhere; only the target must be inside .claude/
        ("cp README.md .claude/scratch/copy.md", PASS),
        ("cp README.md Makefile .claude/scratch/", PASS),
        ("mv README.md .claude/scratch/moved.md", PASS),
        ("ln -s /tmp/x .claude/scratch/link", PASS),
        # the target decides
        ("cp .claude/scratch/a.md docs/copy.md", BLOCK),
        ("cp README.md docs/copy.md", BLOCK),
        ("mv .claude/scratch/a.md docs/a.md", BLOCK),
        ("ln -s /etc/passwd docs/pw", BLOCK),
        ("install -m 644 README.md /etc/x", BLOCK),
        # sed: script operand is not a path
        ("sed -i s/a/b/ .claude/scratch/a.md", PASS),
        ("sed -n 1,20p Makefile", PASS),
        ("sed -i s/a/b/ README.md", BLOCK),
        ("sed -i -e s/a/b/ README.md", BLOCK),
        # dd: only of= is a write target
        ("dd if=/dev/zero of=.claude/scratch/d.bin", PASS),
        ("dd if=/dev/zero of=README.md", BLOCK),
        # unchanged behaviour of the other write heads
        ("echo x | tee .claude/scratch/t.txt", PASS),
        ("echo x | tee README.md", BLOCK),
        ("rm .claude/scratch/a.md", PASS),
        ("rm README.md", BLOCK),
        ("chmod 600 .claude/scratch/a.md", PASS),
        ("chmod 644 README.md", BLOCK),
    ],
)
def test_write_targets(fixture_repo: Path, command: str, expected: int) -> None:
    code, reason = bash(fixture_repo, command)
    assert code == expected, f"{command!r} -> exit {code} ({reason})"


@pytest.mark.precommit
@pytest.mark.parametrize(
    "command",
    [
        "cp secrets/backup/gpg/key.asc .claude/scratch/k",
        "mv stacks/monitoring/compose/.env .claude/scratch/e",
        "dd if=secrets/backup/gpg/key.asc of=.claude/scratch/k",
    ],
)
def test_secret_sources_are_blocked(fixture_repo: Path, command: str) -> None:
    code, reason = bash(fixture_repo, command)
    assert code == BLOCK
    assert "C3" in reason


@pytest.mark.precommit
def test_env_example_stays_readable(fixture_repo: Path) -> None:
    code, _ = bash(fixture_repo, "cat stacks/monitoring/compose/.env.example")
    assert code == PASS


@pytest.mark.precommit
@pytest.mark.parametrize(
    "command",
    [
        "sed -i s/a/b/ .claude/hooks/guard.py",
        "cp /tmp/x .claude/settings.json",
        "rm .claude/hooks/guard-config.json",
    ],
)
def test_self_protection_reports_itself(fixture_repo: Path, tmp_path: Path, command: str) -> None:
    config = write_config(tmp_path, self_protect=True)
    code, reason = bash(fixture_repo, command, config)
    assert code == BLOCK
    assert "self-protection" in reason


@pytest.mark.precommit
def test_find_exec_placeholder_has_actionable_reason(fixture_repo: Path) -> None:
    code, reason = bash(fixture_repo, "find . -name x -exec rm {} \\;")
    assert code == BLOCK
    assert "find" in reason


@pytest.mark.precommit
def test_gh_is_reported_as_operator_only(fixture_repo: Path) -> None:
    code, reason = bash(fixture_repo, "gh pr create")
    assert code == BLOCK
    assert "C4" in reason
