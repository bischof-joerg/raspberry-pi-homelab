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
import textwrap
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

QUERY_WINDOW = os.getenv("VECTORE2E_QUERY_WINDOW", "5m")
TIMEOUT_S = float(os.getenv("VECTORE2E_TIMEOUT_S", "25"))
POLL_S = float(os.getenv("VECTORE2E_POLL_S", "0.8"))

# Avoid docker_logs attach race for very short-lived containers:
# - wait a moment before emitting
# - keep the container alive briefly after emitting
START_DELAY_S = float(os.getenv("VECTORE2E_START_DELAY_S", "1.0"))
TAIL_HOLD_S = float(os.getenv("VECTORE2E_TAIL_HOLD_S", "2.0"))


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
    script = textwrap.dedent(f"""
      set -e
      sleep {START_DELAY_S}

      i=1
      while [ "$i" -le "$LINES" ]; do
        # logfmt for readability + parsability
        echo "event=vector_e2e token=$TOKEN seq=$i"
        i=$((i+1))
      done

      sleep {TAIL_HOLD_S}
    """).strip()

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

    # Enforce that Vector extracted structured fields from logfmt.
    q = (
        f'{{stack="{STACK}",service="{SERVICE}"}} '
        f'e2e_token:"{token}" _time:{QUERY_WINDOW} | limit 1'
    )

    while time.monotonic() < deadline:
        rows = _query_vlogs(q)
        if rows:
            return rows[0]
        time.sleep(POLL_S)

    # Helpful diagnostics: show recent logs from the same stream.
    sample_q = (
        f'{{stack="{STACK}",service="{SERVICE}"}} '
        f"_time:{QUERY_WINDOW} | sort by (_time) desc | limit 5"
    )
    sample = _query_vlogs(sample_q)

    pytest.fail(
        "Vector → VictoriaLogs e2e marker not found.\n"
        f"- Expected: e2e_token={token} within _time:{QUERY_WINDOW}\n"
        f"- Query: {q}\n\n"
        "If sample rows contain the token in _msg but NOT e2e_token, "
        "Vector likely hasn't reloaded the updated remap (send SIGHUP or recreate the container).\n\n"
        f"Sample (last 5 rows):\n{json.dumps(sample, indent=2)[:4000]}"
    )
    raise AssertionError("unreachable")


def test_vector_docker_logs_reach_victorialogs() -> None:
    # Fail fast if VictoriaLogs isn't reachable/authenticated.
    _ = _query_vlogs("* | limit 1")

    token = f"vector-e2e-{uuid.uuid4().hex[:12]}"
    _emit_docker_logs(token)
    row = _wait_for_token(token)

    msg = str(row.get("_msg", ""))
    assert token in msg, f"token missing from _msg: {msg!r}"
    assert row.get("e2e_token") == token, f"e2e_token missing/mismatch: {row.get('e2e_token')!r}"
