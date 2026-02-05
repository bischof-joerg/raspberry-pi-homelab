from __future__ import annotations

from pathlib import Path

import pytest

from tests._helpers import REPO_ROOT, run

## This test is no longer need and covered by pre-commit hooks.
# Keeping it here for historical reasons.
# See: .pre-commit-config.yaml (jsonlint hook)
# For this reason changed marker from @pytest.mark.precommit to @pytest.mark.lint

MAX_KB = 1024  # same as pre-commit args: ["--maxkb=1024"]
MAX_BYTES = MAX_KB * 1024

EXCLUDE_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache"}


def relpath(p: Path) -> str:
    try:
        return str(p.relative_to(REPO_ROOT))
    except Exception:
        return str(p)


def list_staged_files() -> list[Path]:
    # staged files (added/modified) – is close to “added-large-files” behavior
    res = run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"])
    if res.returncode != 0:
        return []
    files = []
    for line in res.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        files.append(REPO_ROOT / line)
    return files


def list_tracked_files() -> list[Path]:
    res = run(["git", "ls-files"])
    if res.returncode != 0:
        return []
    files = []
    for line in res.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        files.append(REPO_ROOT / line)
    return files


@pytest.mark.lint
def test_no_large_files():
    staged = [p for p in list_staged_files() if p.exists()]
    candidates = staged if staged else [p for p in list_tracked_files() if p.exists()]

    if not candidates:
        pytest.skip("No git files found (are we in a git repo?)")

    too_big: list[str] = []
    for p in candidates:
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        size = p.stat().st_size
        if size > MAX_BYTES:
            too_big.append(f"{relpath(p)} ({size / 1024:.1f} KB)")

    assert not too_big, (
        f"❌ Files exceed max size of {MAX_KB} KB:\n"
        + "\n".join(f" - {x}" for x in too_big)
        + "\n\nFix options:\n"
        " - Put large artifacts into releases/object storage\n"
        " - Add to .gitignore (if generated)\n"
        " - Use Git LFS if really needed\n"
    )
