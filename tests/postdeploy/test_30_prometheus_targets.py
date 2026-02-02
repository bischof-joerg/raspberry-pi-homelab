import json
import urllib.request

import pytest

REQUIRED_JOBS = {
    "prometheus",
    "node-exporter",
    "cadvisor",
    "alertmanager",
    "grafana",
    # extend upon additional jobs added to prometheus/prometheus.yml: "docker-exporter",  ...
}


@pytest.mark.postdeploy
def test_prometheus_targets_up():
    with urllib.request.urlopen("http://127.0.0.1:9090/api/v1/targets", timeout=5) as r:
        data = json.loads(r.read().decode())

    assert data.get("status") == "success", data
    active = data["data"]["activeTargets"]

    job_to_health = {}
    for t in active:
        job = t["labels"].get("job")
        if job:
            job_to_health.setdefault(job, []).append(t["health"])

    missing = sorted(REQUIRED_JOBS - set(job_to_health.keys()))
    assert not missing, f"Missing required Prometheus jobs: {missing}"

    bad = {job: hs for job, hs in job_to_health.items() if job in REQUIRED_JOBS and any(h != "up" for h in hs)}
    assert not bad, f"Some required targets are not UP: {bad}"
