from __future__ import annotations

import os
import subprocess

import pytest


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


@pytest.mark.postdeploy
def test_prometheus_is_removed_when_flag_set() -> None:
    if os.environ.get("PROMETHEUS_REMOVED", "1") != "1":
        pytest.skip("PROMETHEUS_REMOVED=0 (legacy mode)")

    # Hard requirement: no running container/service named "prometheus"
    cp = _run(["docker", "ps", "--format", "{{.Names}}"])
    assert cp.returncode == 0, f"docker ps failed: {cp.stderr.strip()}"

    names = [line.strip() for line in cp.stdout.splitlines() if line.strip()]
    bad = [n for n in names if "prometheus" in n.lower()]

    assert not bad, "PROMETHEUS_REMOVED=1 but Prometheus container(s) still running:\n" + "\n".join(
        f"- {n}" for n in bad
    )
