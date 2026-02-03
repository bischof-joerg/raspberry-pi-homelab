# tests/postdeploy/test_21_victoriametrics_queries.py
from __future__ import annotations

import json
import os
import urllib.parse

import pytest

VM_BASE = "http://127.0.0.1:8428"


def _env_csv(name: str) -> list[str]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def vm_query(http_get, expr: str) -> dict:
    qs = urllib.parse.urlencode({"query": expr})
    url = f"{VM_BASE}/api/v1/query?{qs}"
    status, body = http_get(url, timeout=8)
    assert status == 200, f"GET {url} expected 200, got {status}. body[:400]={body[:400]!r}"
    payload = json.loads(body)
    assert payload.get("status") == "success", payload
    return payload


def _result(payload: dict) -> tuple[str, list]:
    data = payload.get("data") or {}
    result_type = data.get("resultType")
    result = data.get("result")
    assert isinstance(result_type, str), payload
    assert isinstance(result, list), payload
    return result_type, result


def _metric_names_from_vector(result: list) -> set[str]:
    names: set[str] = set()
    for item in result:
        metric = item.get("metric") or {}
        if "__name__" in metric:
            names.add(metric["__name__"])
    return names


@pytest.mark.postdeploy
def test_vm_query_api_responds_and_success(http_get):
    payload = vm_query(http_get, "1")
    result_type, result = _result(payload)
    assert result_type in {"vector", "scalar", "matrix"}, (result_type, payload)
    assert isinstance(result, list), payload


@pytest.mark.postdeploy
def test_vm_query_up_metric_exists(retry, http_get):
    def _check():
        payload = vm_query(http_get, "up")
        result_type, result = _result(payload)
        assert result_type == "vector", payload
        assert result, payload

        names = _metric_names_from_vector(result)
        assert "up" in names, names

    retry(_check, timeout_s=120, interval_s=3.0)


@pytest.mark.postdeploy
def test_vm_expected_metrics_optional(retry, http_get):
    expected = _env_csv("VM_EXPECT_METRICS")
    if not expected:
        pytest.skip("VM_EXPECT_METRICS not set")

    # Exact-match metric names using regex alternation
    selector = '{__name__=~"(' + "|".join(expected) + ')"}'

    def _check():
        payload = vm_query(http_get, selector)
        result_type, result = _result(payload)
        assert result_type == "vector", payload
        assert result, payload

        names = _metric_names_from_vector(result)
        missing = sorted(set(expected) - names)
        assert not missing, {"missing": missing, "present": sorted(names)}

    retry(_check, timeout_s=120, interval_s=3.0)


@pytest.mark.postdeploy
def test_vm_expected_jobs_optional(retry, http_get):
    jobs = _env_csv("VM_EXPECT_JOBS")
    if not jobs:
        pytest.skip("VM_EXPECT_JOBS not set")

    for job in jobs:

        def _check(job=job):
            payload = vm_query(http_get, f'up{{job="{job}"}}')
            result_type, result = _result(payload)
            assert result_type == "vector", payload
            assert result, {"job": job, "payload": payload}

        retry(_check, timeout_s=120, interval_s=3.0)
