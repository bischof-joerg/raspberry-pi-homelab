import subprocess
import time

import pytest


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


@pytest.mark.postdeploy
def test_cadvisor_metrics_endpoint_responds():
    # No host port is published in your stack; validate from inside the prometheus container network.
    # Adjust container name if yours differs.
    # This assumes prometheus has curl or wget; if not, use an alpine/curl helper container (see below).
    for _ in range(20):
        p = _run(["docker", "exec", "prometheus", "wget", "-qO-", "http://cadvisor:8080/metrics"])
        if p.returncode == 0 and "cadvisor_version_info" in (p.stdout or ""):
            return
        time.sleep(0.5)

    raise AssertionError(
        "cadvisor /metrics not responding from within prometheus container.\n"
        f"last rc={p.returncode}\nstdout:\n{p.stdout}\nstderr:\n{p.stderr}"
    )
