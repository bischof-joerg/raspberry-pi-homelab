import json
from collections.abc import Iterable
from dataclasses import dataclass

import pytest

ALERTMANAGER_BASE = "http://127.0.0.1:9093"
VICTORIAMETRICS_BASE = "http://127.0.0.1:8428"
VMAGENT_BASE = "http://127.0.0.1:8429"
VMALERT_BASE = "http://127.0.0.1:8880"
GRAFANA_BASE = "http://127.0.0.1:3000"
VLOGS_BASE = "http://127.0.0.1:9428"


@dataclass(frozen=True)
class EndpointCheck:
    name: str
    url: str
    # Optional additional assertions on body content.
    must_contain_any: tuple[str, ...] = ()


def _looks_like_json(body: str) -> bool:
    b = body.lstrip()
    return b.startswith("{") or b.startswith("[")


def _assert_200(status: int, body: str, name: str, url: str) -> None:
    assert status == 200, f"{name}: GET {url} expected 200, got {status}. body[:400]={body[:400]!r}"


def _assert_contains_any(body: str, needles: Iterable[str], name: str, url: str) -> None:
    if not needles:
        return
    assert any(n in body for n in needles), (
        f"{name}: GET {url} body missing expected markers {list(needles)!r}. "
        f"body[:400]={body[:400]!r}"
    )


# Stronger checks for endpoints where "200" alone is too weak.
def _validate_metrics(body: str, name: str, url: str) -> None:
    # Prometheus exposition usually contains HELP/TYPE lines; VictoriaLogs exposes many metrics.
    # Accept either HELP/TYPE markers or a few common metric prefixes.
    markers = ("# HELP", "# TYPE", "vl_", "vm_", "process_", "go_")
    _assert_contains_any(body, markers, name, url)


@pytest.mark.postdeploy
@pytest.mark.parametrize(
    "check",
    [
        # Alertmanager
        EndpointCheck("alertmanager-ready", f"{ALERTMANAGER_BASE}/-/ready"),
        EndpointCheck("alertmanager-healthy", f"{ALERTMANAGER_BASE}/-/healthy"),
        # VictoriaMetrics single-node
        EndpointCheck("victoriametrics-ready", f"{VICTORIAMETRICS_BASE}/-/ready"),
        EndpointCheck("victoriametrics-health", f"{VICTORIAMETRICS_BASE}/health"),
        # vmagent
        EndpointCheck("vmagent-ready", f"{VMAGENT_BASE}/-/ready"),
        EndpointCheck("vmagent-health", f"{VMAGENT_BASE}/health"),
        # vmalert
        EndpointCheck("vmalert-ready", f"{VMALERT_BASE}/-/ready"),
        EndpointCheck("vmalert-health", f"{VMALERT_BASE}/health"),
        # VictoriaLogs:
        # - /insert/ready is the documented ingest-readiness probe for Loki-compatible shippers (Vector, etc.)
        # - /metrics must exist for scraping
        EndpointCheck("victorialogs-insert-ready", f"{VLOGS_BASE}/insert/ready"),
        EndpointCheck("victorialogs-metrics", f"{VLOGS_BASE}/metrics"),
    ],
    ids=lambda c: c.name,
)
def test_ready_health_endpoints_strict_200(retry, http_get, check: EndpointCheck):
    """These endpoints must exist and return 200 when the service is healthy."""

    def _check():
        status, body = http_get(check.url, timeout=6)
        _assert_200(status, body, check.name, check.url)

        if check.name.endswith("-metrics"):
            _validate_metrics(body, check.name, check.url)
        else:
            _assert_contains_any(body, check.must_contain_any, check.name, check.url)

    retry(_check, timeout_s=90, interval_s=3.0)


@pytest.mark.postdeploy
def test_grafana_health(retry, http_get):
    """Grafana health endpoint must return 200 and contain an expected marker."""
    url = f"{GRAFANA_BASE}/api/health"

    def _check():
        status, body = http_get(url, timeout=6)
        _assert_200(status, body, "grafana-health", url)
        payload = json.loads(body)
        assert isinstance(payload, dict), payload
        assert payload.get("database") in {"ok", "healthy"} or "version" in payload, payload

    retry(_check, timeout_s=90, interval_s=3.0)


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
        _assert_200(status, body, "vmagent-targets", url)

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
