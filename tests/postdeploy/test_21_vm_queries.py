# tests/postdeploy/test_21_victoriametrics_queries.py
from __future__ import annotations

import json
import os
import re
import urllib.parse

import pytest

VM_BASE = "http://127.0.0.1:8428"
_METRIC_NAME_RE = re.compile(r"^[a-zA-Z_:][a-zA-Z0-9_:]*$")


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

    def _normalize(item: str) -> str:
        # tolerate accidental quoting in env var, e.g. '"up"' or "'up'"
        s = item.strip()
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            s = s[1:-1].strip()
        return s

    expected = [_normalize(x) for x in expected if _normalize(x)]
    assert expected, "VM_EXPECT_METRICS was set but empty after normalization"

    def _check_one(expr_or_name: str) -> None:
        # If it's a plain metric name, query by name; otherwise treat as PromQL expression.
        expr = expr_or_name if not _METRIC_NAME_RE.match(expr_or_name) else expr_or_name

        payload = vm_query(http_get, expr)
        result_type, result = _result(payload)

        # Most instant queries yield vector; allow scalar for expressions like "1".
        assert result_type in {"vector", "scalar"}, {"expr": expr, "payload": payload}

        if result_type == "vector":
            assert result, {"expr": expr, "payload": payload}

    # Retry the whole set to allow scrape/ingestion to settle
    def _check_all():
        missing = []
        for item in expected:
            try:
                _check_one(item)
            except AssertionError:
                missing.append(item)
        assert not missing, {"missing_or_empty": missing, "expected": expected}

    retry(_check_all, timeout_s=120, interval_s=3.0)


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
