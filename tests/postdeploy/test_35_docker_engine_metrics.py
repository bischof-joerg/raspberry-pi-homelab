# tests/postdeploy/test_35_docker_engine_metrics.py
from __future__ import annotations

import json
import urllib.parse

import pytest

from tests._helpers import run, which_ok

PROMETHEUS_BASE = "http://127.0.0.1:9090"
DOCKER_ENGINE_PORT = 9323
MONITORING_NETWORK = "monitoring"
EXPECTED_BRIDGE_NAME = "br-monitoring"
EXPECTED_SUBNET = "172.20.0.0/16"
EXPECTED_GATEWAY = "172.20.0.1"

REQUIRED_SAMPLE_METRIC = "engine_daemon_engine_info"


def _get_ipam_configs(net: dict) -> list[dict]:
    ipam = net.get("IPAM") or {}
    cfg = ipam.get("Config")
    return cfg if isinstance(cfg, list) else []


def _assert_monitoring_ipam_is_stable(net: dict) -> tuple[str, str]:
    cfgs = _get_ipam_configs(net)
    assert cfgs, f"No IPAM.Config found for network {MONITORING_NETWORK}: {net.get('IPAM')}"

    cfg = cfgs[0]
    subnet = cfg.get("Subnet")
    gateway = cfg.get("Gateway")

    assert subnet == EXPECTED_SUBNET, (
        f"monitoring network Subnet must be {EXPECTED_SUBNET} but is {subnet!r}. IPAM.Config={cfgs}"
    )
    assert gateway == EXPECTED_GATEWAY, (
        f"monitoring network Gateway must be {EXPECTED_GATEWAY} but is {gateway!r}. IPAM.Config={cfgs}"
    )

    return subnet, gateway


def _docker_network_inspect(name: str) -> dict:
    if not which_ok("docker"):
        pytest.skip("docker not available")

    res = run(["docker", "network", "inspect", name])
    if res.returncode != 0:
        pytest.fail(f"docker network inspect failed for {name}:\n{res.stdout}\n{res.stderr}")

    arr = json.loads(res.stdout)
    assert isinstance(arr, list) and arr, "unexpected network inspect output"
    return arr[0]


def _get_bridge_name(net: dict) -> str | None:
    return (net.get("Options") or {}).get("com.docker.network.bridge.name")


def _assert_metrics_reachable_from_monitoring_net(gateway_ip: str) -> None:
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


def _prom_query(http_get, expr: str) -> dict:
    qs = urllib.parse.urlencode({"query": expr})
    url = f"{PROMETHEUS_BASE}/api/v1/query?{qs}"
    status, body = http_get(url, timeout=8)
    assert status == 200, f"GET {url} expected 200, got {status}. body[:400]={body[:400]!r}"
    return json.loads(body)


@pytest.mark.postdeploy
def test_docker_engine_metrics_network_and_scrape_is_stable(retry, http_get):
    # 1) Verify the monitoring network exists and is bound to the fixed bridge name.
    net = _docker_network_inspect(MONITORING_NETWORK)
    assert net.get("Name") == MONITORING_NETWORK, net

    bridge = _get_bridge_name(net)
    assert bridge == EXPECTED_BRIDGE_NAME, (
        f"monitoring network must be bound to bridge {EXPECTED_BRIDGE_NAME} "
        f"but is {bridge!r}. Options: {net.get('Options')}"
    )

    # 1b) Verify IPAM is stable (Subnet + Gateway).
    _subnet, gateway_ip = _assert_monitoring_ipam_is_stable(net)

    # 2) Verify the endpoint is reachable from within the monitoring network.
    _assert_metrics_reachable_from_monitoring_net(gateway_ip)

    # 3) Verify Prometheus has the docker-engine target and it is up.
    targets_url = f"{PROMETHEUS_BASE}/api/v1/targets"
    status, body = http_get(targets_url, timeout=8)
    assert status == 200, f"GET {targets_url} expected 200, got {status}. body[:400]={body[:400]!r}"
    j = json.loads(body)
    assert j.get("status") == "success", f"targets endpoint failed: {j}"

    targets = j["data"]["activeTargets"]
    docker_targets = [t for t in targets if (t.get("labels") or {}).get("job") == "docker-engine"]
    assert docker_targets, "No activeTargets with job=docker-engine found (Prometheus scrape_config missing?)"

    for t in docker_targets:
        assert t.get("health") == "up", (
            f"docker-engine target not healthy: health={t.get('health')} err={t.get('lastError')} "
            f"scrapeUrl={t.get('scrapeUrl')}"
        )

        su = t.get("scrapeUrl") or ""
        assert f"http://{gateway_ip}:{DOCKER_ENGINE_PORT}/metrics" in su, (
            f"docker-engine scrapeUrl unexpected. Expected gateway-based URL "
            f"http://{gateway_ip}:{DOCKER_ENGINE_PORT}/metrics but got {su!r}"
        )

    # 4) Verify Prometheus actually ingested a core docker-engine metric (retry).
    def _check_ingestion():
        last = _prom_query(http_get, REQUIRED_SAMPLE_METRIC)
        assert last.get("status") == "success", last
        result = last.get("data", {}).get("result", [])
        assert result, f"Prometheus query returned empty result for {REQUIRED_SAMPLE_METRIC}. last={last}"

    retry(_check_ingestion, timeout_s=45, interval_s=2.0)
