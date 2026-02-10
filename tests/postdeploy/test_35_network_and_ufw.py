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

    return DockerNet(name=name, bridge=bridge, subnet=subnet, gateway=gateway)


def _iface_exists(iface: str) -> bool:
    return _run(["ip", "link", "show", iface]).returncode == 0


def _ufw_is_active() -> bool:
    res = _run(["ufw", "status"])
    if res.returncode != 0:
        raise AssertionError(f"ufw status failed:\nstdout:\n{res.stdout}\n\nstderr:\n{res.stderr}")
    return "Status: active" in res.stdout


def _ufw_status_verbose() -> str:
    res = _run(["ufw", "status", "verbose"])
    if res.returncode != 0:
        raise AssertionError(
            f"ufw status verbose failed:\nstdout:\n{res.stdout}\n\nstderr:\n{res.stderr}"
        )
    return res.stdout


def _ufw_status_numbered() -> str:
    res = _run(["ufw", "status", "numbered"])
    if res.returncode != 0:
        raise AssertionError(
            f"ufw status numbered failed:\nstdout:\n{res.stdout}\n\nstderr:\n{res.stderr}"
        )
    return res.stdout


def _ufw_numbered_lines(numbered: str) -> list[str]:
    """Return only the rule lines (those starting with '[')."""
    return [ln.rstrip("\n") for ln in numbered.splitlines() if ln.strip().startswith("[")]


def _ufw_normalized_rule_text(ln: str) -> str:
    """
    Normalize a single numbered rule line so regex can anchor at the actual rule:
      - drop leading "[ N] "
      - drop trailing " # comment"
    """
    ln2 = re.sub(r"^\[\s*\d+\]\s+", "", ln)
    ln2 = re.sub(r"\s+#.*$", "", ln2)
    return ln2


def _ufw_normalized_numbered(numbered: str) -> list[str]:
    return [_ufw_normalized_rule_text(ln) for ln in _ufw_numbered_lines(numbered)]


def _has_allow_rule_for_metrics(
    ufw_numbered: str, *, iface: str, subnet: str, port: int = 9323
) -> tuple[bool, str | None]:
    """
    Match typical ufw output lines like:
      [ 1] 9323/tcp on br-monitoring  ALLOW IN  172.20.0.0/16  # comment
    We normalize and match the rule content.
    """
    want = re.compile(
        rf"^{port}/tcp\s+on\s+{re.escape(iface)}\s+ALLOW\s+IN\s+{re.escape(subnet)}(?:\s|$)",
        re.IGNORECASE,
    )
    for ln in _ufw_normalized_numbered(ufw_numbered):
        if want.search(ln):
            return True, ln
    return False, None


def _docker_run_in_network(network: str, cmd: str) -> subprocess.CompletedProcess[str]:
    """Run an ephemeral alpine container attached to a given Docker network."""
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
    if apps.bridge:
        assert _iface_exists(apps.bridge), (
            f"apps bridge interface reported but missing: {apps.bridge}"
        )


@pytest.mark.postdeploy
def test_ufw_active_and_metrics_rule_present():
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
    """Positive smoke test: metrics endpoint should be reachable on the monitoring network gateway."""
    monitoring = _get_docker_network("monitoring")
    assert monitoring.gateway, "monitoring gateway missing; cannot build metrics URL"
    url = f"http://{monitoring.gateway}:9323/metrics"

    res = _run(["curl", "-fsS", url])
    assert res.returncode == 0, (
        f"Docker Engine metrics endpoint not reachable at {url}.\n"
        f"stdout:\n{res.stdout}\n\nstderr:\n{res.stderr}"
    )
    assert ("HELP" in res.stdout) or ("TYPE" in res.stdout), (
        "metrics output did not look like Prometheus format"
    )


@pytest.mark.postdeploy
def test_negative_apps_cannot_reach_docker_engine_metrics_on_monitoring_gateway():
    """
    Negative test:
    From the `apps` network, reaching Docker Engine metrics on the monitoring gateway should be blocked by UFW,
    because the allow rule is interface-bound (monitoring bridge) and subnet-scoped (monitoring subnet).

    Guardrail:
    If there is no route from `apps` to the monitoring gateway at all, we skip to avoid false positives.
    """
    if not _ufw_is_active():
        pytest.skip("UFW inactive; negative firewall test not applicable")

    monitoring = _get_docker_network("monitoring")
    assert monitoring.gateway, "monitoring gateway missing; cannot run negative test"

    route_check = _docker_run_in_network(
        "apps", f"ip route get {monitoring.gateway} >/dev/null 2>&1"
    )
    if route_check.returncode != 0:
        pytest.skip(
            "No route from apps network to monitoring gateway; cannot assert UFW-based blocking.\n"
            f"stderr:\n{route_check.stderr}"
        )

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


