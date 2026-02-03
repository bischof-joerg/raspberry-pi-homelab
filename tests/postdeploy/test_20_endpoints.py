import json
import os
import pathlib
import time
import urllib.request

import pytest

PROM_BASE = "http://127.0.0.1:9090"
ALERTMANAGER_BASE = "http://127.0.0.1:9093"
GRAFANA_BASE = "http://127.0.0.1:3000"
VM_BASE = "http://127.0.0.1:8428"
VMALERT_BASE = "http://127.0.0.1:8880"


def require_postdeploy_target() -> None:
    """Skip locally unless explicitly forced.

    Postdeploy tests are intended to run on the deploy target (the Pi).
    Set POSTDEPLOY_ON_TARGET=1 to force running them elsewhere.
    """
    if os.environ.get("POSTDEPLOY_ON_TARGET") == "1":
        return

    # Heuristic: marker file exists on the Pi
    if pathlib.Path("/etc/raspberry-pi-homelab/.env").exists():
        return

    pytest.skip("postdeploy tests must run on the deploy target (set POSTDEPLOY_ON_TARGET=1 to force)")


def http_get(url: str, headers: dict | None = None, timeout: int = 5) -> tuple[int, str]:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode()


def retry(assert_fn, timeout_s: int = 60, interval_s: float = 2.5) -> None:
    """Simple retry helper to avoid flaky postdeploy tests."""
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


# --- Prometheus ---


@pytest.mark.postdeploy
def test_prometheus_ready():
    require_postdeploy_target()
    status, _ = http_get(f"{PROM_BASE}/-/ready")
    assert status == 200


@pytest.mark.postdeploy
def test_prometheus_healthy():
    require_postdeploy_target()
    status, _ = http_get(f"{PROM_BASE}/-/healthy")
    assert status == 200


# --- Alertmanager ---


@pytest.mark.postdeploy
def test_alertmanager_ready():
    require_postdeploy_target()
    status, _ = http_get(f"{ALERTMANAGER_BASE}/-/ready")
    assert status == 200


@pytest.mark.postdeploy
def test_alertmanager_healthy():
    require_postdeploy_target()
    status, _ = http_get(f"{ALERTMANAGER_BASE}/-/healthy")
    assert status == 200


# --- Grafana ---


@pytest.mark.postdeploy
def test_grafana_health():
    require_postdeploy_target()
    status, body = http_get(f"{GRAFANA_BASE}/api/health")
    assert status == 200, body
    data = json.loads(body)
    assert "database" in data, data


# --- VictoriaMetrics ---


@pytest.mark.postdeploy
def test_victoriametrics_health():
    require_postdeploy_target()
    status, body = http_get(f"{VM_BASE}/health")
    assert status == 200, body


# --- vmalert ---


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
        payload = json.loads(body)

        # vmalert returns: {"status":"success","data":{"groups":[...]}}
        assert payload.get("status") == "success", payload

        groups = payload.get("data", {}).get("groups")
        if groups is None:
            # Fallback for other shapes (or future changes)
            groups = payload.get("groups")

        assert isinstance(groups, list), payload
        assert len(groups) > 0, payload

    retry(_check, timeout_s=60, interval_s=2.0)
