# tests/postdeploy/test_35_docker_engine_metrics.py
from __future__ import annotations

import json
import urllib.parse
import urllib.request

import pytest


pytestmark = pytest.mark.postdeploy

PROMETHEUS_BASE = "http://localhost:9090"


def _http_get_json(url: str, timeout_s: int = 3) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "raspberry-pi-homelab-tests",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8", errors="strict"))


def _prom_query(expr: str, timeout_s: int = 3) -> dict:
    qs = urllib.parse.urlencode({"query": expr})
    return _http_get_json(f"{PROMETHEUS_BASE}/api/v1/query?{qs}", timeout_s=timeout_s)


def _vector_values(q: dict) -> list[float]:
    # Prometheus instant query returns:
    # {"status":"success","data":{"resultType":"vector","result":[{"value":[ts,"<number>"],...}]}}
    assert q.get("status") == "success", f"Prometheus query failed: {q}"
    data = q.get("data", {})
    assert data.get("resultType") == "vector", f"Expected vector resultType, got: {data.get('resultType')}"
    result = data.get("result", [])
    vals: list[float] = []
    for series in result:
        v = series.get("value")
        if isinstance(v, list) and len(v) == 2:
            try:
                vals.append(float(v[1]))
            except Exception:
                # ignore parse failures, will be caught by assertions later
                pass
    return vals


def test_prometheus_targets_contains_docker_engine_and_is_up():
    j = _http_get_json(f"{PROMETHEUS_BASE}/api/v1/targets", timeout_s=4)
    assert j.get("status") == "success", f"targets endpoint failed: {j}"

    targets = j["data"]["activeTargets"]
    docker_targets = [t for t in targets if t.get("labels", {}).get("job") == "docker-engine"]

    assert docker_targets, "No activeTargets with job=docker-engine found (Prometheus scrape_config missing?)"

    # You usually want exactly one on a single-host homelab, but we keep it flexible.
    for t in docker_targets:
        assert t.get("health") == "up", f"docker-engine target not healthy: health={t.get('health')} err={t.get('lastError')}"


def test_docker_engine_up_metric_is_1():
    q = _prom_query('max(up{job="docker-engine"})')
    vals = _vector_values(q)
    assert vals, 'No result for up{job="docker-engine"} (target not scraped / relabel mismatch?)'
    assert max(vals) >= 1.0, f'up{{job="docker-engine"}} is not 1: {vals}'


def test_engine_daemon_engine_info_present():
    # This is the canonical "engine is exporting metrics" signal used by many dashboards.
    q = _prom_query("count(engine_daemon_engine_info)")
    vals = _vector_values(q)
    assert vals, "No result for count(engine_daemon_engine_info)"
    assert max(vals) >= 1.0, f"engine_daemon_engine_info missing/0: {vals}"
