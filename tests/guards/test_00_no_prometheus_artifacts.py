from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Hard-ban: Prometheus runtime/config artifacts must not exist in repo anymore.
BANNED_PATH_PATTERNS = [
    r"(^|/)(prometheus)(/|$)",  # folders named prometheus
    r"(^|/).*prometheus.*\.ya?ml$",  # prometheus*.yml / *prometheus*.yaml
    r"(^|/)prometheus\.ya?ml$",  # direct config file
    r"(^|/)rules(_|-)prometheus.*",  # rules_prometheus*
]

# Hard-ban: Prometheus runtime references in infra configs.
BANNED_TEXT_PATTERNS = [
    r"(?mi)^\s*prometheus\s*:\s*$",  # compose service named prometheus
    r"(?mi)\bprometheus/prometheus\b",  # prometheus image
    r"(?mi)\bprometheus:9090\b",  # service endpoint
    r"(?mi)\bhttps?://prometheus(:9090)?\b",  # URL endpoint
]

# Keep this narrow: infra configs only (avoid docs false positives).
TEXT_SCAN_FILES = [
    "stacks/monitoring/compose/docker-compose.yml",
    "stacks/monitoring/grafana/provisioning/datasources/victoriametrics.yml",
]

IGNORE_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules"}


def _repo_files() -> list[Path]:
    files: list[Path] = []
    for p in REPO_ROOT.rglob("*"):
        if any(part in IGNORE_DIRS for part in p.parts):
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


def test_no_prometheus_runtime_references_in_infra_configs():
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

    assert not hits, "Prometheus runtime references found:\n" + "\n".join(hits)
