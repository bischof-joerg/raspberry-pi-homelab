# tests/postdeploy/test_35_docker_engine_metrics.py
import json
import urllib.parse
import urllib.request

import pytest

PROMETHEUS_BASE = "http://127.0.0.1:9090"


def _http_get_json(url: str, *, timeout_s: int = 5) -> dict:
    with urllib.request.urlopen(url, timeout=timeout_s) as r:
        return json.loads(r.read().decode())


def _prom_query(expr: str, *, timeout_s: int = 5) -> dict:
    qs = urllib.parse.urlencode({"query": expr})
    return _http_get_json(f"{PROMETHEUS_BASE}/api/v1/query?{qs}", timeout_s=timeout_s)


@pytest.mark.postdeploy
def test_prometheus_targets_contains_docker_engine_and_is_up():
    j = _http_get_json(f"{PROMETHEUS_BASE}/api/v1/targets", timeout_s=5)
    assert j.get("status") == "success", f"targets endpoint failed: {j}"

    targets = j["data"]["activeTargets"]
    docker_targets = [t for t in targets if t.get("labels", {}).get("job") == "docker-engine"]

    assert docker_targets, "No activeTargets with job=docker-engine found (Prometheus scrape_config missing?)"

    for t in docker_targets:
        assert t.get("health") == "up", (
            f"docker-engine target not healthy: health={t.get('health')} err={t.get('lastError')}"
        )

        scrape_url = t.get("scrapeUrl", "")
        # We mainly care that it's the engine metrics port.
        assert scrape_url.endswith(":9323/metrics") or ":9323/metrics" in scrape_url, (
            f"Unexpected scrapeUrl for docker-engine: {scrape_url}"
        )


@pytest.mark.postdeploy
def test_docker_engine_up_metric_is_1():
    # Strong signal: Prometheus itself reports the target as up.
    j = _prom_query('up{job="docker-engine"}', timeout_s=5)
    assert j.get("status") == "success", f"query failed: {j}"

    res = j["data"]["result"]
    assert res, 'No series returned for up{job="docker-engine"} (target missing or not scraped?)'

    # Accept multiple series, but all should be "1".
    bad = []
    for s in res:
        metric = s.get("metric", {})
        val = s.get("value", [None, None])[1]
        if val != "1":
            bad.append((metric, val))

    assert not bad, f'Expected up{{job="docker-engine"}} == 1, but got non-1 series: {bad}'


@pytest.mark.postdeploy
def test_docker_engine_scrape_samples_positive():
    # Another strong signal: target produces samples (not just up/down).
    j = _prom_query('scrape_samples_scraped{job="docker-engine"}', timeout_s=5)
    assert j.get("status") == "success", f"query failed: {j}"

    res = j["data"]["result"]
    assert res, 'No series returned for scrape_samples_scraped{job="docker-engine"}'

    bad = []
    for s in res:
        metric = s.get("metric", {})
        val_s = s.get("value", [None, None])[1]
        try:
            val = float(val_s)
        except Exception:
            bad.append((metric, val_s))
            continue

        if val <= 0:
            bad.append((metric, val))

    assert not bad, f"Expected scrape_samples_scraped>0 for docker-engine, got: {bad}"


@pytest.mark.postdeploy
def test_docker_engine_has_expected_engine_daemon_metrics_best_effort():
    # Dashboard 21040 typically expects engine_daemon_* metrics.
    # Depending on Docker version/config, exact metric set can vary,
    # so we check a small set of commonly present ones and require >=1 to exist.
    candidates = [
        "engine_daemon_engine_info",
        "engine_daemon_container_states_containers",
        "engine_daemon_events_total",
    ]

    found = []
    for m in candidates:
        j = _prom_query(m, timeout_s=5)
        assert j.get("status") == "success", f"query failed for {m}: {j}"
        if j["data"]["result"]:
            found.append(m)

    assert found, (
        "None of the expected docker engine metrics were found in Prometheus. "
        "Scrape may be hitting the wrong endpoint, or Docker metrics exposure does not include engine_daemon_*.\n"
        f"Tried: {candidates}"
    )
