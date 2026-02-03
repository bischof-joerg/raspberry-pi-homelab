import json
import os
import pathlib
import time
import urllib.parse
import urllib.request

import pytest

VM_BASE = "http://127.0.0.1:8428"


def require_postdeploy_target() -> None:
    """Skip locally unless explicitly forced.

    Postdeploy tests are intended to run on the deploy target (the Pi).
    Set POSTDEPLOY_ON_TARGET=1 to force running them elsewhere.
    """
    if os.environ.get("POSTDEPLOY_ON_TARGET") == "1":
        return

    if pathlib.Path("/etc/raspberry-pi-homelab/.env").exists():
        return

    pytest.skip("postdeploy tests must run on the deploy target (set POSTDEPLOY_ON_TARGET=1 to force)")


def http_get(url: str, headers: dict | None = None, timeout: int = 8) -> tuple[int, str]:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode()


def retry(assert_fn, timeout_s: int = 60, interval_s: float = 2.5) -> None:
    deadline = time.time() + timeout_s
    last_err: AssertionError | None = None
    while time.time() < deadline:
        try:
            assert_fn()
            return
        except AssertionError as e:
            last_err = e
            time.sleep(interval_s)
    raise last_err or AssertionError("retry timeout")


def vm_query(expr: str) -> dict:
    qs = urllib.parse.urlencode({"query": expr})
    url = f"{VM_BASE}/api/v1/query?{qs}"
    status, body = http_get(url)
    assert status == 200, body
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


def _env_csv(name: str) -> list[str]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


@pytest.mark.postdeploy
def test_vm_query_api_responds_and_success():
    """Baseline: query API answers + returns success."""
    require_postdeploy_target()
    payload = vm_query("1")
    result_type, result = _result(payload)
    # For instant query, VM typically returns vector with one sample; accept any sane type.
    assert result_type in {"vector", "scalar", "matrix"}, (result_type, payload)
    assert isinstance(result, list), payload


@pytest.mark.postdeploy
def test_vm_query_up_metric_exists():
    """Default expectation: 'up' exists once ingestion is running."""
    require_postdeploy_target()

    def _check():
        payload = vm_query("up")
        result_type, result = _result(payload)
        assert result_type == "vector", payload
        assert len(result) > 0, payload  # at least one target ingested

        names = _metric_names_from_vector(result)
        # If ingestion is correct, VM stores a metric named 'up'.
        assert "up" in names, names

    retry(_check, timeout_s=90, interval_s=3.0)


@pytest.mark.postdeploy
def test_vm_expected_metrics_optional():
    """Optional stricter assertions.

    Set VM_EXPECT_METRICS="up,vm_app_version,..." to enforce presence.
    """
    require_postdeploy_target()
    expected = _env_csv("VM_EXPECT_METRICS")
    if not expected:
        pytest.skip("VM_EXPECT_METRICS not set")

    def _check():
        payload = vm_query('{__name__=~"(' + "|".join(expected) + ')"}')
        result_type, result = _result(payload)
        assert result_type == "vector", payload
        assert len(result) > 0, payload

        names = _metric_names_from_vector(result)
        missing = sorted(set(expected) - names)
        assert not missing, {"missing": missing, "present": sorted(names)}

    retry(_check, timeout_s=90, interval_s=3.0)


@pytest.mark.postdeploy
def test_vm_expected_jobs_optional():
    """Optional job-level checks.

    Set VM_EXPECT_JOBS="node-exporter,cadvisor,..." to enforce at least one 'up{job="<job>"} == 1'.
    """
    require_postdeploy_target()
    jobs = _env_csv("VM_EXPECT_JOBS")
    if not jobs:
        pytest.skip("VM_EXPECT_JOBS not set")

    def _check_job(job: str) -> None:
        payload = vm_query(f'up{{job="{job}"}}')
        result_type, result = _result(payload)
        assert result_type == "vector", payload
        assert len(result) > 0, {"job": job, "payload": payload}

    for job in jobs:
        retry(lambda j=job: _check_job(j), timeout_s=90, interval_s=3.0)
