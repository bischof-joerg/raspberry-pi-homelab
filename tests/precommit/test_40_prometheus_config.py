from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests._helpers import REPO_ROOT, run, which_ok


def find_prometheus_config() -> Path:
    candidates = [
        REPO_ROOT / "stacks" / "monitoring" / "prometheus" / "prometheus.yml",
        REPO_ROOT / "monitoring" / "prometheus" / "prometheus.yml",
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


def _env_truthy(name: str) -> bool:
    v = (os.environ.get(name, "") or "").strip().lower()
    return v in {"1", "true", "yes", "on"}


@pytest.mark.precommit
def test_prometheus_config_is_valid_if_present():
    """
    Migration behavior:
    - If Prometheus config file does not exist: skip (Prometheus removed).
    - If it exists: validate with promtool (guardrail while Prometheus is still in repo).
    - If PROMETHEUS_REMOVAL_ENFORCE=1 and config exists: fail (ensures cleanup is complete).
    """
    prom_config = find_prometheus_config()

    if not prom_config.exists():
        pytest.skip(f"Prometheus config not present ({prom_config}); Prometheus likely removed")

    if _env_truthy("PROMETHEUS_REMOVAL_ENFORCE"):
        pytest.fail(f"Prometheus config still present but PROMETHEUS_REMOVAL_ENFORCE=1: {prom_config}")

    if not which_ok("promtool"):
        pytest.skip("promtool not installed")

    res = run(["promtool", "check", "config", str(prom_config)])
    assert res.returncode == 0, f"promtool failed:\n{res.stdout}\n{res.stderr}"
