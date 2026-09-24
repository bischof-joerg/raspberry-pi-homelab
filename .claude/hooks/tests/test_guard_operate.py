"""Guard tests for mode `operate` (Phase 8, patch P10, cases T47-T52).

`operate` retires the transition constraints C1/C2: Claude may write inside the project, minus
`operate_write_excludes` and minus secret paths, and may run the make gates and the formatters.
Everything permanent stays: C3 (secrets), C4 (git history), C5 (Pi), self-protection, and the
inspection limits (heredocs, inline interpreter code, shell without -c).

The policy values below are the ones the operator decided on 2026-09-24. They are passed
explicitly, so these tests pin the *intended* operate policy independent of the real config.
The guard runs as a subprocess against a temporary fixture repository.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
GUARD = HOOKS_DIR / "guard.py"
CONFIG = HOOKS_DIR / "guard-config.json"

PASS = 0
BLOCK = 2

OPERATE_POLICY = {
    "mode": "operate",
    "self_protect": True,
    "operate_write_excludes": [
        "secrets",
        "logs",
        ".vscode",
        "ChatGPTHint.txt",
        "Todo.txt",
        ".git",
        ".venv",
    ],
    "operate_extra_make_targets": [
        "precommit",
        "test",
        "tests",
        "ci",
        "check",
        "ci-doctor",
        "ci-precommit",
        "ci-tests",
        "format",
        "ruff",
        "ruff-fix",
    ],
    "operate_ruff_fix_allowed": True,
}


@pytest.fixture(scope="module")
def repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = Path(os.path.realpath(tmp_path_factory.mktemp("operate-fixture")))
    for directory in (
        ".claude/scratch",
        ".claude/hooks",
        ".git/hooks",
        ".venv/bin",
        ".vscode",
        "docs",
        "logs",
        "secrets/backup/gpg",
        "stacks/monitoring/compose",
        "tests/precommit",
    ):
        (root / directory).mkdir(parents=True, exist_ok=True)
    for file in (
        "README.md",
        "Makefile",
        "Todo.txt",
        "ChatGPTHint.txt",
        "secrets/backup/gpg/key.asc",
        "stacks/monitoring/compose/.env",
        "stacks/monitoring/compose/.env.example",
        "stacks/monitoring/compose/docker-compose.yml",
    ):
        (root / file).write_text("x\n", encoding="utf-8")
    (root / ".claude/scratch/escape").symlink_to("/etc/hosts")
    return root


@pytest.fixture(scope="module")
def operate_config(tmp_path_factory: pytest.TempPathFactory) -> Path:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    config.update(OPERATE_POLICY)
    target = tmp_path_factory.mktemp("config") / "guard-config-operate.json"
    target.write_text(json.dumps(config), encoding="utf-8")
    return target


def run_guard(repo: Path, config: Path, tool: str, tool_input: dict) -> tuple[int, str]:
    event = {"tool_name": tool, "tool_input": tool_input, "cwd": str(repo)}
    result = subprocess.run(
        [sys.executable, str(GUARD), "--config", str(config)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        cwd=str(repo),
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(repo), "PYTHONDONTWRITEBYTECODE": "1"},
        timeout=30,
        check=False,
    )
    assert result.returncode in (PASS, BLOCK), f"unexpected exit {result.returncode}: {result}"
    return result.returncode, result.stderr.strip()


# T47 - file tools: the project is writable, the exclusions and the outside world are not.
@pytest.mark.precommit
@pytest.mark.parametrize(
    ("path", "expected", "reason_part"),
    [
        ("tests/precommit/test_99_new.py", PASS, ""),
        ("stacks/monitoring/compose/docker-compose.yml", PASS, ""),
        ("docs/new.md", PASS, ""),
        ("README.md", PASS, ""),
        (".claude/scratch/a.md", PASS, ""),
        ("~/.claude/plans/some-plan.md", PASS, ""),
        ("Todo.txt", BLOCK, "scope"),
        ("ChatGPTHint.txt", BLOCK, "scope"),
        (".vscode/settings.json", BLOCK, "scope"),
        ("logs/x.log", BLOCK, "scope"),
        (".git/hooks/pre-commit", BLOCK, "scope"),
        (".venv/bin/python", BLOCK, "scope"),
        ("secrets/backup/gpg/new.asc", BLOCK, "C3"),
        ("stacks/monitoring/compose/.env", BLOCK, "C3"),
        ("docs/../../outside.txt", BLOCK, "scope"),
        (".claude/scratch/escape", BLOCK, "scope"),
        ("~/.bashrc", BLOCK, "scope"),
        ("~/.ssh/config", BLOCK, "C3"),
        ("/etc/hosts", BLOCK, "scope"),
        (".claude/hooks/guard.py", BLOCK, "self-protection"),
        (".claude/settings.json", BLOCK, "self-protection"),
    ],
)
def test_t47_file_tool_write_scope(
    repo: Path, operate_config: Path, path: str, expected: int, reason_part: str
) -> None:
    target = str(Path(path).expanduser()) if path.startswith("~") else path
    code, reason = run_guard(repo, operate_config, "Write", {"file_path": target})
    assert code == expected, f"Write {path!r} -> exit {code} ({reason})"
    assert reason_part in reason


# T48 - Bash write targets follow the same scope as the file tools.
@pytest.mark.precommit
@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("echo x > docs/new.md", PASS),
        ("cp README.md docs/copy.md", PASS),
        ("sed -i s/a/b/ README.md", PASS),
        ("rm docs/new.md", PASS),
        ("echo x >> Todo.txt", BLOCK),
        ("cp README.md ~/.bashrc", BLOCK),
        ("echo x > stacks/monitoring/compose/.env", BLOCK),
        ("mv README.md .git/hooks/pre-commit", BLOCK),
        ("echo x > .claude/.gitignore", BLOCK),
        ("cp secrets/backup/gpg/key.asc docs/k", BLOCK),
    ],
)
def test_t48_bash_write_scope(
    repo: Path, operate_config: Path, command: str, expected: int
) -> None:
    code, reason = run_guard(repo, operate_config, "Bash", {"command": command})
    assert code == expected, f"{command!r} -> exit {code} ({reason})"


# T49 - the make gates and the formatters are open; venv, Pi and backup targets are not.
@pytest.mark.precommit
@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("make ci", PASS),
        ("make precommit", PASS),
        ("make test", PASS),
        ("make check", PASS),
        ("make ci-tests", PASS),
        ("make format", PASS),
        ("make ruff-fix", PASS),
        ("make doctor", PASS),
        ("ruff check --fix .", PASS),
        ("ruff format .", PASS),
        (".venv/bin/ruff check --fix --no-cache .", PASS),
        ("make", BLOCK),
        ("make venv", BLOCK),
        ("make venv-clean", BLOCK),
        ("make hooks", BLOCK),
        ("make postdeploy", BLOCK),
        ("make backup", BLOCK),
        ("make restore", BLOCK),
        ("make renovate-apply", BLOCK),
        ("pre-commit run --all-files", BLOCK),
        ("pip install requests", BLOCK),
        ("docker compose up -d", BLOCK),
    ],
)
def test_t49_make_and_tool_policy(
    repo: Path, operate_config: Path, command: str, expected: int
) -> None:
    code, reason = run_guard(repo, operate_config, "Bash", {"command": command})
    assert code == expected, f"{command!r} -> exit {code} ({reason})"


# T50 - C3, C4, C5 are permanent and hold unchanged in operate mode.
@pytest.mark.precommit
@pytest.mark.parametrize(
    ("command", "constraint"),
    [
        ("git commit -m x", "C4"),
        ('bash -c "git push"', "C4"),
        ("gh pr create", "C4"),
        ("ssh rpi-hub true", "C5"),
        ("curl -fsS http://192.168.178.29:3000/api/health", "C5"),
        ("./deploy.sh", "C5"),
        ("sudo true", "C5"),
        ("bash scripts/network/cleanup-ufw.sh", "C5"),
        ("cat secrets/backup/gpg/key.asc", "C3"),
        ("cat stacks/monitoring/compose/.env", "C3"),
    ],
)
def test_t50_permanent_constraints_hold(
    repo: Path, operate_config: Path, command: str, constraint: str
) -> None:
    code, reason = run_guard(repo, operate_config, "Bash", {"command": command})
    assert code == BLOCK, f"{command!r} passed in operate mode"
    assert constraint in reason, f"{command!r} -> {reason}"


@pytest.mark.precommit
def test_t50_secret_read_tool_holds(repo: Path, operate_config: Path) -> None:
    code, reason = run_guard(
        repo, operate_config, "Read", {"file_path": "secrets/backup/gpg/key.asc"}
    )
    assert code == BLOCK
    assert "C3" in reason


# T51 - inspection limits stay, but no longer claim a transition constraint.
@pytest.mark.precommit
@pytest.mark.parametrize(
    "command",
    [
        "bash <<'EOF'\necho hi\nEOF\n",
        "python3 -c \"open('x','w')\"",
        "bash scripts/tests/run-tests.sh",
        "find . -name '*.pyc' -delete",
    ],
)
def test_t51_inspection_limits_stay(repo: Path, operate_config: Path, command: str) -> None:
    code, reason = run_guard(repo, operate_config, "Bash", {"command": command})
    assert code == BLOCK, f"{command!r} passed in operate mode"
    assert "C1" not in reason and "C2" not in reason and "transition" not in reason, reason


# T52 - the operate-only keys have no effect in transition mode.
@pytest.mark.precommit
@pytest.mark.parametrize("command", ["make ci", "ruff check --fix ."])
def test_t52_operate_keys_are_inert_in_transition(repo: Path, tmp_path: Path, command: str) -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    config.update({**OPERATE_POLICY, "mode": "transition"})
    path = tmp_path / "guard-config-transition.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    code, reason = run_guard(repo, path, "Bash", {"command": command})
    assert code == BLOCK, f"{command!r} passed in transition mode"
    assert "C2" in reason