@pytest.mark.postdeploy
def test_ufw_inbound_exposure_allowlisted_v4_and_closed_v6():
    """
    Exposure contract (enforced by scripts/cleanup-network-ufw.sh):

    Required inbound (IPv4):
      - SSH 22/tcp: ALLOW IN from ADMIN_IPV4 and LAN_CIDR
      - Grafana 3000/tcp: ALLOW IN from LAN_CIDR
      - VictoriaLogs UI 9428/tcp: ALLOW IN from LAN_CIDR

    Required deny (v4 + v6):
      - 3000/tcp DENY IN Anywhere
      - 3000/tcp (v6) DENY IN Anywhere (v6)
      - 9428/tcp DENY IN Anywhere
      - 9428/tcp (v6) DENY IN Anywhere (v6)

    Forbidden:
      - Any "ALLOW IN Anywhere" for managed ports (v4)
      - Any IPv6 global allows (e.g. 2000::/3, Anywhere (v6), fe80::/10) for managed ports
      - Any inbound exposure for Prometheus/Alertmanager (9090/9093)
      - Any inbound "Anywhere on docker0" allow rule (broad docker0 exposure)
    """
    lan_cidr = os.environ.get("LAN_CIDR")
    admin_ipv4 = os.environ.get("ADMIN_IPV4")
    if not lan_cidr or not admin_ipv4:
        pytest.skip(
            "Set LAN_CIDR and ADMIN_IPV4 (loaded from monitoring.env on the Pi) to enable this test."
        )

    grafana_port = os.environ.get("GRAFANA_PORT", "3000")
    vlogs_port = os.environ.get("VLOGS_UI_PORT", "9428")
    ssh_port = os.environ.get("SSH_PORT", "22")
    prom_port = os.environ.get("PROMETHEUS_PORT", "9090")
    am_port = os.environ.get("ALERTMANAGER_PORT", "9093")

    verbose = _ufw_status_verbose()
    assert "Status: active" in verbose, "UFW is not active"
    assert "Default: deny (incoming)" in verbose, "UFW incoming default policy is not deny"

    numbered_raw = _ufw_status_numbered()
    numbered_lines = _ufw_normalized_numbered(numbered_raw)
    numbered = "\n".join(numbered_lines)  # normalized, no "[ N]" prefixes, no trailing comments

    def must(pattern: str, msg: str) -> None:
        if not re.search(pattern, numbered, flags=re.MULTILINE):
            raise AssertionError(
                f"{msg}\nPattern: {pattern}\n--- ufw status numbered (normalized) ---\n{numbered}\n\n"
                f"--- ufw status numbered (raw) ---\n{numbered_raw}"
            )

    def must_not(pattern: str, msg: str) -> None:
        if re.search(pattern, numbered, flags=re.MULTILINE):
            raise AssertionError(
                f"{msg}\nPattern: {pattern}\n--- ufw status numbered (normalized) ---\n{numbered}\n\n"
                f"--- ufw status numbered (raw) ---\n{numbered_raw}"
            )

    def p_tcp(p: str) -> str:
        # UFW prints IPv6 rules sometimes as "3000/tcp (v6)" (note the extra token).
        return rf"{re.escape(p)}/tcp(?:\s+\(v6\))?"

    # ---- Required IPv4 allows ----
    must(
        rf"^{re.escape(grafana_port)}/tcp\s+ALLOW IN\s+{re.escape(lan_cidr)}(?:\s|$)",
        "Missing Grafana LAN allow (v4)",
    )
    must(
        rf"^{re.escape(vlogs_port)}/tcp\s+ALLOW IN\s+{re.escape(lan_cidr)}(?:\s|$)",
        "Missing VictoriaLogs UI LAN allow (v4)",
    )
    must(
        rf"^{re.escape(ssh_port)}/tcp\s+ALLOW IN\s+{re.escape(admin_ipv4)}(?:\s|$)",
        "Missing SSH admin allow (v4)",
    )
    must(
        rf"^{re.escape(ssh_port)}/tcp\s+ALLOW IN\s+{re.escape(lan_cidr)}(?:\s|$)",
        "Missing SSH LAN allow (v4)",
    )

    # ---- Required denies (v4 + v6) for Grafana and VictoriaLogs UI ----
    must(
        rf"^{re.escape(grafana_port)}/tcp\s+DENY IN\s+Anywhere(?:\s|$)",
        "Missing Grafana deny-anywhere (v4)",
    )
    must(
        rf"^{p_tcp(grafana_port)}\s+DENY IN\s+Anywhere\s+\(v6\)(?:\s|$)",
        "Missing Grafana deny-anywhere (v6)",
    )
    must(
        rf"^{re.escape(vlogs_port)}/tcp\s+DENY IN\s+Anywhere(?:\s|$)",
        "Missing VictoriaLogs deny-anywhere (v4)",
    )
    must(
        rf"^{p_tcp(vlogs_port)}\s+DENY IN\s+Anywhere\s+\(v6\)(?:\s|$)",
        "Missing VictoriaLogs deny-anywhere (v6)",
    )

    # ---- Must not be globally allowed (IPv4) ----
    for p in (grafana_port, vlogs_port, ssh_port):
        must_not(
            rf"^{re.escape(p)}/tcp\s+ALLOW IN\s+Anywhere(?:\s|$)",
            f"Port {p} is globally allowed (v4)",
        )

    # ---- Must not be globally allowed (IPv6) ----
    for p in (grafana_port, vlogs_port, ssh_port, prom_port, am_port):
        must_not(
            rf"^{p_tcp(p)}\s+ALLOW IN\s+2000::/3(?:\s|$)",
            f"Port {p} is globally allowed over IPv6 (2000::/3)",
        )
        must_not(
            rf"^{p_tcp(p)}\s+ALLOW IN\s+Anywhere\s+\(v6\)(?:\s|$)",
            f"Port {p} is globally allowed over IPv6 (Anywhere v6)",
        )
        must_not(
            rf"^{p_tcp(p)}\s+ALLOW IN\s+fe80::/10(?:\s|$)",
            f"Port {p} is allowed from IPv6 link-local (fe80::/10)",
        )

    # ---- Prometheus / Alertmanager must not be exposed inbound (any allow) ----
    must_not(
        rf"^{re.escape(prom_port)}/tcp\s+ALLOW IN\s+",
        "Prometheus port is still allowed inbound (should be removed)",
    )
    must_not(
        rf"^{re.escape(am_port)}/tcp\s+ALLOW IN\s+",
        "Alertmanager port is still allowed inbound (should be removed)",
    )

    # ---- docker0 broad allow must be absent ----
    must_not(
        r"^Anywhere on docker0\s+ALLOW IN\s+Anywhere(?:\s|$)",
        "Broad inbound allow on docker0 must not exist",
    )


