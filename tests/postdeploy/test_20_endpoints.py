# tests/postdeploy/test_20_endpoints.py
import json
import os
import pathlib
import time
import urllib.request

import pytest

PROMETHEUS_BASE = "http://127.0.0.1:9090"
ALERTMANAGER_BASE = "http://127.0.0.1:9093"
GRAFANA_BASE = "http://127.0.0.1:3000"
VICTORIAMETRICS_BASE = "http://127.0.0.1:8428"
VMALERT_BASE = "http://127.0.0.1:8880"


def require_postdeploy_target() -> None:
    """
    Postdeploy tests are intended to run on the deploy target (the Pi).
    Skip when running locally (WSL/laptop) unless explicitly forced.
    """
    if os.environ.get("POSTDEPLOY_ON_TARGET") == "1":
        return

    # Marker file exists on the Pi
    if pathlib.Path("/etc/raspberry-pi-homelab/.env").exists():
        return

    pytest.skip("postdeploy tests must run on the deploy target (set POSTDEPLOY_ON_TARGET=1 to force)")


def http_get(url: str, timeout: int = 5):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode()


def retry(assert_fn, timeout_s: int = 45, interval_s: float = 2.0):
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


# --- Prometheus (published on host: 127.0.0.1:9090) ---


@pytest.mark.postdeploy
def test_prometheus_ready():
    require_postdeploy_target()
    status, body = http_get(f"{PROMETHEUS_BASE}/-/ready")
    assert status == 200, body


@pytest.mark.postdeploy
def test_prometheus_healthy():
    require_postdeploy_target()
    status, body = http_get(f"{PROMETHEUS_BASE}/-/healthy")
    assert status == 200, body


# --- Alertmanager (published on host: 127.0.0.1:9093) ---


@pytest.mark.postdeploy
def test_alertmanager_ready():
    require_postdeploy_target()
    status, body = http_get(f"{ALERTMANAGER_BASE}/-/ready")
    assert status == 200, body


@pytest.mark.postdeploy
def test_alertmanager_healthy():
    require_postdeploy_target()
    status, body = http_get(f"{ALERTMANAGER_BASE}/-/healthy")
    assert status == 200, body


# --- Grafana (published on host: 127.0.0.1:3000) ---


@pytest.mark.postdeploy
def test_grafana_health():
    require_postdeploy_target()

    def _check():
        status, body = http_get(f"{GRAFANA_BASE}/api/health")
        assert status == 200, body
        data = json.loads(body)
        assert "database" in data, data

    retry(_check, timeout_s=60, interval_s=2.0)


# --- VictoriaMetrics (published on host: 127.0.0.1:8428) ---


@pytest.mark.postdeploy
def test_victoriametrics_health():
    require_postdeploy_target()
    status, body = http_get(f"{VICTORIAMETRICS_BASE}/health")
    assert status == 200, body


# --- vmalert (published on host: 127.0.0.1:8880) ---
# Note: vmalert "/ready" is NOT a valid endpoint in your setup (returns 400),
# so we only check endpoints that actually exist.


@pytest.mark.postdeploy
def test_vmalert_health():
    require_postdeploy_target()
    status, body = http_get(f"{VMALERT_BASE}/health")
    assert status == 200, body


@pytest.mark.postdeploy
def test_vmalert_rules_endpoint():
    require_postdeploy_target()

    def _check():
        status, body = http_get(f"{VMALERT_BASE}/api/v1/rules")
        assert status == 200, body
        data = json.loads(body)
        assert "groups" in data, data

    retry(_check, timeout_s=60, interval_s=2.0)


@pytest.mark.postdeploy
def test_vmalert_alerts_endpoint():
    require_postdeploy_target()
    status, body = http_get(f"{VMALERT_BASE}/api/v1/alerts")
    assert status == 200, body
