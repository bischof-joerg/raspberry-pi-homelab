import os
import base64
import json
import pytest
import urllib.request

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
    user = os.environ.get("GRAFANA_ADMIN_USER")
    pw = os.environ.get("GRAFANA_ADMIN_PASSWORD")
    assert user and pw, "Missing env vars: GRAFANA_ADMIN_USER / GRAFANA_ADMIN_PASSWORD"

    token = base64.b64encode(f"{user}:{pw}".encode()).decode()
    status, body = http_get(
        "http://127.0.0.1:3000/api/health",
        headers={"Authorization": f"Basic {token}"},
    )
    assert status == 200, body
    data = json.loads(body)
    # if database as content is, provide value of data
    # note: in this case likely an issue with Grafana DB is present
    assert "database" in data, data
