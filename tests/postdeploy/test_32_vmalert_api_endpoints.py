# tests/postdeploy/test_32_vmalert_api.py
from __future__ import annotations

import json

import pytest

VMALERT_BASE = "http://127.0.0.1:8880"


def _get_json(http_get, url: str) -> dict:
    status, body = http_get(url, timeout=8)
    assert status == 200, f"GET {url} expected 200, got {status}. body[:400]={body[:400]!r}"
    return json.loads(body)


@pytest.mark.postdeploy
def test_vmalert_rules_endpoint_returns_groups(retry, http_get):
    url = f"{VMALERT_BASE}/api/v1/rules"

    def _check():
        j = _get_json(http_get, url)
        assert j.get("status") == "success", j
        groups = j.get("data", {}).get("groups", [])
        assert isinstance(groups, list), j
        assert groups, j  # strict by default (breaking change)

    retry(_check, timeout_s=120, interval_s=3.0)


@pytest.mark.postdeploy
def test_vmalert_alerts_endpoint_responds(http_get):
    url = f"{VMALERT_BASE}/api/v1/alerts"
    j = _get_json(http_get, url)
    assert j.get("status") == "success", j
