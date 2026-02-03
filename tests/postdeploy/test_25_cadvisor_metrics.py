# tests/postdeploy/test_25_cadvisor_metrics.py
import pytest

from tests._helpers import run, which_ok

MONITORING_NETWORK = "monitoring"


@pytest.mark.postdeploy
def test_cadvisor_metrics_endpoint_responds(retry):
    if not which_ok("docker"):
        pytest.skip("docker not available")

    cmd = [
        "docker",
        "run",
        "--rm",
        "--network",
        MONITORING_NETWORK,
        "alpine:3.20",
        "sh",
        "-lc",
        "apk add --no-cache curl >/dev/null && curl -fsS --max-time 3 http://cadvisor:8080/metrics | grep -qF cadvisor_version_info",
    ]

    last = None

    def _check():
        nonlocal last
        last = run(cmd)
        assert last.returncode == 0, (
            "cadvisor /metrics not responding from within monitoring network.\n"
            f"last rc={last.returncode}\nstdout:\n{last.stdout}\nstderr:\n{last.stderr}"
        )

    retry(_check, timeout_s=20, interval_s=0.5)
