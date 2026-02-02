import time

import pytest

from tests._helpers import run, which_ok

MONITORING_NETWORK = "monitoring"
VMAGENT_URL = "http://vmagent:8429/targets"


@pytest.mark.postdeploy
def test_vmagent_targets_ui_reachable():
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
        f"apk add --no-cache curl >/dev/null && curl -fsS --max-time 3 {VMAGENT_URL} | head -c 200",
    ]

    last = None
    for _ in range(20):
        last = run(cmd)
        if last.returncode == 0 and (last.stdout or "").strip():
            return
        time.sleep(0.5)

    raise AssertionError(
        "vmagent /targets not reachable from within monitoring network.\n"
        f"url={VMAGENT_URL}\n"
        f"last rc={last.returncode}\nstdout:\n{last.stdout}\nstderr:\n{last.stderr}"
    )
