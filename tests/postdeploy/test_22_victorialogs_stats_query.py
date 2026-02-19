from __future__ import annotations

import os
import subprocess
import time
import uuid
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


def _extract_rows(payload: Any) -> list[dict[str, Any]]:
    """
    VictoriaLogs /select/logsql/stats_query can return a Prometheus-like shape:
      {"status":"success","data":{"resultType":"vector","result":[{"metric":{...},"value":[ts,"7"]}, ...]}}
    Be tolerant to a couple of other potential shapes as well.
    """
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict):
            result = data.get("result")
            if isinstance(result, list):
                return [r for r in result if isinstance(r, dict)]

        # Fallbacks if an alternative shape is returned
        for k in ("rows", "result"):
            v = payload.get(k)
            if isinstance(v, list):
                return [r for r in v if isinstance(r, dict)]

    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]

    return []


def _row_service(row: dict[str, Any]) -> str:
    metric = row.get("metric")
    if isinstance(metric, dict):
        return str(metric.get("service", "")).strip()
    return str(row.get("service", "")).strip()


def _row_count(row: dict[str, Any]) -> int:
    # Prometheus-like: row["value"] == [ts, "7"]
    v = row.get("value")
    if isinstance(v, list) and len(v) >= 2:
        try:
            return int(float(v[1]))
        except Exception:
            return 0

    # Flat row variants (future-proof)
    for k in ("count(*)", "count()", "count", "hits", "value"):
        if k in row:
            try:
                return int(float(row[k]))
            except Exception:
                return 0

    return 0


def _vlogs_query(base: str, query: str, timeout_s: float) -> str:
    r = requests.post(
        f"{base}/select/logsql/query",
        data={"query": query},
        timeout=timeout_s,
    )
    r.raise_for_status()
    return r.text or ""


COMPOSE_PROJECT = (
    os.environ.get("COMPOSE_PROJECT", "homelab-home-prod-mon").strip() or "homelab-home-prod-mon"
)


def _emit_seed_log_token(token: str) -> None:
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--label",
            f"com.docker.compose.project={COMPOSE_PROJECT}",
            "--label",
            "com.docker.compose.service=vlogs-seed",
            "alpine:3.20",
            "sh",
            "-lc",
            f"echo {token}",
        ],
        check=True,
        text=True,
        capture_output=True,
    )


def _wait_for_token_in_vlogs(base: str, token: str, timeout_s: float) -> None:
    """
    Poll VictoriaLogs until the token appears in _msg. Needed because ingestion is async
    (docker -> vector -> victorialogs).
    """
    deadline = time.time() + timeout_s
    last = ""
    # Token has no spaces => quoting ok. Keep LogsQL simple.
    q = f'_time:10m _msg:"{token}" | limit 5'

    interval = 0.5
    while time.time() < deadline:
        try:
            last = _vlogs_query(base, q, timeout_s=min(5.0, timeout_s))
            if token in last:
                return
        except Exception as e:  # noqa: BLE001
            last = str(e)

        time.sleep(interval)
        interval = min(interval * 1.5, 3.0)

    raise AssertionError(
        "Token did not appear in VictoriaLogs within timeout.\n"
        f"base={base}\nquery={q!r}\nlast={last[:1200]!r}"
    )


@pytest.mark.postdeploy
def test_victorialogs_stats_query_has_nonzero_service_bucket() -> None:
    """
    Robust smoke:
    - triggers a log line (so stats aren't empty on fresh systems)
    - waits until it is ingested into VictoriaLogs (async pipeline)
    - calls /select/logsql/stats_query
    - parses JSON
    - asserts at least one bucket with non-empty service has count > 0

    Default: only runs on target (POSTDEPLOY_ON_TARGET=1).
    Optional local: set VLOGS_BASE_URL to run against a reachable instance.
    """
    on_target = _env_bool("POSTDEPLOY_ON_TARGET")
    has_url_override = bool(os.environ.get("VLOGS_BASE_URL", "").strip())

    if not on_target and not has_url_override:
        pytest.skip("POSTDEPLOY_ON_TARGET!=1 and VLOGS_BASE_URL not set")

    base = _base_url()

    timeout_s = float(os.environ.get("VLOGS_TIMEOUT_SECONDS", "5"))
    # Separate timeout for "seed log + wait", keep it modest but > pipeline latency
    seed_timeout_s = float(os.environ.get("VLOGS_SEED_TIMEOUT_SECONDS", "20"))

    # 0) Seed: generate one known log event that should get a service label
    token = f"vlogs-stats-seed-{uuid.uuid4()}"
    _emit_seed_log_token(token)
    _wait_for_token_in_vlogs(base, token, timeout_s=seed_timeout_s)

    # 1) Stats query
    query = os.environ.get("VLOGS_STATS_QUERY", "_time:30m | stats by (service) count()")

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

    rows = _extract_rows(payload)
    if not rows:
        pytest.fail(f"Unexpected stats_query JSON shape: {type(payload)} -> {payload}")

    nonzero_services: list[str] = []
    for row in rows:
        svc = _row_service(row)
        if not svc:
            continue
        if _row_count(row) > 0:
            nonzero_services.append(svc)

    assert nonzero_services, (
        "No service bucket with count>0 returned by VictoriaLogs stats_query.\n"
        f"base={base}\nquery={query}\n"
        f"seed_token={token}\n"
        f"sample_json={str(payload)[:800]}"
    )
