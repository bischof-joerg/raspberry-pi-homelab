"""Test matrix T01-T35 for the PreToolUse guard (.claude/ClaudeTransition.md 5.4.6).

Every case runs `guard.py` as a subprocess with crafted stdin JSON and `CLAUDE_PROJECT_DIR`
pointing at a temporary fixture repository, so no file of the real repository is touched and
the guard's decision log is written inside `tmp_path`.

Run: PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider -q .claude/hooks/tests
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

BLOCK = 2
PASS = 0

# P7: every call runs against a copy of the real config with the mode pinned, so the matrix
# keeps testing the transition policy after the operator switches guard-config.json to operate.
TRANSITION_CONFIG: Path | None = None


def pinned_config(directory: Path, mode: str = "transition", **overrides: object) -> Path:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    config.update({"mode": mode, **overrides})
    target = directory / f"guard-config-{mode}.json"
    target.write_text(json.dumps(config), encoding="utf-8")
    return target


@pytest.fixture(autouse=True, scope="module")
def _pin_transition_mode(tmp_path_factory: pytest.TempPathFactory) -> None:
    global TRANSITION_CONFIG
    TRANSITION_CONFIG = pinned_config(tmp_path_factory.mktemp("config"))


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A minimal fixture repository that mirrors the paths the guard reasons about."""
    root = Path(os.path.realpath(tmp_path))
    for directory in (
        ".claude/scratch",
        "stacks/monitoring/compose",
        "scripts/network",
        "secrets/backup/gpg",
        "tests/precommit",
    ):
        (root / directory).mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text("readme\n", encoding="utf-8")
    (root / "Makefile").write_text("doctor:\n\t@true\n", encoding="utf-8")
    (root / "stacks/monitoring/compose/.env").write_text("SECRET=1\n", encoding="utf-8")
    (root / "stacks/monitoring/compose/.env.example").write_text("SECRET=\n", encoding="utf-8")
    (root / "scripts/network/cleanup-ufw.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (root / "secrets/backup/gpg/key.asc").write_text("key\n", encoding="utf-8")
    (root / ".claude/scratch/link").symlink_to("../../Makefile")
    return root


def guard(repo: Path, tool_name: str, tool_input: dict, config: Path | None = None) -> int:
    payload = json.dumps(
        {
            "hook_event_name": "PreToolUse",
            "cwd": str(repo),
            "tool_name": tool_name,
            "tool_input": tool_input,
        }
    )
    return _run(repo, payload, config)


def bash(repo: Path, command: str) -> int:
    return guard(repo, "Bash", {"command": command})


def _run(repo: Path, payload: str, config: Path | None = None) -> int:
    argv = [sys.executable, str(GUARD), "--config", str(config or TRANSITION_CONFIG)]
    env = os.environ | {"CLAUDE_PROJECT_DIR": str(repo), "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run(
        argv,
        input=payload,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(repo),
        check=False,
    )
    assert result.returncode in (PASS, BLOCK), f"unexpected exit {result.returncode}: {result}"
    if result.returncode == BLOCK:
        assert result.stderr.strip().startswith("guard:"), result.stderr
    return result.returncode


def test_t01_write_inside_claude_scratch(repo: Path) -> None:
    assert guard(repo, "Write", {"file_path": ".claude/scratch/a.md"}) == PASS


def test_t02_write_readme_is_blocked(repo: Path) -> None:
    assert guard(repo, "Write", {"file_path": "README.md"}) == BLOCK


def test_t03_edit_escaping_claude_via_parent(repo: Path) -> None:
    assert guard(repo, "Edit", {"file_path": ".claude/../stacks/x.yml"}) == BLOCK


def test_t04_write_through_symlink_out_of_claude(repo: Path) -> None:
    assert guard(repo, "Write", {"file_path": ".claude/scratch/link"}) == BLOCK


def test_t05_self_protection_blocks_guard_edit(repo: Path, tmp_path: Path) -> None:
    protected = pinned_config(tmp_path, self_protect=True)
    assert guard(repo, "Edit", {"file_path": ".claude/hooks/guard.py"}, protected) == BLOCK


def test_t06_read_private_key_material(repo: Path) -> None:
    assert guard(repo, "Read", {"file_path": "secrets/backup/gpg/key.asc"}) == BLOCK


def test_t07_read_env_example_is_allowed(repo: Path) -> None:
    assert guard(repo, "Read", {"file_path": "stacks/monitoring/compose/.env.example"}) == PASS


def test_t08_git_status(repo: Path) -> None:
    assert bash(repo, "git status") == PASS


def test_t09_git_commit(repo: Path) -> None:
    assert bash(repo, "git commit -m x") == BLOCK


def test_t10_git_commit_inside_bash_c(repo: Path) -> None:
    assert bash(repo, 'bash -c "git commit -m x"') == BLOCK


def test_t11_ssh_inside_sh_c(repo: Path) -> None:
    assert bash(repo, "sh -c 'echo ok && ssh rpi-hub true'") == BLOCK


def test_t12_ssh_inside_command_substitution(repo: Path) -> None:
    assert bash(repo, "echo $(ssh 192.168.178.29 id)") == BLOCK


def test_t13_curl_to_pi_inside_backticks(repo: Path) -> None:
    assert bash(repo, "echo `curl http://rpi-hub.fritz.box:3000`") == BLOCK


def test_t14_scp_behind_env_and_timeout_wrappers(repo: Path) -> None:
    assert bash(repo, "env FOO=1 timeout 5 /usr/bin/scp a rpi-hub:/tmp") == BLOCK


def test_t15_find_exec_rm(repo: Path) -> None:
    assert bash(repo, r"find . -name x -exec rm {} \;") == BLOCK


def test_t16_redirection_into_readme(repo: Path) -> None:
    assert bash(repo, "echo x > README.md") == BLOCK


def test_t17_redirection_into_claude_scratch(repo: Path) -> None:
    assert bash(repo, "echo x > .claude/scratch/y.txt") == PASS


def test_t18_make_targets(repo: Path) -> None:
    assert bash(repo, "make precommit") == BLOCK
    assert bash(repo, "make doctor") == PASS


def test_t19_ruff_fix_versus_no_fix(repo: Path) -> None:
    assert bash(repo, "ruff check --fix .") == BLOCK
    assert bash(repo, "ruff check --no-fix .") == PASS


def test_t20_cat_env_file(repo: Path) -> None:
    assert bash(repo, "cat stacks/monitoring/compose/.env") == BLOCK


def test_t21_heredoc_script(repo: Path) -> None:
    assert bash(repo, "bash <<'EOF'\necho hi\nEOF\n") == BLOCK


def test_t22_inline_python_code(repo: Path) -> None:
    assert bash(repo, "python3 -c \"open('x','w')\"") == BLOCK


def test_t23_unbalanced_quotes_fail_closed(repo: Path) -> None:
    assert bash(repo, 'echo "unterminated') == BLOCK


def test_t24_invalid_stdin_json_fails_closed(repo: Path) -> None:
    assert _run(repo, "{not json") == BLOCK


def test_t25_webfetch_to_pi(repo: Path) -> None:
    assert guard(repo, "WebFetch", {"url": "http://rpi-hub:3000"}) == BLOCK


def test_t26_nesting_depth_six(repo: Path) -> None:
    command = "echo hi"
    for _ in range(6):
        command = f"echo $({command})"
    assert bash(repo, command) == BLOCK


def test_t27_pytest_from_venv(repo: Path) -> None:
    assert bash(repo, ".venv/bin/python -m pytest -q tests/precommit -m precommit") == PASS


def test_t28_docker_compose_config(repo: Path) -> None:
    command = "docker compose -f stacks/monitoring/compose/docker-compose.yml config"
    assert bash(repo, command) == PASS


def test_t29_substitution_nested_in_quotes(repo: Path) -> None:
    assert bash(repo, 'echo "$(echo \\"$(git push)\\")"') == BLOCK


def test_t30_substitution_inside_single_quotes_is_literal(repo: Path) -> None:
    assert bash(repo, "echo 'literal $(git push) in single quotes'") == PASS


def test_t31_unbalanced_substitution_fails_closed(repo: Path) -> None:
    assert bash(repo, "echo $(git status") == BLOCK


def test_t32_unclassified_read_command_passes(repo: Path) -> None:
    assert bash(repo, "ls -la stacks/") == PASS


def test_t33_host_script_via_bash(repo: Path) -> None:
    assert bash(repo, "bash scripts/network/cleanup-ufw.sh --verbose") == BLOCK


def test_t34_host_script_with_env_prefix(repo: Path) -> None:
    assert bash(repo, "DRY_RUN=1 ./scripts/network/bootstrap-networks.sh") == BLOCK


def test_t35_reading_a_host_script_is_allowed(repo: Path) -> None:
    assert guard(repo, "Read", {"file_path": "scripts/network/cleanup-ufw.sh"}) == PASS
