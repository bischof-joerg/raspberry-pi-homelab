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
    rows = payload
    if isinstance(payload, dict):
        # common patterns: {"data":[...]} or {"rows":[...]} – tolerate both
        rows = payload.get("data") or payload.get("rows") or payload.get("result")

    if not isinstance(rows, list):
        pytest.fail(f"Unexpected stats_query JSON shape: {type(payload)} -> {payload}")

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
