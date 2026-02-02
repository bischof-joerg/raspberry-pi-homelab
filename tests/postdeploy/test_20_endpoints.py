import json
import urllib.request

import pytest


def http_get(url: str, headers: dict | None = None, timeout: int = 5):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode()


@pytest.mark.postdeploy
def test_prometheus_ready():
    status, _ = http_get("http://127.0.0.1:9090/-/ready")
    assert status == 200


@pytest.mark.postdeploy
def test_alertmanager_ready():
    status, _ = http_get("http://127.0.0.1:9093/-/ready")
    assert status == 200


@pytest.mark.postdeploy
def test_grafana_health():
    # Grafana health endpoint does not require authentication by default.
    status, body = http_get("http://127.0.0.1:3000/api/health")
    assert status == 200, body
    data = json.loads(body)
    assert "database" in data, data
