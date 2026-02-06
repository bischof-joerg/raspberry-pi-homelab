# tests/postdeploy/test_22_victorialogs_stats_query.py
from __future__ import annotations

import os
from typing import Any

import pytest
import requests


def _env_bool(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip() == "1"


def _base_url() -> str:
    # Prefer explicit override
    url = os.environ.get("VLOGS_BASE_URL", "").strip()
    if url:
        return url.rstrip("/")

    # Fallback for on-target runs (matches your curl usage)
    return "http://127.0.0.1:9428"


@pytest.mark.postdeploy
def test_victorialogs_stats_query_has_nonzero_service_bucket() -> None:
    """
    Robust smoke:
    - calls /select/logsql/stats_query
    - parses JSON
    - asserts at least one bucket with service=... has hits > 0

    Default: only runs on target (POSTDEPLOY_ON_TARGET=1).
    Optional local: set VLOGS_BASE_URL to run against a reachable instance.
    """
    on_target = _env_bool("POSTDEPLOY_ON_TARGET")
    has_url_override = bool(os.environ.get("VLOGS_BASE_URL", "").strip())

    if not on_target and not has_url_override:
        pytest.skip("POSTDEPLOY_ON_TARGET!=1 and VLOGS_BASE_URL not set")

    base = _base_url()

    # 30m window to avoid flakiness on quiet systems
    query = os.environ.get("VLOGS_STATS_QUERY", "_time:30m | stats by (service) count()")
    timeout_s = float(os.environ.get("VLOGS_TIMEOUT_SECONDS", "5"))

    r = requests.post(
        f"{base}/select/logsql/stats_query",
        data={"query": query},
        timeout=timeout_s,
    )
    r.raise_for_status()

    try:
        payload: Any = r.json()
    except Exception as e:  # pragma: no cover
        pytest.fail(f"stats_query returned non-JSON body: {e}\nBody: {r.text[:500]}")

    # VictoriaLogs may return either a list of rows or an object containing rows;
    # handle both defensively.
    # Normalize result rows across possible response shapes.
    rows: list[dict[str, Any]] = []

    # Shape A (your output): {"status":"success","data":{"result":[{"metric":{...},"value":[ts,"7"]}, ...]}}
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict) and isinstance(data.get("result"), list):
            rows = data["result"]

    # Shape B: plain list of dict rows (future-proof)
    if not rows and isinstance(payload, list):
        rows = payload

    # Shape C: {"data":[...]} or {"rows":[...]} or {"result":[...]}
    if not rows and isinstance(payload, dict):
        for k in ("data", "rows", "result"):
            v = payload.get(k)
            if isinstance(v, list):
                rows = v
                break

    if not isinstance(rows, list) or not rows:
        pytest.fail(f"Unexpected stats_query JSON shape: {type(payload)} -> {payload}")

    def _row_service(row: dict[str, Any]) -> str:
        # Prometheus-like: row["metric"]["service"]
        metric = row.get("metric")
        if isinstance(metric, dict):
            return str(metric.get("service", "")).strip()
        # Flat row: row["service"]
        return str(row.get("service", "")).strip()

    def _row_count(row: dict[str, Any]) -> int:
        # Prometheus-like: row["value"] == [ts, "7"]
        v = row.get("value")
        if isinstance(v, list) and len(v) >= 2:
            try:
                return int(float(v[1]))
            except Exception:
                return 0

        # Flat row variants
        for k in ("count()", "count", "hits", "value"):
            if k in row:
                try:
                    return int(float(row[k]))
                except Exception:
                    return 0
        return 0

    nonzero_services: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        svc = _row_service(row)
        if not svc:
            continue
        if _row_count(row) > 0:
            nonzero_services.append(svc)

    assert nonzero_services, (
        "No service bucket with count>0 returned by VictoriaLogs stats_query.\n"
        f"base={base}\nquery={query}\n"
        f"sample_json={str(payload)[:800]}"
    )

    # Accept any service bucket with count > 0
    # Common field names across stats outputs: "service", "count()", "count", "hits"
    def _get_count(row: dict[str, Any]) -> int:
        for k in ("count()", "count", "hits"):
            if k in row:
                try:
                    return int(row[k])
                except Exception:
                    return 0
        return 0

    nonzero_services: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        svc = str(row.get("service", "")).strip()
        if not svc:
            continue
        if _get_count(row) > 0:
            nonzero_services.append(svc)

    assert nonzero_services, (
        "No service bucket with count>0 returned by VictoriaLogs stats_query.\n"
        f"base={base}\nquery={query}\n"
        f"sample_json={str(payload)[:800]}"
    )
