# Hard-ban Prometheus (Compose + repo artifacts + docs/configs).

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Tune this list as you discover real leftovers in your repo.
BANNED_PATH_PATTERNS = [
    r"(^|/)(prometheus)(/|$)",  # folders named prometheus
    r"(^|/).*prometheus.*\.ya?ml$",  # prometheus*.yml
    r"(^|/)rules(_|-)prometheus.*",  # rules_prometheus*
]

# Compose-level "prometheus" should not exist anymore.
BANNED_TEXT_PATTERNS = [
    r"(?mi)^\s*prometheus\s*:\s*$",  # service named prometheus
    r"(?mi)\bprometheus/prometheus\b",  # image
    r"(?mi)\b--web\.listen-address\b",  # common prom flags
    r"(?mi)\bpromtool\b",
    r"(?mi)\b:9090\b",  # port reference (tune if you legitimately use 9090 elsewhere)
]

TEXT_SCAN_FILES = [
    "stacks/monitoring/compose/docker-compose.yml",
    "stacks/monitoring/README.md",
    "docs/monitoring.md",
]


def _repo_files() -> list[Path]:
    # skip big/irrelevant dirs; adjust for your repo
    ignore = {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules"}
    files: list[Path] = []
    for p in REPO_ROOT.rglob("*"):
        if any(part in ignore for part in p.parts):
            continue
        if p.is_file():
            files.append(p)
    return files


def test_no_prometheus_files_or_dirs_exist():
    bad: list[str] = []
    patterns = [re.compile(x) for x in BANNED_PATH_PATTERNS]

    for f in _repo_files():
        rel = f.relative_to(REPO_ROOT).as_posix()
        for pat in patterns:
            if pat.search(rel):
                bad.append(rel)
                break

    assert not bad, "Prometheus artifacts found:\n" + "\n".join(sorted(bad))


def test_no_prometheus_references_in_key_text_files():
    pats = [re.compile(x) for x in BANNED_TEXT_PATTERNS]
    hits: list[str] = []

    for rel in TEXT_SCAN_FILES:
        f = REPO_ROOT / rel
        if not f.exists():
            continue

        txt = f.read_text(encoding="utf-8", errors="replace")
        for pat in pats:
            if pat.search(txt):
                hits.append(f"{rel} matched {pat.pattern}")

    assert not hits, "Prometheus references found:\n" + "\n".join(hits)