@pytest.mark.postdeploy
def test_victorialogs_ui_reachable_via_configured_url():
    """
    Smoke test that the VictoriaLogs UI is reachable using the configured URL.

    Expected env var (from /etc/raspberry-pi-homelab/monitoring.env):
      VLOGS_UI_URL=http://rpi-hub.fritz.box:9428/select/vmui

    Notes:
    - This runs on the Pi. DNS must resolve (e.g. rpi-hub.fritz.box via local resolver).
    - We verify HTTP success and basic HTML content.
    """
    url = os.environ.get("VLOGS_UI_URL")
    if not url:
        pytest.skip("VLOGS_UI_URL not set (load monitoring.env on the target).")

    res = _run(["curl", "-fsS", "--max-time", "5", url])
    assert res.returncode == 0, (
        f"VictoriaLogs UI not reachable at {url}\nstdout:\n{res.stdout}\n\nstderr:\n{res.stderr}"
    )

    body = res.stdout or ""
    # Keep heuristics loose: UI pages might change slightly between versions.
    assert ("<html" in body.lower()) or ("vmui" in body.lower()) or ("victoria" in body.lower()), (
        "VictoriaLogs UI response did not look like HTML/UI content.\n"
        f"First 200 bytes:\n{body[:200]!r}"
    )
