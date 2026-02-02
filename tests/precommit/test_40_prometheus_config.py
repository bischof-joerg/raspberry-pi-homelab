from __future__ import annotations

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


@pytest.mark.precommit
def test_prometheus_config():
    prom_config = find_prometheus_config()
    if not prom_config.exists():
        pytest.fail(f"Missing: {prom_config}")

    if not which_ok("promtool"):
        pytest.skip("promtool not installed")

    res = run(["promtool", "check", "config", str(prom_config)])
    assert res.returncode == 0, f"promtool failed:\n{res.stdout}\n{res.stderr}"
