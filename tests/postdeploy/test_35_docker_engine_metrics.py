# tests/postdeploy/test_35_docker_engine_metrics.py
import json
import os
import time
import urllib.parse
import urllib.request

import pytest

from tests._helpers import run, which_ok

PROMETHEUS_BASE = "http://127.0.0.1:9090"
DOCKER_ENGINE_PORT = 9323
MONITORING_NETWORK = "monitoring"
EXPECTED_BRIDGE_NAME = "br-monitoring"
EXPECTED_SUBNET = "172.20.0.0/16"
EXPECTED_GATEWAY = "172.20.0.1"

# Keep this consistent with your docker daemon metrics endpoint.
# Metric name that should exist if dockerd metrics are enabled (dockerd exposes it).
REQUIRED_SAMPLE_METRIC = "engine_daemon_engine_info"

def _get_ipam_configs(net: dict) -> list[dict]:
    ipam = net.get("IPAM") or {}
    cfg = ipam.get("Config")
    return cfg if isinstance(cfg, list) else []

def _assert_monitoring_ipam_is_stable(net: dict) -> tuple[str, str]:
    """
    Ensures the monitoring network uses the expected IPAM subnet+gateway.
    Returns (subnet, gateway).
    """
    cfgs = _get_ipam_configs(net)
    assert cfgs, f"No IPAM.Config found for network {MONITORING_NETWORK}: {net.get('IPAM')}"

    # We expect exactly one IPv4 config for this setup.
    cfg = cfgs[0]
    subnet = cfg.get("Subnet")
    gateway = cfg.get("Gateway")

    assert subnet == EXPECTED_SUBNET, (
        f"monitoring network Subnet must be {EXPECTED_SUBNET} but is {subnet!r}. "
        f"IPAM.Config={cfgs}"
    )
    assert gateway == EXPECTED_GATEWAY, (
        f"monitoring network Gateway must be {EXPECTED_GATEWAY} but is {gateway!r}. "
        f"IPAM.Config={cfgs}"
    )

    return subnet, gateway

def _http_get_json(url: str, timeout_s: int = 5) -> dict:
    with urllib.request.urlopen(url, timeout=timeout_s) as r:
        return json.loads(r.read().decode())


def _prom_query(expr: str, timeout_s: int = 5) -> dict:
    qs = urllib.parse.urlencode({"query": expr})
    return _http_get_json(f"{PROMETHEUS_BASE}/api/v1/query?{qs}", timeout_s=timeout_s)


def _docker_network_inspect(name: str) -> dict:
    if not which_ok("docker"):
        pytest.skip("docker not available")

    res = run(["docker", "network", "inspect", name])
    if res.returncode != 0:
        pytest.fail(f"docker network inspect failed for {name}:\n{res.stdout}\n{res.stderr}")

    try:
        arr = json.loads(res.stdout)
        assert isinstance(arr, list) and arr, "unexpected network inspect output"
        return arr[0]
    except Exception as e:
        pytest.fail(f"Failed to parse docker network inspect JSON: {e}\nRaw:\n{res.stdout}")


def _get_monitoring_gateway_ip(net: dict) -> str:
    ipam = (net.get("IPAM") or {}).get("Config") or []
    if not ipam:
        pytest.fail(f"No IPAM config found for network {net.get('Name')}")

    gw = ipam[0].get("Gateway")
    if not gw:
        pytest.fail(f"No Gateway in IPAM config for network {net.get('Name')}: {ipam}")
    return gw


def _get_bridge_name(net: dict) -> str | None:
    return (net.get("Options") or {}).get("com.docker.network.bridge.name")


