# tests/postdeploy/test_35_docker_engine_metrics.py
from __future__ import annotations

import json
import os
import urllib.parse

import pytest

from tests._helpers import run, which_ok

VM_BASE = "http://127.0.0.1:8428"
DOCKER_ENGINE_PORT = 9323
MONITORING_NETWORK = "monitoring"
EXPECTED_BRIDGE_NAME = "br-monitoring"
EXPECTED_SUBNET = "172.20.0.0/16"
EXPECTED_GATEWAY = "172.20.0.1"

REQUIRED_SAMPLE_METRIC = "engine_daemon_engine_info"


def _env_truthy(name: str) -> bool:
    return (os.environ.get(name, "") or "").strip().lower() in {"1", "true", "yes", "on"}


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
        "Action: verify UFW/FORWARD policy, allow rule for br-monitoring, and dockerd metrics listening on 9323."
    )


def _vm_query(http_get, expr: str) -> dict:
    qs = urllib.parse.urlencode({"query": expr})
    url = f"{VM_BASE}/api/v1/query?{qs}"
    status, body = http_get(url, timeout=8)
    assert status == 200, f"GET {url} expected 200, got {status}. body[:400]={body[:400]!r}"
    return json.loads(body)


@pytest.mark.postdeploy
def test_docker_engine_metrics_network_and_ingestion_is_stable(retry, http_get):
    """
    Guardrails:
    - REQUIRED: dockerd metrics must be reachable from inside the monitoring network (UFW/bridge policy).
    - OPTIONAL (enforceable): metrics must be ingested into VictoriaMetrics.

    Set DOCKER_ENGINE_METRICS_ENFORCE=1 once vmagent has a scrape_config for dockerd metrics.
    """

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

    # 2) REQUIRED: endpoint reachable from within the monitoring network.
    _assert_metrics_reachable_from_monitoring_net(gateway_ip)

    # 3) OPTIONAL: verify ingestion into VictoriaMetrics (eventually).
    def _check_ingestion():
        last = _vm_query(http_get, REQUIRED_SAMPLE_METRIC)
        assert last.get("status") == "success", last
        data = last.get("data") or {}
        assert data.get("resultType") in {"vector", "matrix"}, last

        result = data.get("result") or []
        assert isinstance(result, list), last

        if not result:
            msg = (
                f"VictoriaMetrics query returned empty result for {REQUIRED_SAMPLE_METRIC}.\n"
                "Action required: add a vmagent scrape_config for dockerd metrics (gateway:9323/metrics) and remote_write to VictoriaMetrics.\n"
                "Evidence: vmagent /targets currently does not list a docker-engine job.\n"
                "Check: docker run --rm --network monitoring alpine:3.20 sh -lc "
                "\"apk add --no-cache curl >/dev/null && curl -fsS http://vmagent:8429/targets | grep -n '9323' || true\"\n"
                "To enforce ingestion once configured: set DOCKER_ENGINE_METRICS_ENFORCE=1."
            )
            if _env_truthy("DOCKER_ENGINE_METRICS_ENFORCE"):
                raise AssertionError(msg)
            pytest.skip(msg)

    retry(_check_ingestion, timeout_s=90, interval_s=3.0)
