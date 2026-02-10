from __future__ import annotations

import os
import subprocess
from urllib.parse import urlparse

import pytest

pytestmark = pytest.mark.postdeploy


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


def _host_resolves(host: str) -> bool:
    # Uses system NSS (DNS, /etc/hosts, etc.). Matches your getent debugging.
    r = _run(["getent", "hosts", host])
    return r.returncode == 0


def test_victorialogs_vmui_reachable_via_lan_url() -> None:
    """
    Verify the VictoriaLogs UI (VMUI) is reachable via a LAN URL from the target host.

    Set VLOGS_UI_URL in /etc/raspberry-pi-homelab/monitoring.env, e.g.:
      VLOGS_UI_URL=http://rpi-hub.fritz.box:9428/
    or:
      VLOGS_UI_URL=http://rpi-hub.fritz.box:9428/select/vmui/

    Notes:
      - This test validates routing/firewall/service reachability.
      - If the hostname is not resolvable on the target, the test fails with guidance.
    """
    url = os.environ.get("VLOGS_UI_URL")
    if not url:
        pytest.skip(
            "Set VLOGS_UI_URL (e.g. http://rpi-hub.fritz.box:9428/ or /select/vmui/) to enable this test."
        )

    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        pytest.fail(f"VLOGS_UI_URL is invalid (no hostname): {url!r}")

    if not _host_resolves(host):
        pytest.fail(
            f"Hostname for VLOGS_UI_URL is not resolvable via NSS/getent: host={host!r} url={url!r}\n"
            "Fix: set VLOGS_UI_URL to a resolvable name on the target (e.g. rpi-hub.fritz.box), "
            "or configure DNS/hosts accordingly."
        )

    # Follow redirects: some setups may redirect / -> /select/vmui/
    r = _run(["curl", "-fsSL", "--max-time", "5", url])
    assert r.returncode == 0, f"curl failed rc={r.returncode}\nstdout={r.stdout}\nstderr={r.stderr}"

    # very light content check; avoid brittle HTML matching
    assert len(r.stdout) > 200, (
        "VMUI response unexpectedly small; check routing/firewall/port publish"
    )
