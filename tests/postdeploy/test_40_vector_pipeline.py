"""
Postdeploy: Vector docker_logs -> VictoriaLogs (fast smoke).

This test emits a short burst of logfmt lines from an ephemeral container and asserts
that at least one line reaches VictoriaLogs within a small time budget.

Notes:
- Runs only on the target host (POSTDEPLOY_ON_TARGET=1).
- Uses Compose labels so Vector's docker_logs source (include_labels) picks up the emitter.
- Does NOT require any optional parsing/enrichment in Vector (no e2e_token field needed).
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from typing import Any

import pytest
import requests

pytestmark = pytest.mark.postdeploy

if os.getenv("POSTDEPLOY_ON_TARGET") != "1":
    pytest.skip(
        "postdeploy tests must run on target (set POSTDEPLOY_ON_TARGET=1)",
        allow_module_level=True,
    )

# VictoriaLogs query endpoint (host-reachable)
VLOGS_QUERY_URL = os.getenv("VLOGS_QUERY_URL", "http://127.0.0.1:9428/select/logsql/query")

# Must match Vector's docker source include_labels / normalize labels.
STACK = os.getenv("VECTORE2E_STACK", "homelab-home-prod-mon")
SERVICE = os.getenv("VECTORE2E_SERVICE", "vector-e2e")

# Keep runtime low by default, but overridable.
BURST_LINES = int(os.getenv("VECTORE2E_BURST_LINES", "6"))
QUERY_WINDOW = os.getenv("VECTORE2E_QUERY_WINDOW", "3m")
TIMEOUT_S = float(os.getenv("VECTORE2E_TIMEOUT_S", "15"))
POLL_S = float(os.getenv("VECTORE2E_POLL_S", "0.25"))

BUSYBOX_IMAGE = os.getenv("VECTORE2E_IMAGE", "busybox:1.36")


def _run(args: list[str], *, timeout: float | None = None) -> str:
    res = subprocess.run(
        args,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return res.stdout


def _emit_docker_logs(token: str) -> None:
    """
    Emit log lines from an ephemeral container.

    Labels are set so that:
    - Vector's docker source include_labels picks it up
    - normalize can derive stable stack/service labels
    """
    script = r"""
      i=1
      while [ "$i" -le "$LINES" ]; do
        # logfmt (readable, parsable if desired)
        echo "event=vector_e2e token=$TOKEN seq=$i"
        i=$((i+1))
      done
    """.strip()

    _run(
        [
            "docker",
            "run",
            "--rm",
            "--pull=never",
            "--label",
            f"com.docker.compose.project={STACK}",
            "--label",
            f"com.docker.compose.service={SERVICE}",
            "-e",
            f"TOKEN={token}",
            "-e",
            f"LINES={BURST_LINES}",
            BUSYBOX_IMAGE,
            "sh",
            "-lc",
            script,
        ],
        timeout=30,
    )


def _query_vlogs(session: requests.Session, query: str) -> list[dict[str, Any]]:
    resp = session.post(VLOGS_QUERY_URL, data={"query": query}, timeout=6)
    resp.raise_for_status()

    rows: list[dict[str, Any]] = []
    for line in resp.text.splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _wait_for_token(session: requests.Session, token: str) -> dict[str, Any]:
    deadline = time.monotonic() + TIMEOUT_S
    needle = f"token={token}"

    q = f'{{stack="{STACK}",service="{SERVICE}"}} _time:{QUERY_WINDOW} "{needle}" | limit 1'

    while time.monotonic() < deadline:
        rows = _query_vlogs(session, q)
        if rows:
            return rows[0]
        time.sleep(POLL_S)

    # Diagnostics: show a small sample from the expected stream.
    sample_q = f'{{stack="{STACK}",service="{SERVICE}"}} _time:{QUERY_WINDOW} | sort by (_time) desc | limit 5'
    sample = _query_vlogs(session, sample_q)

    pytest.fail(
        "Vector → VictoriaLogs e2e marker not found.\n"
        f"- Expected: {needle!r} within _time:{QUERY_WINDOW}\n"
        f"- Query: {q}\n\n"
        f"Sample (last 5 rows):\n{json.dumps(sample, indent=2)[:4000]}"
    )
    raise AssertionError("unreachable")


def test_vector_docker_logs_reach_victorialogs() -> None:
    with requests.Session() as s:
        # Fail fast if VictoriaLogs isn't reachable/authenticated.
        _ = _query_vlogs(s, "* | limit 1")

        token = uuid.uuid4().hex[:16]  # hex-only to avoid LogSQL edge-cases
        _emit_docker_logs(token)
        row = _wait_for_token(s, token)

    msg = str(row.get("_msg", ""))
    assert f"token={token}" in msg, f"token missing from _msg: {msg!r}"
    assert row.get("stack") == STACK, f"unexpected stack: {row.get('stack')!r}"
    assert row.get("service") == SERVICE, f"unexpected service: {row.get('service')!r}"
