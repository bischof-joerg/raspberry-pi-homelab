import os
import subprocess
import time
import uuid

import pytest

POSTDEPLOY_ON_TARGET = os.getenv("POSTDEPLOY_ON_TARGET") == "1"

# VictoriaLogs on host (as in your stack)
VLOGS_BASE_URL = os.getenv("VLOGS_BASE_URL", "http://127.0.0.1:9428")
VLOGS_QUERY_URL = f"{VLOGS_BASE_URL}/select/logsql/query"

# Tuning knobs (keep defaults conservative)
VECTORE2E_TIMEOUT_S = int(os.getenv("VECTOR_E2E_TIMEOUT_S", "120"))
VECTORE2E_QUERY_WINDOW = os.getenv("VECTOR_E2E_QUERY_WINDOW", "15m")  # LogSQL window
VECTORE2E_EMIT_SECONDS = int(os.getenv("VECTOR_E2E_EMIT_SECONDS", "15"))  # how long emitter runs
VECTORE2E_EMIT_INTERVAL = float(os.getenv("VECTOR_E2E_EMIT_INTERVAL", "1.0"))


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


def _emit_reliable_docker_logs(token: str) -> str:
    """
    Emit logs in a container that stays alive long enough for Vector's docker_logs source to attach.
    Returns the emitter container name.
    """
    cname = f"vector-test-{token[:12]}"
    # Busybox prints the token multiple times with sleeps.
    # We intentionally keep it running for a bit.
    script = (
        "i=0; "
        f"while [ $i -lt {VECTORE2E_EMIT_SECONDS} ]; do "
        f"echo '{token} i='\"$i\"; "
        f"i=$((i+1)); "
        f"sleep {VECTORE2E_EMIT_INTERVAL}; "
        "done"
    )
    _run(
        ["docker", "run", "--rm", "--name", cname, "busybox:1.36", "sh", "-lc", script], check=True
    )
    return cname


def _wait_for_token_in_vlogs(token: str, timeout_s: int) -> None:
    """
    Wait until the token appears in VictoriaLogs.
    Uses a robust LogSQL query anchored on _msg.
    """
    deadline = time.time() + timeout_s
    last = ""

    # Prefer exact match on _msg to avoid surprises in LogSQL parsing.
    q = f'_msg:"{token}" AND _time:{VECTORE2E_QUERY_WINDOW} | limit 20'

    while time.time() < deadline:
        try:
            last = _vlogs_query(q)
            if token in last:
                return
        except subprocess.CalledProcessError as e:
            last = (e.stdout or "").strip() or str(e)

        time.sleep(2)

    # Failure diagnostics (keep short but actionable)
    diag = []
    diag.append(f"VictoriaLogs query used: {q!r}")
    diag.append(f"Last response (first 800 chars): {(last or '')[:800]!r}")

    # Try to show whether VictoriaLogs has any recent logs at all (helps distinguish ingest break vs token miss)
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

    # 1) Validate config inside Vector container (fast sanity check)
    # If your image ever becomes distroless without the CLI, this will fail clearly.
    _run(
        ["docker", "exec", vector_name, "vector", "validate", "/etc/vector/vector.yaml"], check=True
    )

    # 2) Emit a token multiple times in a long-enough container (avoids docker_logs attach race)
    token = f"vector-e2e-{uuid.uuid4()}"
    _emit_reliable_docker_logs(token)

    # 3) Verify it arrives in VictoriaLogs (more generous timeout, robust query)
    _wait_for_token_in_vlogs(token, timeout_s=VECTORE2E_TIMEOUT_S)