def _assert_metrics_reachable_from_monitoring_net(gateway_ip: str) -> None:
    """
    Robust connectivity check from inside the monitoring network.
    Avoid grep -E regex pitfalls on BusyBox (Alpine).
    """
    cmd = [
        "docker",
        "run",
        "--rm",
        "--network",
        MONITORING_NETWORK,
        "alpine:3.20",
        "sh",
        "-lc",
        (
            "apk add --no-cache curl >/dev/null && "
            f"curl -fsS --max-time 3 http://{gateway_ip}:{DOCKER_ENGINE_PORT}/metrics "
            f"| grep -qF '{REQUIRED_SAMPLE_METRIC}'"
        ),
    ]
    res = run(cmd)
    assert res.returncode == 0, (
        "Docker engine metrics are NOT reachable from within the monitoring network.\n"
        f"Expected: http://{gateway_ip}:{DOCKER_ENGINE_PORT}/metrics to be reachable and contain {REQUIRED_SAMPLE_METRIC}.\n"
        f"stdout:\n{res.stdout}\n"
        f"stderr:\n{res.stderr}\n"
        "This typically indicates: UFW/FORWARD policy blocking, missing allow rule on br-monitoring, "
        "or dockerd metrics not enabled/listening."
    )


@pytest.mark.postdeploy
def test_docker_engine_metrics_network_and_scrape_is_stable():
    # 1) Verify the monitoring network exists and is bound to the fixed bridge name.
    net = _docker_network_inspect(MONITORING_NETWORK)
    assert net.get("Name") == MONITORING_NETWORK, net

    bridge = _get_bridge_name(net)
    assert bridge == EXPECTED_BRIDGE_NAME, (
        f"monitoring network must be bound to bridge {EXPECTED_BRIDGE_NAME} "
        f"but is {bridge!r}. Options: {net.get('Options')}"
    )

    # 1b) Verify IPAM is stable (Subnet + Gateway) — aligns with UFW allow rule scope.
    _subnet, gateway_ip = _assert_monitoring_ipam_is_stable(net)

    # 2) Verify the endpoint is reachable from within the monitoring network (real traffic path).
    _assert_metrics_reachable_from_monitoring_net(gateway_ip)

    # 3) Verify Prometheus has the docker-engine target and it is up (end-to-end scrape).
    j = _http_get_json(f"{PROMETHEUS_BASE}/api/v1/targets", timeout_s=4)
    assert j.get("status") == "success", f"targets endpoint failed: {j}"

    targets = j["data"]["activeTargets"]
    docker_targets = [t for t in targets if t.get("labels", {}).get("job") == "docker-engine"]
    assert docker_targets, "No activeTargets with job=docker-engine found (Prometheus scrape_config missing?)"

    for t in docker_targets:
        assert t.get("health") == "up", (
            f"docker-engine target not healthy: health={t.get('health')} err={t.get('lastError')} "
            f"scrapeUrl={t.get('scrapeUrl')}"
        )

        # Optional but very useful: ensure it scrapes exactly the gateway we expect.
        # This ties together IPAM stability + Prometheus config.
        su = t.get("scrapeUrl") or ""
        assert f"http://{gateway_ip}:{DOCKER_ENGINE_PORT}/metrics" in su, (
            f"docker-engine scrapeUrl unexpected. Expected gateway-based URL "
            f"http://{gateway_ip}:{DOCKER_ENGINE_PORT}/metrics but got {su!r}"
        )

    # 4) Verify Prometheus actually ingested a core docker-engine metric.
    #    Retry to avoid flakiness right after deploy/reload.
    deadline = time.time() + 25
    last = None
    while time.time() < deadline:
        last = _prom_query(REQUIRED_SAMPLE_METRIC, timeout_s=5)
        if last.get("status") == "success":
            result = last.get("data", {}).get("result", [])
            if result:
                return
        time.sleep(2)

    pytest.fail(
        f"Prometheus did not ingest {REQUIRED_SAMPLE_METRIC} within retry window.\n"
        f"Last query response: {last}\n"
        "Target may be up but scraping empty/filtered, or scrape interval too long, "
        "or dockerd metrics endpoint not exporting expected series."
    )
