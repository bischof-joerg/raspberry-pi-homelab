from __future__ import annotations

import json

import pytest

# Keep bases explicit and local-only: postdeploy is intended to run on the Pi.
ALERTMANAGER_BASE = "http://127.0.0.1:9093"
GRAFANA_BASE = "http://127.0.0.1:3000"
VM_BASE = "http://127.0.0.1:8428"
VMAGENT_BASE = "http://127.0.0.1:8429"
VMALERT_BASE = "http://127.0.0.1:8880"

# add later
# VLOGS_BASE = "http://127.0.0.1:9428"


# “Ready/health endpoints must exist and must be OK.”
# 404 is *always* a failure here by design.
STRICT_READY_ENDPOINTS: list[tuple[str, str]] = [
    ("alertmanager-ready", f"{ALERTMANAGER_BASE}/-/ready"),
    ("alertmanager-healthy", f"{ALERTMANAGER_BASE}/-/healthy"),
    ("victoriametrics-ready", f"{VM_BASE}/-/ready"),
    ("victoriametrics-health", f"{VM_BASE}/health"),
    ("vmagent-ready", f"{VMAGENT_BASE}/-/ready"),
    ("vmagent-health", f"{VMAGENT_BASE}/health"),
    ("vmalert-ready", f"{VMALERT_BASE}/-/ready"),
    ("vmalert-health", f"{VMALERT_BASE}/health"),
]

# later add
#    ("victorialogs-ready", f"{VLOGS_BASE}/-/ready"),
#    ("victorialogs-health", f"{VLOGS_BASE}/health"),


@pytest.mark.postdeploy
@pytest.mark.parametrize("name,url", STRICT_READY_ENDPOINTS)
def test_ready_health_endpoints_strict_200(http_get, name: str, url: str):
    status, body = http_get(url, timeout=6)
    assert status == 200, f"{name}: GET {url} expected 200, got {status}. body[:400]={body[:400]!r}"


@pytest.mark.postdeploy
def test_grafana_health(http_get):
    url = f"{GRAFANA_BASE}/api/health"
    status, body = http_get(url, timeout=6)
    assert status == 200, f"GET {url} expected 200, got {status}. body[:400]={body[:400]!r}"
    data = json.loads(body)
    assert "database" in data, data


@pytest.mark.postdeploy
def test_vmagent_targets_endpoint_strict(retry, http_get):
    """
    /targets is a “ready-adjacent” endpoint: if it is missing (404), treat as a real issue.
    We also sanity-check that the response looks like JSON with a 'status' field.
    """
    url = f"{VMAGENT_BASE}/targets"

    def _check():
        status, body = http_get(url, timeout=6)
        assert status == 200, f"GET {url} expected 200, got {status}. body[:400]={body[:400]!r}"
        payload = json.loads(body)
        # VictoriaMetrics-style APIs typically return {"status":"success", ...}
        assert isinstance(payload, dict), payload
        assert payload.get("status") in {"success", "ok"} or "data" in payload, payload

    retry(_check, timeout_s=90, interval_s=3.0)


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
