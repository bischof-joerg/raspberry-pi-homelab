import json
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass

import pytest

ALERTMANAGER_BASE = "http://127.0.0.1:9093"
VICTORIAMETRICS_BASE = "http://127.0.0.1:8428"
VMAGENT_BASE = "http://127.0.0.1:8429"
VMALERT_BASE = "http://127.0.0.1:8880"
GRAFANA_BASE = "http://127.0.0.1:3000"
VLOGS_BASE = "http://127.0.0.1:9428"

# Container-internal endpoints (not exposed on host)
NODE_EXPORTER_INNER = "http://127.0.0.1:9100"
CADVISOR_INNER = "http://127.0.0.1:8080"
VECTOR_INNER = "http://127.0.0.1:8686"

# Default container names (as seen on your target). If your naming changes, update here.
NODE_EXPORTER_CONTAINER = "homelab-home-prod-mon-node-exporter-1"
CADVISOR_CONTAINER = "homelab-home-prod-mon-cadvisor-1"
VECTOR_CONTAINER = "homelab-home-prod-mon-vector-1"

# Curl helper image (pinned)
CURL_IMAGE = "curlimages/curl:8.11.1"


@dataclass(frozen=True)
class EndpointCheck:
    name: str
    url: str
    # Optional additional assertions on body content.
    must_contain_any: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContainerEndpointCheck:
    name: str
    container: str
    url: str
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
    # Prometheus exposition usually contains HELP/TYPE lines.
    markers = ("# HELP", "# TYPE", "vl_", "vm_", "process_", "go_")
    _assert_contains_any(body, markers, name, url)


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _container_http_get(container: str, url: str, timeout: int = 6) -> tuple[int, str]:
    """
    Perform an HTTP GET *inside* the network namespace of `container` via a short-lived curl helper container.
    Returns: (status_code, body)
    """
    # We don't use -f, because we want body+status even on non-200.
    # Output format: <body>\n<status>
    cp = _run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            f"container:{container}",
            CURL_IMAGE,
            "-sS",
            "--max-time",
            str(timeout),
            "-w",
            "\n%{http_code}",
            url,
        ]
    )

    out = (cp.stdout or "").rstrip("\n")
    if not out:
        # Distinguish "no output" from "status != 200"
        return 0, f"(empty response; docker/curl output: {cp.stdout!r})"

    # Split last line as status code
    if "\n" in out:
        body, status_s = out.rsplit("\n", 1)
    else:
        body, status_s = "", out

    try:
        status = int(status_s.strip())
    except ValueError:
        # If docker run itself failed (e.g., container not found), surface that clearly.
        return 0, f"(could not parse status; last_line={status_s!r}; output[:400]={out[:400]!r})"

    return status, body


# -------------------------
# Host-reachable endpoints
# -------------------------
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


# -----------------------------------
# Container-internal endpoints (no host ports)
# -----------------------------------
@pytest.mark.postdeploy
@pytest.mark.parametrize(
    "check",
    [
        ContainerEndpointCheck(
            "node-exporter-metrics",
            NODE_EXPORTER_CONTAINER,
            f"{NODE_EXPORTER_INNER}/metrics",
        ),
        ContainerEndpointCheck(
            "cadvisor-metrics",
            CADVISOR_CONTAINER,
            f"{CADVISOR_INNER}/metrics",
        ),
        # Your /metrics on Vector returned 404; that’s fine if Vector API is enabled but metrics endpoint is disabled.
        # We therefore check /health for liveness here, and keep the real “pipeline works” guarantee in the dedicated Vector E2E test.
        ContainerEndpointCheck(
            "vector-health",
            VECTOR_CONTAINER,
            f"{VECTOR_INNER}/health",
        ),
    ],
    ids=lambda c: c.name,
)
def test_container_internal_health_and_metrics_strict_200(retry, check: ContainerEndpointCheck):
    """Check monitoring sidecars/exporters without exposing ports on the host."""

    def _check():
        status, body = _container_http_get(check.container, check.url, timeout=6)
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
