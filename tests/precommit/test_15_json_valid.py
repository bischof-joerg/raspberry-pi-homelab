from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests._helpers import REPO_ROOT

# In the repo, the important JSONs are here:
# monitoring/grafana/dashboards/**.json
# Optionally we check all *.json files in the repo (except .git).
EXCLUDE_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache"}


def iter_json_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for p in root.rglob("*.json"):
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        files.append(p)
    return sorted(files)


@pytest.mark.precommit
def test_all_json_files_are_valid():
    json_files = iter_json_files(REPO_ROOT)
    assert json_files, "No .json files found to validate"

    errors: list[str] = []
    for f in json_files:
        try:
            # UTF-8 is normal for Grafana JSON
            data = f.read_text(encoding="utf-8")
            json.loads(data)
        except Exception as e:
            rel = f.relative_to(REPO_ROOT)
            errors.append(f"{rel}: {type(e).__name__}: {e}")

    assert not errors, "❌ Invalid JSON files:\n" + "\n".join(f" - {e}" for e in errors)
