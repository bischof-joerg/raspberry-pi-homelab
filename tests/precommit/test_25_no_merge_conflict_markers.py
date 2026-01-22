from __future__ import annotations

from pathlib import Path

import pytest
from tests._helpers import REPO_ROOT

## This test is no longer need and covered by pre-commit hooks.
# Keeping it here for historical reasons.
# See: .pre-commit-config.yaml (jsonlint hook)
# For this reason changed marker from @pytest.mark.precommit to @pytest.mark.lint

EXCLUDE_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache"}
EXCLUDE_FILES = {
    "tests/precommit/test_25_no_merge_conflict_markers.py",
}
MARKERS = ("<<<<<<<", "=======", ">>>>>>>")

# scan text files "best effort". Binary/strange encodings are skipped.
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB, so the test stays fast


def is_excluded(path: Path) -> bool:
    rel = path.relative_to(REPO_ROOT)
    if str(rel) in EXCLUDE_FILES:
        return True
    return any(part in EXCLUDE_DIRS for part in path.parts)


@pytest.mark.lint
def test_no_merge_conflict_markers_present():
    hits: list[str] = []

    for f in REPO_ROOT.rglob("*"):
        if not f.is_file():
            continue
        if is_excluded(f):
            continue
        if f.stat().st_size > MAX_FILE_SIZE_BYTES:
            continue

        try:
            text = f.read_text(encoding="utf-8", errors="strict")
        except Exception:
            # non-UTF8 / binary -> skip
            continue

        if any(m in text for m in MARKERS):
            rel = f.relative_to(REPO_ROOT)
            hits.append(str(rel))

    assert not hits, (
        "❌ Merge conflict markers found in files:\n"
        + "\n".join(f" - {h}" for h in hits)
        + "\n\nFix: resolve conflicts and remove the markers (<<<<<<< ======= >>>>>>>)."
    )
