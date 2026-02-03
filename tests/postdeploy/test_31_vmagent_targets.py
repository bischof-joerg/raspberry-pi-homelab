# tests/postdeploy/test_31_vmagent_targets.py
import pytest

from tests._helpers import run, which_ok

MONITORING_NETWORK = "monitoring"
VMAGENT_URL = "http://vmagent:8429/targets"


@pytest.mark.postdeploy
def test_vmagent_targets_ui_reachable(retry):
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

    def _check():
        nonlocal last
        last = run(cmd)
        ok = last.returncode == 0 and (last.stdout or "").strip()
        assert ok, (
            "vmagent /targets not reachable from within monitoring network.\n"
            f"url={VMAGENT_URL}\n"
            f"last rc={last.returncode}\nstdout:\n{last.stdout}\nstderr:\n{last.stderr}"
        )

    retry(_check, timeout_s=20, interval_s=0.5)
