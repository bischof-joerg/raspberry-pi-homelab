from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass

import pytest


def _run(cmd: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        check=check,
    )


def _require_postdeploy_on_target() -> None:
    if os.environ.get("POSTDEPLOY_ON_TARGET") != "1":
        pytest.skip(
            "POSTDEPLOY_ON_TARGET!=1 (set POSTDEPLOY_ON_TARGET=1 on the Pi to run postdeploy tests)"
        )


@dataclass(frozen=True)
class DockerNet:
    name: str
    bridge: str
    subnet: str
    gateway: str


def _get_docker_network(name: str) -> DockerNet:
    res = _run(["docker", "network", "inspect", name])
    if res.returncode != 0:
        raise AssertionError(
            f"docker network inspect failed: {name}\nstdout:\n{res.stdout}\n\nstderr:\n{res.stderr}"
        )

    try:
        data = json.loads(res.stdout)
        assert isinstance(data, list) and data, "unexpected docker network inspect JSON"
        net = data[0]
    except Exception as e:
        raise AssertionError(
            f"failed to parse docker network inspect JSON: {e}\nraw:\n{res.stdout}"
        ) from e

    bridge = (net.get("Options") or {}).get("com.docker.network.bridge.name") or ""
    ipam_cfg = (net.get("IPAM") or {}).get("Config") or []
    subnet = ""
    gateway = ""
    if ipam_cfg and isinstance(ipam_cfg, list) and isinstance(ipam_cfg[0], dict):
        subnet = str(ipam_cfg[0].get("Subnet") or "")
        gateway = str(ipam_cfg[0].get("Gateway") or "")

    # Note: for some networks, Docker might omit bridge option. We treat this as required only for monitoring.
    return DockerNet(name=name, bridge=bridge, subnet=subnet, gateway=gateway)


def _iface_exists(iface: str) -> bool:
    return _run(["ip", "link", "show", iface]).returncode == 0


def _ufw_is_active() -> bool:
    res = _run(["ufw", "status"])
    if res.returncode != 0:
        raise AssertionError(f"ufw status failed:\nstdout:\n{res.stdout}\n\nstderr:\n{res.stderr}")
    return "Status: active" in res.stdout


def _ufw_status_numbered() -> str:
    res = _run(["ufw", "status", "numbered"])
    if res.returncode != 0:
        raise AssertionError(
            f"ufw status numbered failed:\nstdout:\n{res.stdout}\n\nstderr:\n{res.stderr}"
        )
    return res.stdout


def _has_allow_rule_for_metrics(
    ufw_numbered: str, *, iface: str, subnet: str, port: int = 9323
) -> tuple[bool, str | None]:
    """
    Match typical ufw output lines like:
      [ 1] 9323/tcp on br-monitoring             ALLOW IN    172.20.0.0/16
    """
    lines = [ln.rstrip() for ln in ufw_numbered.splitlines() if ln.strip().startswith("[")]
    want = re.compile(
        rf"^\[\s*\d+\]\s+{port}/tcp\s+on\s+{re.escape(iface)}\s+ALLOW\s+IN\s+{re.escape(subnet)}\b",
        re.IGNORECASE,
    )
    for ln in lines:
        if want.search(ln):
            return True, ln
    return False, None


def _docker_run_in_network(network: str, cmd: str) -> subprocess.CompletedProcess[str]:
    """
    Run an ephemeral alpine container attached to a given Docker network.
    """
    return _run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            network,
            "alpine:3.20",
            "sh",
            "-lc",
            cmd,
        ]
    )


@pytest.mark.postdeploy
def test_networks_exist_monitoring_strict_apps_loose():
    """
    Contract:
    - monitoring: must have a stable bridge interface (used for UFW interface-bound rules) and IPAM config.
    - apps: must exist (external network), but we do NOT require a fixed bridge interface name.
    """
    _require_postdeploy_on_target()

    monitoring = _get_docker_network("monitoring")
    apps = _get_docker_network("apps")

    # monitoring: strict requirements
    assert monitoring.subnet, "monitoring network has no IPAM subnet"
    assert monitoring.gateway, "monitoring network has no IPAM gateway"
    assert monitoring.bridge, (
        "monitoring network has no bridge name in Options[com.docker.network.bridge.name]. "
        "If you rely on UFW interface rules, the bridge name must be stable."
    )
    assert _iface_exists(monitoring.bridge), (
        f"monitoring bridge interface missing: {monitoring.bridge}"
    )

    # apps: existence + basic sanity only (no fixed bridge contract)
    assert apps.subnet, "apps network has no IPAM subnet"
    assert apps.gateway, "apps network has no IPAM gateway"
    # If Docker provides a bridge name, ensure the interface exists; but do not require it.
    if apps.bridge:
        assert _iface_exists(apps.bridge), (
            f"apps bridge interface reported but missing: {apps.bridge}"
        )


