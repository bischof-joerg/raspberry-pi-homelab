import os
import subprocess

import pytest

pytestmark = pytest.mark.postdeploy


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


def test_victorialogs_vmui_reachable_via_lan_url() -> None:
    """
    Single test to verify the VictoriaLogs UI (VMUI) is reachable via LAN URL.

    Set VLOGS_UI_URL in /etc/raspberry-pi-homelab/monitoring.env, e.g.:
      VLOGS_UI_URL=http://rpi-hub.lan:9428/select/vmui/
    """
    url = os.environ.get("VLOGS_UI_URL")
    if not url:
        pytest.skip(
            "Set VLOGS_UI_URL (e.g. http://rpi-hub.lan:9428/select/vmui/) to enable this test."
        )

    r = _run(["curl", "-fsS", "--max-time", "5", url])
    assert r.returncode == 0, f"curl failed rc={r.returncode}\nstdout={r.stdout}\nstderr={r.stderr}"
    # very light content check; avoid brittle HTML matching
    assert len(r.stdout) > 200, (
        "VMUI response unexpectedly small; check routing/firewall/port publish"
    )
