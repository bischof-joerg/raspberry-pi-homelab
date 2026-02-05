import json

import pytest

ALERTMANAGER_BASE = "http://127.0.0.1:9093"
VICTORIAMETRICS_BASE = "http://127.0.0.1:8428"
VMAGENT_BASE = "http://127.0.0.1:8429"
VMALERT_BASE = "http://127.0.0.1:8880"
GRAFANA_BASE = "http://127.0.0.1:3000"
# add later
# VLOGS_BASE = "http://127.0.0.1:9428"


@pytest.mark.postdeploy
@pytest.mark.parametrize(
    "name,url",
    [
        ("alertmanager-ready", f"{ALERTMANAGER_BASE}/-/ready"),
        ("alertmanager-healthy", f"{ALERTMANAGER_BASE}/-/healthy"),
        ("victoriametrics-ready", f"{VICTORIAMETRICS_BASE}/-/ready"),
        ("victoriametrics-health", f"{VICTORIAMETRICS_BASE}/health"),
        ("vmagent-ready", f"{VMAGENT_BASE}/-/ready"),
        ("vmagent-health", f"{VMAGENT_BASE}/health"),
        ("vmalert-ready", f"{VMALERT_BASE}/-/ready"),
        ("vmalert-health", f"{VMALERT_BASE}/health"),
    ],
)
# later add
#    ("victorialogs-ready", f"{VLOGS_BASE}/-/ready"),
#    ("victorialogs-health", f"{VLOGS_BASE}/health")

def test_ready_health_endpoints_strict_200(retry, http_get, name, url):
    """These endpoints must exist and return 200 when the service is healthy."""

    def _check():
        status, body = http_get(url, timeout=6)
        assert status == 200, (
            f"{name}: GET {url} expected 200, got {status}. body[:400]={body[:400]!r}"
        )

    retry(_check, timeout_s=90, interval_s=3.0)


@pytest.mark.postdeploy
def test_grafana_health(retry, http_get):
    """Grafana health endpoint must return 200 and contain an expected marker."""
    url = f"{GRAFANA_BASE}/api/health"

    def _check():
        status, body = http_get(url, timeout=6)
        assert status == 200, f"GET {url} expected 200, got {status}. body[:400]={body[:400]!r}"
        payload = json.loads(body)
        assert isinstance(payload, dict), payload
        assert payload.get("database") in {"ok", "healthy"} or "version" in payload, payload

    retry(_check, timeout_s=90, interval_s=3.0)


def _looks_like_json(body: str) -> bool:
    b = body.lstrip()
    return b.startswith("{") or b.startswith("[")


@pytest.mark.postdeploy
def test_vmagent_targets_endpoint_strict(retry, http_get):
    """
    /targets is a “ready-adjacent” endpoint: if it is missing (404), treat as a real issue.

    vmagent's /targets output is often plain text (Prometheus-style), not JSON.
    We accept either:
      - JSON with status/data fields, OR
      - text containing expected markers (job= / state= / up)
    """
    url = f"{VMAGENT_BASE}/targets"

    def _check():
        status, body = http_get(url, timeout=6)
        assert status == 200, f"GET {url} expected 200, got {status}. body[:400]={body[:400]!r}"

        if _looks_like_json(body):
            payload = json.loads(body)
            assert isinstance(payload, (dict, list)), payload
            if isinstance(payload, dict):
                assert payload.get("status") in {"success", "ok"} or "data" in payload, payload
        else:
            assert len(body.strip()) > 0, "targets response is empty"
            must_have_any = ("job=", "state=", " up", " down")
            assert any(m in body for m in must_have_any), (
                f"targets response unexpected: body[:400]={body[:400]!r}"
            )

    retry(_check, timeout_s=90, interval_s=3.0)
