import os
import subprocess
import time
import uuid

import pytest

POSTDEPLOY_ON_TARGET = os.getenv("POSTDEPLOY_ON_TARGET") == "1"

# VictoriaLogs on host (as in your stack)
VLOGS_BASE_URL = os.getenv("VLOGS_BASE_URL", "http://127.0.0.1:9428")
VLOGS_QUERY_URL = f"{VLOGS_BASE_URL}/select/logsql/query"

# Tuning knobs (defaults optimized for speed while keeping reliability)
VECTORE2E_TIMEOUT_S = int(os.getenv("VECTOR_E2E_TIMEOUT_S", "60"))
VECTORE2E_QUERY_WINDOW = os.getenv("VECTOR_E2E_QUERY_WINDOW", "10m")  # LogsQL time filter
VECTORE2E_POLL_INTERVAL_S = float(os.getenv("VECTOR_E2E_POLL_INTERVAL_S", "1.0"))
VECTORE2E_POLL_MAX_INTERVAL_S = float(os.getenv("VECTOR_E2E_POLL_MAX_INTERVAL_S", "5.0"))

# Emitter behavior (fast + avoids docker_logs attach race)
VECTORE2E_START_DELAY_S = float(os.getenv("VECTOR_E2E_START_DELAY_S", "1.0"))
VECTORE2E_BURST_LINES = int(os.getenv("VECTOR_E2E_BURST_LINES", "200"))
VECTORE2E_TAIL_HOLD_S = float(os.getenv("VECTOR_E2E_TAIL_HOLD_S", "2.0"))


def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _docker_container_id_by_name_exact(name: str) -> str:
    cp = _run(["docker", "ps", "-q", "--filter", f"name=^{name}$"], check=False)
    return (cp.stdout or "").strip()


def _pick_vector_container() -> str:
    # Prefer your naming convention
    candidates = [
        "homelab-home-prod-mon-vector-1",
        "vector",
    ]
    for c in candidates:
        if _docker_container_id_by_name_exact(c):
            return c

    # last resort: first container containing "vector"
    cp = _run(["docker", "ps", "--format", "{{.Names}}", "--filter", "name=vector"], check=False)
    names = (cp.stdout or "").strip().splitlines()
    if names:
        return names[0]

    raise AssertionError("Could not find a running Vector container (name match failed).")


def _vlogs_query(query: str) -> str:
    # VictoriaLogs expects POST form field `query=...`
    cp = _run(["curl", "-fsS", VLOGS_QUERY_URL, "-d", f"query={query}"], check=True)
    return cp.stdout or ""


def _emit_burst_docker_logs(token: str) -> None:
    """
    Emit many log lines quickly, but keep the container alive briefly.
    This avoids the attach race with docker_logs and reduces test runtime.
    """
    cname = f"vector-test-{token[:12]}"

    # Notes:
    # - initial sleep ensures Vector is already watching docker events
    # - burst prints many lines so even if a few are missed, we still ingest the token
    # - tail hold gives docker logs + vector enough time to read + flush
    script = (
        f"sleep {VECTORE2E_START_DELAY_S}; "
        f"i=1; while [ $i -le {VECTORE2E_BURST_LINES} ]; do "
        f"echo '{token} i='\"$i\"; "
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
            "busybox:1.36",
            "sh",
            "-lc",
            script,
        ],
        check=True,
    )


def _wait_for_token_in_vlogs(token: str, timeout_s: int) -> None:
    """
    Wait until the token appears in VictoriaLogs.

    LogsQL idiom: `_time:<window> <filters> | limit N`
    We search in _msg using an exact phrase match to reduce false positives.
    """
    deadline = time.time() + timeout_s
    last = ""

    # Keep LogsQL simple (avoid AND). Token has no spaces, so quoting is safe.
    q = f'_time:{VECTORE2E_QUERY_WINDOW} _msg:"{token}" | limit 5'

    interval = VECTORE2E_POLL_INTERVAL_S
    while time.time() < deadline:
        try:
            last = _vlogs_query(q)
            if token in last:
                return
        except subprocess.CalledProcessError as e:
            last = (e.stdout or "").strip() or str(e)

        time.sleep(interval)
        interval = min(interval * 1.5, VECTORE2E_POLL_MAX_INTERVAL_S)

    # Failure diagnostics (short but actionable)
    diag = []
    diag.append(f"VictoriaLogs query used: {q!r}")
    diag.append(f"Last response (first 1200 chars): {(last or '')[:1200]!r}")

    try:
        any_recent = _vlogs_query(f"_time:{VECTORE2E_QUERY_WINDOW} | limit 1")
        diag.append(f"Recent logs sample (first 800 chars): {any_recent[:800]!r}")
    except Exception as e:  # noqa: BLE001
        diag.append(f"Could not query recent logs sample: {e!r}")

    raise AssertionError("Did not find token in VictoriaLogs.\n" + "\n".join(diag))


@pytest.mark.postdeploy
@pytest.mark.skipif(
    not POSTDEPLOY_ON_TARGET, reason="POSTDEPLOY_ON_TARGET=1 required (run on target host)."
)
def test_vector_end_to_end_dockerlogs_to_victorialogs():
    vector_name = _pick_vector_container()

    # 1) Validate Vector config inside container (fast sanity check)
    _run(
        ["docker", "exec", vector_name, "vector", "validate", "/etc/vector/vector.yaml"], check=True
    )

    # 2) Emit a burst of logs (fast, avoids attach race)
    token = f"vector-e2e-{uuid.uuid4()}"
    _emit_burst_docker_logs(token)

    # 3) Verify it arrives in VictoriaLogs
    _wait_for_token_in_vlogs(token, timeout_s=VECTORE2E_TIMEOUT_S)
