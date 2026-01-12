import pytest
from pathlib import Path
from tests._helpers import run, which_ok, REPO_ROOT

PROM_CONFIG = REPO_ROOT / "monitoring/prometheus/prometheus.yml"

@pytest.mark.precommit
def test_prometheus_config():
    if not PROM_CONFIG.exists():
        pytest.fail(f"Missing: {PROM_CONFIG}")

    if not which_ok("promtool"):
        pytest.skip("promtool not installed")

    res = run(["promtool", "check", "config", str(PROM_CONFIG)])
    assert res.returncode == 0, f"promtool failed:\n{res.stdout}\n{res.stderr}"
