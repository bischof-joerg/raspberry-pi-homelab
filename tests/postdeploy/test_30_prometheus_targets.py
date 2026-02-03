# tests/postdeploy/test_30_prometheus_targets.py
from __future__ import annotations

import json

import pytest

PROM_TARGETS_URL = "http://127.0.0.1:9090/api/v1/targets"

REQUIRED_JOBS = {
    "prometheus",
    "node-exporter",
    "cadvisor",
    "alertmanager",
    "grafana",
}


@pytest.mark.postdeploy
def test_prometheus_targets_up(retry, http_get):
    def _check():
        status, body = http_get(PROM_TARGETS_URL, timeout=8)
        assert status == 200, f"GET {PROM_TARGETS_URL} expected 200, got {status}. body[:400]={body[:400]!r}"

        data = json.loads(body)
        assert data.get("status") == "success", data
        active = data["data"]["activeTargets"]

        job_to_health: dict[str, list[str]] = {}
        for t in active:
            job = (t.get("labels") or {}).get("job")
            if job:
                job_to_health.setdefault(job, []).append(t.get("health", ""))

        missing = sorted(REQUIRED_JOBS - set(job_to_health.keys()))
        assert not missing, f"Missing required Prometheus jobs: {missing}. Seen: {sorted(job_to_health.keys())}"

        bad = {job: hs for job, hs in job_to_health.items() if job in REQUIRED_JOBS and any(h != "up" for h in hs)}
        assert not bad, f"Some required targets are not UP: {bad}"

    retry(_check, timeout_s=120, interval_s=3.0)