@pytest.mark.postdeploy
def test_ufw_active_and_metrics_rule_present():
    _require_postdeploy_on_target()

    monitoring = _get_docker_network("monitoring")

    if not _ufw_is_active():
        pytest.fail(
            "UFW is inactive. Enable UFW or adjust postdeploy policy if intentionally disabled."
        )

    assert monitoring.bridge, "monitoring bridge missing; cannot validate interface-bound UFW rule"
    assert monitoring.subnet, "monitoring subnet missing; cannot validate subnet-scoped UFW rule"

    numbered = _ufw_status_numbered()
    ok, _matched = _has_allow_rule_for_metrics(
        numbered, iface=monitoring.bridge, subnet=monitoring.subnet, port=9323
    )
    assert ok, (
        "Missing required UFW rule for Docker Engine metrics (9323/tcp) scoped to monitoring network.\n"
        f"Expected: '9323/tcp on {monitoring.bridge} ALLOW IN {monitoring.subnet}'\n\n"
        f"ufw status numbered:\n{numbered}"
    )


@pytest.mark.postdeploy
def test_docker_engine_metrics_reachable_from_monitoring_gateway():
    """
    Positive smoke test: metrics endpoint should be reachable on the monitoring network gateway.
    """
    _require_postdeploy_on_target()

    monitoring = _get_docker_network("monitoring")
    assert monitoring.gateway, "monitoring gateway missing; cannot build metrics URL"
    url = f"http://{monitoring.gateway}:9323/metrics"

    res = _run(["curl", "-fsS", url])
    assert res.returncode == 0, (
        f"Docker Engine metrics endpoint not reachable at {url}.\n"
        f"stdout:\n{res.stdout}\n\nstderr:\n{res.stderr}"
    )
    assert "HELP" in res.stdout or "TYPE" in res.stdout, (
        "metrics output did not look like Prometheus exposition format"
    )


@pytest.mark.postdeploy
def test_negative_apps_cannot_reach_docker_engine_metrics_on_monitoring_gateway():
    """
    Negative test:
    From the `apps` network, reaching Docker Engine metrics on the monitoring gateway should be blocked by UFW,
    because the allow rule is interface-bound (monitoring bridge) and subnet-scoped (monitoring subnet).

    Guardrail:
    If there is no route from `apps` to the monitoring gateway at all, we skip to avoid false positives
    (failure could be due to routing, not firewall).
    """
    _require_postdeploy_on_target()

    if not _ufw_is_active():
        pytest.skip("UFW inactive; negative firewall test not applicable")

    monitoring = _get_docker_network("monitoring")
    assert monitoring.gateway, "monitoring gateway missing; cannot run negative test"

    # First, verify that the apps container has a route to the monitoring gateway IP.
    route_check = _docker_run_in_network(
        "apps",
        f"ip route get {monitoring.gateway} >/dev/null 2>&1",
    )
    if route_check.returncode != 0:
        pytest.skip(
            "No route from apps network to monitoring gateway; cannot assert UFW-based blocking.\n"
            f"stderr:\n{route_check.stderr}"
        )

    # Now attempt to fetch metrics from apps network. This should fail if UFW scoping is correct.
    fetch = _docker_run_in_network(
        "apps",
        f"wget -qO- -T 2 http://{monitoring.gateway}:9323/metrics >/dev/null 2>&1",
    )

    assert fetch.returncode != 0, (
        "Unexpectedly reached Docker Engine metrics from apps network.\n"
        "This suggests the firewall is too permissive or traffic is not constrained to monitoring interface/subnet.\n"
        f"monitoring_gateway={monitoring.gateway}\n"
        f"stdout:\n{fetch.stdout}\n\nstderr:\n{fetch.stderr}"
    )
