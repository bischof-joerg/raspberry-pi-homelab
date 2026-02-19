#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
import requests


def _env_bool(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _base_url() -> str:
    return os.environ.get("VLOGS_BASE_URL", "http://127.0.0.1:9428").rstrip("/")


def _extract_rows(payload: Any) -> list[dict[str, Any]]:
    # VictoriaLogs stats_query returns a VM-like JSON response shape (vector result)
    try:
        data = payload.get("data", {})
        res = data.get("result", [])
        rows: list[dict[str, Any]] = []
        for item in res:
            # item likely has: {"metric": {...}, "value": [...]}
            metric = item.get("metric", {})
            value = item.get("value", [])
            rows.append({"metric": metric, "value": value})
        return rows
    except Exception:  # noqa: BLE001
        return []


def _vlogs_query(base: str, query: str, timeout_s: float = 5.0) -> str:
    r = requests.post(
        f"{base}/select/logsql/query",
        data={"query": query},
        timeout=timeout_s,
    )
    r.raise_for_status()
    return r.text or ""


def _wait_for_token_in_vlogs(base: str, token: str, timeout_s: float) -> None:
    """
    Poll VictoriaLogs until the token appears in _msg. Needed because ingestion can be async.
    """
    deadline = time.time() + timeout_s
    last = ""
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


def _emit_seed_log_token(base: str, token: str) -> None:
    """
    Seed VictoriaLogs with a single log line so that stats_query has something to aggregate
    even on a fresh / quiet system.

    We intentionally insert directly via VictoriaLogs' /insert/jsonline endpoint instead of
    going through docker->vector->victorialogs, because the end-to-end pipeline is already
    validated elsewhere and we want this test to be deterministic.

    VictoriaLogs supports /insert/jsonline with field mapping parameters. :contentReference[oaicite:1]{index=1}
    """
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    record = {
        "_time": now,
        "_msg": token,
        "service": "vlogs-seed",
        "level": "info",
        "stack": "homelab-home-prod-mon",
        "namespace": "prod",
        "host": os.environ.get("HOSTNAME", "rpi-hub"),
    }

    params = {
        "_time_field": "_time",
        "_msg_field": "_msg",
        "_stream_fields": "service,stack,namespace,host",
    }

    try:
        r = requests.post(
            f"{base}/insert/jsonline",
            params=params,
            data=json.dumps(record) + "\n",
            timeout=5.0,
        )
        r.raise_for_status()
        return
    except Exception:
        # Fallback to the docker->vector pipeline in case /insert/jsonline is disabled.
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--label",
                "com.docker.compose.project=homelab-home-prod-mon",
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


@pytest.mark.postdeploy
def test_victorialogs_stats_query_has_nonzero_service_bucket() -> None:
    """
    Robust smoke:
    - seeds at least one log line (so stats aren't empty on fresh systems)
    - waits until it is queryable in VictoriaLogs
    - calls /select/logsql/stats_query
    - parses JSON
    - asserts at least one bucket with non-empty service has count > 0

    Default: runs on target (POSTDEPLOY_ON_TARGET=1).
    Optional local: set VLOGS_BASE_URL to run against a reachable instance.
    """
    on_target = _env_bool("POSTDEPLOY_ON_TARGET")
    has_url_override = bool(os.environ.get("VLOGS_BASE_URL", "").strip())

    if not on_target and not has_url_override:
        pytest.skip("POSTDEPLOY_ON_TARGET!=1 and VLOGS_BASE_URL not set")

    base = _base_url()

    timeout_s = float(os.environ.get("VLOGS_TIMEOUT_SECONDS", "5"))
    seed_timeout_s = float(os.environ.get("VLOGS_SEED_TIMEOUT_SECONDS", "20"))

    # 0) Seed: generate one known log event that should get a service label
    token = f"vlogs-stats-seed-{uuid.uuid4()}"
    _emit_seed_log_token(base, token)
    _wait_for_token_in_vlogs(base, token, timeout_s=seed_timeout_s)

    # 1) Query stats
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

    # Assert at least one service bucket has count > 0 (and service label non-empty)
    # In VM-like response: value is ["<unix_ts>", "<count>"].
    for row in rows:
        metric = row.get("metric", {})
        val = row.get("value", [])
        service = (metric.get("service") or "").strip()
        if len(val) >= 2 and service:
            try:
                count = float(val[1])
            except Exception:  # noqa: BLE001
                continue
            if count > 0:
                return

    pytest.fail(f"No non-empty service bucket with count>0 found. rows={rows!r}")
