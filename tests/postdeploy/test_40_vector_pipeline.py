"""
Postdeploy: Vector docker_logs -> VictoriaLogs.

Emits a short burst of logfmt lines from a temporary container and asserts:
- the marker arrives in VictoriaLogs
- Vector extracted structured fields (e2e_token, e2e_seq) from logfmt
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

# Must match Vector's docker source include_labels / normalize labels.
STACK = os.getenv("VECTORE2E_STACK", "homelab-home-prod-mon")
SERVICE = os.getenv("VECTORE2E_SERVICE", "vector-e2e")

# Keep noise low by default.
BURST_LINES = int(os.getenv("VECTORE2E_BURST_LINES", "30"))
BUSYBOX_IMAGE = os.getenv("VECTORE2E_IMAGE", "busybox:1.36")

QUERY_WINDOW = os.getenv("VECTORE2E_QUERY_WINDOW", "10m")
TIMEOUT_S = float(os.getenv("VECTORE2E_TIMEOUT_S", "30"))
POLL_S = float(os.getenv("VECTORE2E_POLL_S", "0.8"))


def _run(args: list[str], *, timeout: float | None = None) -> str:
    res = subprocess.run(
        args,
        check=True,
        capture_output=True,  # Ruff UP022
        text=True,
        timeout=timeout,
    )
    # Keep stderr available for debugging if needed.
    return (res.stdout or "") + (("\n" + res.stderr) if res.stderr else "")


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
        # logfmt for readability + parsability
        echo "event=vector_e2e token=$TOKEN seq=$i"
        i=$((i+1))
      done
    """.strip()

    _run(
        [
            "docker",
            "run",
            "--rm",
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


def _wait_for_token(token: str) -> dict[str, Any]:
    deadline = time.monotonic() + TIMEOUT_S

    # Token is hex-only -> avoid special chars in LogSQL filters.
    q = f'{{stack="{STACK}",service="{SERVICE}"}} e2e_token:{token} _time:{QUERY_WINDOW} | limit 1'

    while time.monotonic() < deadline:
        rows = _query_vlogs(q)
        if rows:
            return rows[0]
        time.sleep(POLL_S)

    sample_q = (
        f'{{stack="{STACK}",service="{SERVICE}"}} '
        f"_time:{QUERY_WINDOW} | sort by (_time) desc | limit 8"
    )
    sample = _query_vlogs(sample_q)

    pytest.fail(
        "Vector → VictoriaLogs e2e marker not found via extracted fields.\n"
        f"- Expected: e2e_token={token} within _time:{QUERY_WINDOW}\n"
        f"- Query: {q}\n\n"
        "If sample rows contain 'token=<...>' in _msg but do NOT contain e2e_token/e2e_seq fields, "
        "then the Vector remap extraction isn't active (config not deployed/reloaded) or isn't matching.\n\n"
        f"Sample (last rows):\n{json.dumps(sample, indent=2)[:4000]}"
    )
    raise AssertionError("unreachable")


def test_vector_docker_logs_reach_victorialogs() -> None:
    # Fail fast if VictoriaLogs isn't reachable/authenticated.
    _ = _query_vlogs("* | limit 1")

    # Hex-only token to avoid LogSQL / tokenization edge-cases.
    token = uuid.uuid4().hex[:16]
    _emit_docker_logs(token)

    row = _wait_for_token(token)

    msg = str(row.get("_msg", ""))
    assert f"token={token}" in msg, f"token missing from _msg: {msg!r}"
    assert row.get("e2e_token") == token, f"e2e_token missing/mismatch: {row.get('e2e_token')!r}"
    assert row.get("e2e_seq") is not None, "e2e_seq missing"
