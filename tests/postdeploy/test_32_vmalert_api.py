import json
import urllib.request

import pytest

VMALERT_BASE = "http://127.0.0.1:8880"


def _get_json(url: str, timeout_s: int = 5) -> dict:
    with urllib.request.urlopen(url, timeout=timeout_s) as r:
        return json.loads(r.read().decode())


@pytest.mark.postdeploy
def test_vmalert_rules_endpoint_returns_groups():
    j = _get_json(f"{VMALERT_BASE}/api/v1/rules", timeout_s=5)
    assert j.get("status") == "success", j
    groups = j.get("data", {}).get("groups", [])
    assert isinstance(groups, list), j
    # OK if empty early in migration, but usually you'd expect at least one group
    # once you ship your first rules bundle.
    # If you want strict: assert groups, j


@pytest.mark.postdeploy
def test_vmalert_alerts_endpoint_responds():
    j = _get_json(f"{VMALERT_BASE}/api/v1/alerts", timeout_s=5)
    assert j.get("status") == "success", j
