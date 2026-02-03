# tests/postdeploy/test_20_endpoints.py
from __future__ import annotations

import json

import pytest

ALERTMANAGER_BASE = "http://127.0.0.1:9093"
GRAFANA_BASE = "http://127.0.0.1:3000"
VM_BASE = "http://127.0.0.1:8428"
VMALERT_BASE = "http://127.0.0.1:8880"


@pytest.mark.postdeploy
@pytest.mark.parametrize(
    "url",
    [
        f"{ALERTMANAGER_BASE}/-/ready",
        f"{ALERTMANAGER_BASE}/-/healthy",
        f"{VM_BASE}/health",
        f"{VMALERT_BASE}/health",
    ],
)
def test_basic_health_endpoints_200(http_get, url: str):
    status, body = http_get(url, timeout=6)
    assert status == 200, f"GET {url} expected 200, got {status}. body[:400]={body[:400]!r}"


@pytest.mark.postdeploy
def test_grafana_health(http_get):
    url = f"{GRAFANA_BASE}/api/health"
    status, body = http_get(url, timeout=6)
    assert status == 200, f"GET {url} expected 200, got {status}. body[:400]={body[:400]!r}"
    data = json.loads(body)
    assert "database" in data, data


@pytest.mark.postdeploy
def test_vmalert_rules_endpoint(retry, http_get):
    url = f"{VMALERT_BASE}/api/v1/rules"

    def _check():
        status, body = http_get(url, timeout=6)
        assert status == 200, f"GET {url} expected 200, got {status}. body[:400]={body[:400]!r}"

        payload = json.loads(body)
        assert payload.get("status") == "success", payload

        groups = payload.get("data", {}).get("groups")
        if groups is None:
            groups = payload.get("groups")

        assert isinstance(groups, list), payload
        assert groups, payload  # rules should exist once shipped

    retry(_check, timeout_s=90, interval_s=3.0)
