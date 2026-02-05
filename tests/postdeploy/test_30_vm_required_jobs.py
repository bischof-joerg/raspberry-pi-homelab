from __future__ import annotations

import json
import urllib.parse

import pytest

VM_BASE = "http://127.0.0.1:8428"

REQUIRED_JOBS = {
    "alertmanager",
    "cadvisor",
    "node-exporter",
    "victoriametrics",
    "vmagent",
    "vmalert",
}


def _vm_query(http_get, expr: str) -> dict:
    qs = urllib.parse.urlencode({"query": expr})
    url = f"{VM_BASE}/api/v1/query?{qs}"
    status, body = http_get(url, timeout=8)
    assert status == 200, f"GET {url} expected 200, got {status}. body[:400]={body[:400]!r}"
    payload = json.loads(body)
    assert payload.get("status") == "success", payload
    return payload


def _vector_result(payload: dict) -> list[dict]:
    data = payload.get("data") or {}
    assert data.get("resultType") == "vector", payload
    result = data.get("result")
    assert isinstance(result, list), payload
    return result


@pytest.mark.postdeploy
def test_vm_required_jobs_present_and_up(retry, http_get):
    """
    Ensures scraping + ingestion into VictoriaMetrics is healthy:
    - all required jobs must exist in `count by(job) (up)`
    - each required job must have at least one UP target (up==1)
    """

    def _check():
        payload = _vm_query(http_get, "count by (job) (up)")
        result = _vector_result(payload)

        present_jobs = {((it.get("metric") or {}).get("job") or "") for it in result}
        present_jobs.discard("")

        missing = sorted(REQUIRED_JOBS - present_jobs)
        assert not missing, {
            "missing_jobs": missing,
            "present_jobs": sorted(present_jobs),
            "action": (
                "Missing jobs in VictoriaMetrics. Action: verify vmagent scrape configs and remote_write; "
                "check vmagent /targets UI; ensure services are on the monitoring network."
            ),
        }

        for job in sorted(REQUIRED_JOBS):
            p = _vm_query(http_get, f'up{{job="{job}"}}')
            r = _vector_result(p)
            assert r, {
                "job": job,
                "action": f'No series for up{{job="{job}"}}. Action: check vmagent scrape job "{job}" and connectivity.',
            }

            values = []
            for it in r:
                v = it.get("value") or []
                if isinstance(v, list) and len(v) == 2:
                    values.append(v[1])

            assert any(x == "1" for x in values), {
                "job": job,
                "values": values[:10],
                "action": (
                    f'Job "{job}" exists but no target is UP=1. Action: inspect vmagent /targets, service health, network/UFW.'
                ),
            }

    retry(_check, timeout_s=120, interval_s=3.0)
