from __future__ import annotations

from pathlib import Path

import pytest

from tests._helpers import REPO_ROOT

PROMETHEUS_CONFIG_PATHS = [
    REPO_ROOT / "stacks" / "monitoring" / "prometheus" / "prometheus.yml",
    REPO_ROOT / "monitoring" / "prometheus" / "prometheus.yml",
]


@pytest.mark.precommit
def test_no_legacy_prometheus_config_present():
    """
    Prometheus has been removed from this repository.
    This pre-commit guard ensures legacy Prometheus config files do not reappear.
    """
    present: list[Path] = [p for p in PROMETHEUS_CONFIG_PATHS if p.exists()]
    if present:
        rel = [str(p.relative_to(REPO_ROOT)) for p in present]
        pytest.fail(
            "❌ Legacy Prometheus config file(s) detected (Prometheus is removed):\n"
            + "\n".join(f" - {r}" for r in rel)
            + "\n\nFix:\n"
            " - Remove the files from the repo (git rm)\n"
            " - Ensure no Prometheus stack/config is reintroduced\n"
        )
