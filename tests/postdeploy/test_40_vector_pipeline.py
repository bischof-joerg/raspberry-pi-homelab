import os
import subprocess
import time
import uuid

POSTDEPLOY_ON_TARGET = os.getenv("POSTDEPLOY_ON_TARGET") == "1"

# Adjust if you expose VictoriaLogs differently on the target
VLOGS_BASE_URL = os.getenv("VLOGS_BASE_URL", "http://127.0.0.1:9428")
VLOGS_QUERY_URL = f"{VLOGS_BASE_URL}/select/logsql/query"


def _run(
    cmd: list[str], *, check: bool = True, capture: bool = True, text: bool = True
) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        check=check,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
        text=text,
    )


def _docker_container_id_by_name(name: str) -> str:
    # exact match on name
    cp = _run(["docker", "ps", "-q", "--filter", f"name=^{name}$"])
    cid = (cp.stdout or "").strip()
    return cid


def _docker_any_container_id_by_name_fragment(fragment: str) -> str:
    # fallback: try partial match
    cp = _run(["docker", "ps", "-q", "--filter", f"name={fragment}"])
    cid = (cp.stdout or "").strip().splitlines()
    return cid[0] if cid else ""


def _pick_vector_container() -> str:
    # Prefer your naming convention. Adjust if your actual service name differs.
    # Examples seen in your project: homelab-home-prod-mon-<service>-1
    candidates = [
        "homelab-home-prod-mon-vector-1",
        "homelab-home-prod-mon-vector-agent-1",
        "vector",
    ]
    for c in candidates:
        cid = _docker_container_id_by_name(c)
        if cid:
            return c

    # last resort: any container name containing "vector"
    cid = _docker_any_container_id_by_name_fragment("vector")
    if cid:
        cp = _run(["docker", "ps", "--format", "{{.Names}}", "--filter", "name=vector"])
        names = (cp.stdout or "").strip().splitlines()
        if names:
            return names[0]

    raise AssertionError("Could not find a running Vector container (name match failed).")


def _vlogs_query(query: str) -> str:
    # VictoriaLogs expects POST form field `query=...`
    cp = _run(["curl", "-fsS", VLOGS_QUERY_URL, "-d", f"query={query}"])
    return cp.stdout or ""


def _emit_unique_docker_log(token: str) -> None:
    # json-file is typical; Vector docker_logs source reads from Docker socket / json-file logs.
    # We keep it simple: start a short-lived container that prints the token.
    _run(
        [
            "docker",
            "run",
            "--rm",
            "--name",
            f"vector-test-{token[:12]}",
            "busybox:1.36",
            "sh",
            "-lc",
            f"echo {token}",
        ]
    )


def _wait_for_token_in_vlogs(token: str, timeout_s: int = 45) -> None:
    # LogsQL simplest: just search by token (word match in _msg)
    # We also bound time window to reduce noise.
    deadline = time.time() + timeout_s
    last = ""
    while time.time() < deadline:
        # last 5 minutes should be plenty; adjust if your ingest is slower
        q = f"{token} AND _time:5m | limit 5"
        try:
            last = _vlogs_query(q)
            if token in last:
                return
        except subprocess.CalledProcessError as e:
            last = e.stdout or str(e)

        time.sleep(2)

    raise AssertionError(
        f"Did not find token in VictoriaLogs within {timeout_s}s.\nLast response:\n{last}"
    )


# If you already use pytest markers, add/align accordingly in your repo.
import pytest  # noqa: E402


@pytest.mark.postdeploy
@pytest.mark.skipif(
    not POSTDEPLOY_ON_TARGET, reason="POSTDEPLOY_ON_TARGET=1 required (run on target host)."
)
def test_vector_end_to_end_dockerlogs_to_victorialogs():
    vector_name = _pick_vector_container()

    # 1) validate config inside container (fast sanity check)
    # Works if the image contains the `vector` binary (typical for Vector images).
    _run(["docker", "exec", vector_name, "vector", "validate", "/etc/vector/vector.yaml"])

    # 2) emit a unique log token
    token = f"vector-e2e-{uuid.uuid4()}"
    _emit_unique_docker_log(token)

    # 3) verify it arrives in VictoriaLogs
    _wait_for_token_in_vlogs(token, timeout_s=45)
