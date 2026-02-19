import os
import subprocess
import time
import uuid

import pytest
import requests

# --- Configuration via env (keep fast on Pi) ---------------------------------

# Vector container discovery
VECTOR_CONTAINER_CANDIDATES = os.getenv(
    "VECTOR_CONTAINER_CANDIDATES",
    "homelab-home-prod-mon-vector-1,homelab-home-prod-mon-vector-0,vector",
).split(",")

# VictoriaLogs query endpoint (host-reachable)
VLOGS_HOST = os.getenv("VLOGS_HOST", "http://127.0.0.1:9428")

# Total time budget for the end-to-end assertion
VECTORE2E_TIMEOUT_S = int(os.getenv("VECTOR_E2E_TIMEOUT_S", "60"))

# Emitter behavior (fast + avoids docker_logs attach race)
VECTORE2E_START_DELAY_S = float(os.getenv("VECTOR_E2E_START_DELAY_S", "1.0"))
VECTORE2E_BURST_LINES = int(os.getenv("VECTOR_E2E_BURST_LINES", "40"))
VECTORE2E_TAIL_HOLD_S = float(os.getenv("VECTOR_E2E_TAIL_HOLD_S", "2.0"))

# Retry logic: keep the worst-case upper bound similar to the old behavior
# (default 5 * 40 = 200 lines), but reduce noise in the common "first try succeeds" case.
VECTORE2E_MAX_ATTEMPTS = int(os.getenv("VECTOR_E2E_MAX_ATTEMPTS", "5"))


def _run(cmd: list[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )


def _pick_vector_container() -> str:
    for name in VECTOR_CONTAINER_CANDIDATES:
        name = name.strip()
        if not name:
            continue
        cp = _run(["docker", "inspect", name], check=False, capture=True)
        if cp.returncode == 0:
            return name
    raise RuntimeError(
        f"Could not find Vector container. Tried: {', '.join(VECTOR_CONTAINER_CANDIDATES)}"
    )


def _emit_burst_docker_logs(token: str, *, run_id: str, attempt: int) -> None:
    """
    Emit many log lines quickly, but keep the container alive briefly.
    This avoids the attach race with docker_logs and reduces test runtime.
    """
    cname = f"vector-test-vector-e2e-{run_id[:8]}-{attempt}"

    # Emit logfmt for readability + optional parsing in Vector.
    # Keep the token present as `marker=<token>` so the query stays trivial.
    script = (
        f"sleep {VECTORE2E_START_DELAY_S}; "
        f"i=1; while [ $i -le {VECTORE2E_BURST_LINES} ]; do "
        f"echo 'event=vector_e2e marker={token} run_id={run_id} attempt={attempt} seq='\"$i\"' total={VECTORE2E_BURST_LINES}'; "
        "i=$((i+1)); "
        "done; "
        f"sleep {VECTORE2E_TAIL_HOLD_S}"
    )

    _run(
        [
            "docker",
            "run",
            "--rm",
            "--name",
            cname,
            "--label",
            "com.docker.compose.project=homelab-home-prod-mon",
            "--label",
            "com.docker.compose.service=vector-e2e",
            "busybox:1.36",
            "sh",
            "-lc",
            script,
        ],
        check=True,
    )


def _vlogs_query(q: str) -> list[dict]:
    """
    Query VictoriaLogs LogSQL endpoint. Returns parsed JSON lines.
    """
    url = f"{VLOGS_HOST}/select/logsql/query"
    resp = requests.post(url, data={"query": q}, timeout=10)
    resp.raise_for_status()

    lines = []
    for line in resp.text.splitlines():
        line = line.strip()
        if not line:
            continue
        lines.append(resp.json() if line.startswith("{") and line.endswith("}") else None)

    # VictoriaLogs returns newline-delimited JSON objects (each line is JSON)
    out: list[dict] = []
    for line in resp.text.splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(requests.models.complexjson.loads(line))
    return out


def _wait_for_token_in_vlogs(token: str, timeout_s: int) -> None:
    """
    Poll VictoriaLogs for the marker token to show up in the last N minutes.
    """
    deadline = time.time() + timeout_s
    last_resp: list[dict] | None = None
    last_err: Exception | None = None

    # Search the last 10 minutes for marker presence
    q = f'_time:10m "{token}" | limit 5'

    while time.time() < deadline:
        try:
            last_resp = _vlogs_query(q)
            for obj in last_resp:
                msg = obj.get("_msg", "")
                if token in msg:
                    return
        except Exception as e:
            last_err = e

        time.sleep(2)

    diag = {
        "query": q,
        "last_error": repr(last_err) if last_err else None,
        "last_response_sample": last_resp[:2] if last_resp else None,
    }
    raise AssertionError(f"Did not find token in VictoriaLogs within {timeout_s}s. diag={diag}")


@pytest.mark.postdeploy
def test_vector_end_to_end_dockerlogs_to_victorialogs():
    vector_name = _pick_vector_container()

    # 1) Validate vector config inside container
    _run(["docker", "exec", vector_name, "vector", "validate", "/etc/vector/vector.yaml"])

    token = f"vector-e2e-{uuid.uuid4()}"
    run_id = token.removeprefix("vector-e2e-")

    # 2) Emit a burst of logs (retry a few times to reduce noise in the common case)
    last_err: AssertionError | None = None
    per_attempt_timeout_s = max(5, int(VECTORE2E_TIMEOUT_S / max(1, VECTORE2E_MAX_ATTEMPTS)))

    for attempt in range(1, VECTORE2E_MAX_ATTEMPTS + 1):
        _emit_burst_docker_logs(token, run_id=run_id, attempt=attempt)
        try:
            _wait_for_token_in_vlogs(token, timeout_s=per_attempt_timeout_s)
            return
        except AssertionError as e:
            last_err = e

    # 3) Verify it arrives in VictoriaLogs (final error)
    assert last_err is not None
    raise last_err
