"""
Postdeploy: Vector docker_logs -> VictoriaLogs (end-to-end smoke).

This test:
- starts a short-lived BusyBox container that prints logfmt lines
- labels it so Vector's docker_logs source includes it
- asserts the emitted token shows up in VictoriaLogs within a small time window

Notes:
- This test intentionally does *not* require Vector to parse logfmt into structured fields.
  It only verifies that docker logs make it through the Vector -> VictoriaLogs pipeline.
- Container name must NOT match Vector's docker_logs.exclude_containers pattern (e.g. `vector-test-*`),
  otherwise Vector will intentionally ignore it.
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

VLOGS_QUERY_URL = os.getenv("VLOGS_QUERY_URL", "http://127.0.0.1:9428/select/logsql/query")

# Must match Vector's docker_logs.include_labels + your normalization rules.
STACK = os.getenv("VECTORE2E_STACK", "homelab-home-prod-mon")
SERVICE = os.getenv("VECTORE2E_SERVICE", "vector-e2e")

# Keep noise low by default.
BURST_LINES = int(os.getenv("VECTORE2E_BURST_LINES", "8"))
TAIL_SLEEP_S = float(os.getenv("VECTORE2E_TAIL_SLEEP_S", "1.0"))
BUSYBOX_IMAGE = os.getenv("VECTORE2E_IMAGE", "busybox:1.36")

# Query / retry tuning.
QUERY_WINDOW = os.getenv("VECTORE2E_QUERY_WINDOW", "10m")
TIMEOUT_S = float(os.getenv("VECTORE2E_TIMEOUT_S", "25"))
POLL_S = float(os.getenv("VECTORE2E_POLL_S", "0.8"))


def _run(args: list[str], *, timeout: float | None = None) -> str:
    res = subprocess.run(
        args,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return res.stdout


def _query_vlogs(query: str) -> list[dict[str, Any]]:
    resp = requests.post(VLOGS_QUERY_URL, data={"query": query}, timeout=6)
    resp.raise_for_status()

    rows: list[dict[str, Any]] = []
    for line in resp.text.splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _emit_docker_logs(token: str) -> None:
    # Avoid container names matching Vector's exclude_containers pattern (e.g. vector-test-*).
    cname = f"vectore2e-{token}"

    # Print logfmt; keep container alive briefly so docker_logs reliably observes it.
    script = (
        "i=1; "
        'while [ "$i" -le "$LINES" ]; do '
        '  echo "event=vector_e2e token=$TOKEN seq=$i"; '
        "  i=$((i+1)); "
        "done; "
        'sleep "$TAIL" '
    )

    _run(
        [
            "docker",
            "run",
            "--rm",
            "--name",
            cname,
            "--label",
            f"com.docker.compose.project={STACK}",
            "--label",
            f"com.docker.compose.service={SERVICE}",
            "-e",
            f"TOKEN={token}",
            "-e",
            f"LINES={BURST_LINES}",
            "-e",
            f"TAIL={TAIL_SLEEP_S}",
            BUSYBOX_IMAGE,
            "sh",
            "-lc",
            script,
        ],
        timeout=40,
    )


def _wait_for_token(token: str) -> dict[str, Any]:
    deadline = time.monotonic() + TIMEOUT_S

    # Stream filter + phrase filter:
    # - {stack="...",service="..."} selects the stream labels written by Vector
    # - "<token>" searches inside _msg (full-text phrase match)
    q = f'{{stack="{STACK}",service="{SERVICE}"}} _time:{QUERY_WINDOW} "{token}" | limit 1'

    while time.monotonic() < deadline:
        rows = _query_vlogs(q)
        if rows:
            return rows[0]
        time.sleep(POLL_S)

    # Diagnostics: show most recent rows from the expected stream.
    sample_q = (
        f'{{stack="{STACK}",service="{SERVICE}"}} '
        f"_time:{QUERY_WINDOW} | sort by (_time) desc | limit 8"
    )
    sample = _query_vlogs(sample_q)

    pytest.fail(
        "Vector → VictoriaLogs e2e marker not found.\n"
        f"- Expected token {token!r} within _time:{QUERY_WINDOW}\n"
        f"- Query: {q}\n\n"
        "If `sample` is empty, check Vector docker_logs.include_labels/exclude_containers and whether Vector is running.\n"
        "If `sample` contains the token but your custom fields are missing, that is expected unless you added a remap step.\n\n"
        f"Sample (last rows):\n{json.dumps(sample, indent=2)[:4000]}"
    )
    raise AssertionError("unreachable")


def test_vector_docker_logs_reach_victorialogs() -> None:
    # Fail fast if VictoriaLogs isn't reachable/authenticated.
    _ = _query_vlogs("* | limit 1")

    # Hex-only token to avoid LogSQL tokenization edge-cases.
    token = uuid.uuid4().hex[:16]

    _emit_docker_logs(token)
    row = _wait_for_token(token)

    msg = str(row.get("_msg", ""))
    assert token in msg, f"token missing from _msg: {msg!r}"
