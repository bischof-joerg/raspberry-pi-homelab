import json
import os
import pathlib
import time
import urllib.parse
import urllib.request

import pytest


def require_postdeploy_target() -> None:
    """
    Postdeploy tests are intended to run on the deploy target (the Pi).
    Skip when running locally (WSL/laptop) unless explicitly forced.
    """
    if os.environ.get("POSTDEPLOY_ON_TARGET") == "1":
        return

    # Secondary heuristic: if your target marker file exists on the Pi
    # (adjust path if you use a different one)
    if pathlib.Path("/etc/raspberry-pi-homelab/.env").exists():
        return

    pytest.skip("postdeploy tests must run on the deploy target (set POSTDEPLOY_ON_TARGET=1 to force)")


def http_get(url: str, headers: dict | None = None, timeout: int = 5):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode()


def http_post_form(url: str, data: dict[str, str], headers: dict | None = None, timeout: int = 10):
    payload = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=headers or {}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode()


def retry(assert_fn, timeout_s: int = 60, interval_s: float = 2.5):
    """
    Simple retry helper to avoid flaky postdeploy tests.
    Used for targets/series that may take a few seconds after `compose up`.
    """
    deadline = time.time() + timeout_s
    last_err: AssertionError | None = None
    while time.time() < deadline:
        try:
            assert_fn()
            return
        except AssertionError as e:
            last_err = e
            time.sleep(interval_s)
    raise last_err or AssertionError("retry timeout")


@pytest.mark.postdeploy
def test_prometheus_ready():
    require_postdeploy_target()
    status, _ = http_get("http://127.0.0.1:9090/-/ready")
    assert status == 200


@pytest.mark.postdeploy
def test_alertmanager_ready():
    require_postdeploy_target()
    status, _ = http_get("http://127.0.0.1:9093/-/ready")
    assert status == 200


@pytest.mark.postdeploy
def test_grafana_health():
    require_postdeploy_target()
    # Grafana health endpoint does not require authentication by default.
    status, body = http_get("http://127.0.0.1:3000/api/health")
    assert status == 200, body
    data = json.loads(body)
    assert "database" in data, data


# --- VictoriaMetrics / vmalert (host-based checks; do NOT rely on container-internal tools) ---


@pytest.mark.postdeploy
def test_victoriametrics_health():
    require_postdeploy_target()
    status, body = http_get("http://127.0.0.1:8428/health")
    assert status == 200, body


@pytest.mark.postdeploy
def test_vmalert_health():
    require_postdeploy_target()
    status, body = http_get("http://127.0.0.1:8880/health")
    assert status == 200, body


def assert_vm_query_has_series(query: str):
    status, body = http_post_form(
        "http://127.0.0.1:8428/api/v1/query",
        {"query": query},
        timeout=10,
    )
    assert status == 200, body
    data = json.loads(body)
    assert data.get("status") == "success", {"query": query, "response": data}
    result = data.get("data", {}).get("result", [])
    assert len(result) > 0, {"query": query, "result_len": len(result), "response": data}


@pytest.mark.postdeploy
def test_victoriametrics_has_expected_targets():
    require_postdeploy_target()
    # These job names must match vmagent.yml `job_name` values.
    # vmagent.yml defines:
    #   victoriametrics, vmagent, vmalert, alertmanager, node-exporter, cadvisor
    # Allow time after deploy for vmagent to scrape & remote_write into VM.

    def _check():
        assert_vm_query_has_series("up")
        assert_vm_query_has_series('up{job="victoriametrics"}')
        assert_vm_query_has_series('up{job="vmagent"}')
        assert_vm_query_has_series('up{job="vmalert"}')
        assert_vm_query_has_series('up{job="alertmanager"}')
        assert_vm_query_has_series('up{job="node-exporter"}')
        assert_vm_query_has_series('up{job="cadvisor"}')

    retry(_check, timeout_s=75, interval_s=2.5)


@pytest.mark.postdeploy
def test_victoriametrics_has_cadvisor_cpu_metric():
    require_postdeploy_target()
    # cAdvisor metric naming varies across versions/config.
    # Accept either common CPU metric name.
    candidates = [
        "docker_container_cpu_usage_seconds_total",
        "container_cpu_usage_seconds_total",
    ]

    def _check():
        for q in candidates:
            try:
                assert_vm_query_has_series(q)
                return
            except AssertionError:
                continue
        raise AssertionError(
            "no expected cAdvisor CPU metric found "
            "(docker_container_cpu_usage_seconds_total or container_cpu_usage_seconds_total)"
        )

    retry(_check, timeout_s=90, interval_s=3.0)
