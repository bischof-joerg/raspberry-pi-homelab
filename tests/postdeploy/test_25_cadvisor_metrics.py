from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from tests._helpers import (
    compose_container_name,
    compose_ps_json,
    compose_services_by_name,
    find_monitoring_compose_file,
)

COMPOSE_FILE: Path = find_monitoring_compose_file()


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


@pytest.mark.postdeploy
def test_cadvisor_metrics_endpoint_responds():
    # No host port is published in your stack; validate from inside the prometheus container network.
    ps_rows = compose_ps_json(compose_file=COMPOSE_FILE)
    rows = compose_services_by_name(ps_rows)

    prom_name = compose_container_name(rows, "prometheus")
    assert prom_name, f"prometheus container name not found via compose ps. Rows: {sorted(rows.keys())}"

    for _ in range(20):
        p = _run(["docker", "exec", prom_name, "wget", "-qO-", "http://cadvisor:8080/metrics"])
        if p.returncode == 0 and "cadvisor_version_info" in (p.stdout or ""):
            return
        time.sleep(0.5)

    raise AssertionError(
        "cadvisor /metrics not responding from within prometheus container.\n"
        f"prometheus_container={prom_name}\n"
        f"last rc={p.returncode}\nstdout:\n{p.stdout}\nstderr:\n{p.stderr}"
    )
