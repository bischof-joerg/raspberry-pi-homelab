# tests/guards/test_44_run_hooks.py
#
# Finding F59: `pre-commit run --all-files` selects files from `git ls-files`, so `make ci` never
# ran the hooks on a new, untracked file; they met it first at commit time (test_43, test_54).
# scripts/dev/run-hooks.sh adds a second run over untracked, not-ignored files.
#
# pre-commit 3.8.0 (read in .venv, 2026-09-29): `--files` takes the names as given and checks only
# that they exist (commands/run.py:264-265, 75); an empty `--files` falls back to the staged files
# and stashes unstaged changes (run.py:343), so the second run must not start without files.
#
# The script runs here in a git repository in tmp_path against a stub pre-commit that records its
# arguments, so neither the real hooks nor the repository are touched.

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_HOOKS = REPO_ROOT / "scripts/dev/run-hooks.sh"
MAKEFILE = REPO_ROOT / "Makefile"

# One line per call, arguments separated by "|" so a space inside a file name stays visible.
STUB_PRE_COMMIT = """#!/bin/sh
for arg in "$@"; do printf '%s|' "$arg"; done >> "$STUB_LOG"
echo >> "$STUB_LOG"
case "$*" in
  *--all-files*) exit "${STUB_EXIT_ALL:-0}" ;;
  *) exit "${STUB_EXIT_FILES:-0}" ;;
esac
"""

pytestmark = pytest.mark.xfail(strict=True, reason="R1.14: scripts/dev/run-hooks.sh missing (F59)")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    (repo / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    _git(repo, "add", ".gitignore", "tracked.txt")
    (repo / "ignored.txt").write_text("ignored\n", encoding="utf-8")
    stub = tmp_path / "bin/pre-commit"
    stub.parent.mkdir()
    stub.write_text(STUB_PRE_COMMIT, encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    return repo


def _run(repo: Path, **extra: str) -> tuple[subprocess.CompletedProcess[str], list[list[str]]]:
    log = repo.parent / "calls.log"
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(repo.parent),
        "PRE_COMMIT": str(repo.parent / "bin/pre-commit"),
        "STUB_LOG": str(log),
        **extra,
    }
    proc = subprocess.run(
        ["bash", str(RUN_HOOKS)], cwd=repo, env=env, text=True, capture_output=True, check=False
    )
    calls = (
        [line.rstrip("|").split("|") for line in log.read_text().splitlines()]
        if log.exists()
        else []
    )
    return proc, calls


def test_tracked_files_only_run_once(repo: Path) -> None:
    proc, calls = _run(repo)
    assert proc.returncode == 0, f"❌ run-hooks.sh failed:\n{proc.stderr}"
    assert calls == [["run", "--all-files", "--show-diff-on-failure"]], (
        f"❌ Without untracked files there must be exactly one --all-files run, got {calls}.\n"
        "Fix: skip the second run when the untracked list is empty (an empty --files falls back "
        "to staged files and stashes)."
    )


def test_untracked_files_get_a_second_run_without_ignored_ones(repo: Path) -> None:
    (repo / "new file.py").write_text("x = 1\n", encoding="utf-8")
    proc, calls = _run(repo)
    assert proc.returncode == 0, f"❌ run-hooks.sh failed:\n{proc.stderr}"
    assert len(calls) == 2 and calls[0][:2] == ["run", "--all-files"], (
        f"❌ Expected an --all-files run, then a --files run; got {calls} (F59)."
    )
    second = calls[1]
    files = second[second.index("--files") + 1 :] if "--files" in second else []
    assert files == ["new file.py"], (
        f"❌ The second run got files {files}, expected ['new file.py'] — untracked only, "
        "ignored.txt excluded, the space kept (git ls-files -z | xargs -0).\n"
        f"Call: {second}"
    )


def test_a_failing_second_run_fails_the_script(repo: Path) -> None:
    (repo / "new.md").write_text("trailing \n", encoding="utf-8")
    proc, calls = _run(repo, STUB_EXIT_FILES="1")
    # Guards the guard: the failure must come from the --files run, not from a missing script.
    assert len(calls) == 2 and "--files" in calls[1], f"❌ No --files run happened: {calls}"
    assert proc.returncode != 0, (
        f"❌ run-hooks.sh exited 0 although the hooks failed on an untracked file; calls: {calls}."
        "\nFix: propagate the exit code of the --files run (set -o pipefail)."
    )


def test_a_failing_first_run_fails_the_script(repo: Path) -> None:
    proc, calls = _run(repo, STUB_EXIT_ALL="1")
    assert calls[:1] == [["run", "--all-files", "--show-diff-on-failure"]], (
        f"❌ No --all-files run happened: {calls}"
    )
    assert proc.returncode != 0, "❌ run-hooks.sh exited 0 although the --all-files run failed."


def test_make_hooks_uses_the_script() -> None:
    recipe = MAKEFILE.read_text(encoding="utf-8").split("\nhooks:", 1)[1].split("\n\n", 1)[0]
    assert "scripts/dev/run-hooks.sh" in recipe, (
        "❌ The Makefile target `hooks` does not call scripts/dev/run-hooks.sh (F59).\n"
        f"Recipe:\n{recipe}"
    )
