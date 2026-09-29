# tests/postdeploy/test_26_docker_socket_proxy.py
#
# Finding F30 (R1.10): vector reads the Docker API only through socket-proxy
# (wollomatic/socket-proxy, ADR-0012). These checks prove on the Pi that the proxy filters:
# an allowed GET works, a write (POST) and a file read (archive) are refused, and vector
# neither mounts the socket nor carries the Docker group any more.
#
# The probes run in the proxy's own network namespace (client 127.0.0.1, allowed by -allowfrom),
# so a refusal comes from the method/path allowlist, not from the client check. The proxy
# answers 405 for a method and 403 for a path it does not allow, and logs each refusal at WARN
# as "blocked request" (cmd/socket-proxy/handlehttprequest.go, read 2026-09-29).

from __future__ import annotations

import os
import subprocess

import pytest

from tests._helpers import run, which_ok

PROJECT = os.environ.get("COMPOSE_PROJECT_NAME", "homelab-home-prod-mon")
PROXY_CONTAINER = f"{PROJECT}-socket-proxy-1"
VECTOR_CONTAINER = f"{PROJECT}-vector-1"
# Same pinned helper image as tests/postdeploy/test_25_cadvisor_metrics.py.
CURL_IMAGE = "curlimages/curl:8.11.1"
DOCKER_SOCKET = "/var/run/docker.sock"


@pytest.fixture(autouse=True)
def _need_docker() -> None:
    if not which_ok("docker"):
        pytest.skip("docker not available")


def _status(method: str, path: str) -> str:
    """HTTP status of `method path` sent to the proxy from inside its network namespace."""
    cp = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            f"container:{PROXY_CONTAINER}",
            CURL_IMAGE,
            "-s",
            "-o",
            "/dev/null",
            "-w",
            "%{http_code}",
            "--max-time",
            "5",
            "-X",
            method,
            f"http://127.0.0.1:2375{path}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert cp.returncode == 0, f"❌ curl against {PROXY_CONTAINER} failed:\n{cp.stderr}"
    return cp.stdout.strip()


def _inspect(container: str, fmt: str) -> str:
    res = run(["docker", "inspect", container, "--format", fmt])
    assert res.returncode == 0, f"❌ docker inspect {container} failed:\n{res.stderr}"
    return res.stdout.strip()


def test_proxy_is_healthy(retry) -> None:
    def _check() -> None:
        health = _inspect(PROXY_CONTAINER, "{{.State.Health.Status}}")
        assert health == "healthy", (
            f"❌ {PROXY_CONTAINER} health is {health!r} (F30).\n"
            f"Check `docker logs {PROXY_CONTAINER}`."
        )

    retry(_check, timeout_s=60, interval_s=3)


def test_proxy_allows_listing_containers() -> None:
    status = _status("GET", "/containers/json")
    assert status == "200", (
        f"❌ GET /containers/json through socket-proxy returned {status} (F30).\n"
        "Fix: check -allowGET and -allowfrom (127.0.0.1/32) in the compose command."
    )


def test_proxy_refuses_writes() -> None:
    status = _status("POST", "/containers/create")
    assert status == "405", (
        f"❌ POST /containers/create through socket-proxy returned {status}, expected 405 (F30).\n"
        "Fix: the proxy must allow GET only; remove any -allowPOST."
    )


def test_proxy_refuses_file_reads_from_containers() -> None:
    status = _status("GET", f"/containers/{PROXY_CONTAINER}/archive?path=/")
    assert status == "403", (
        f"❌ GET /containers/<id>/archive through socket-proxy returned {status}, expected 403.\n"
        "Fix: narrow -allowGET to events, containers/json, containers/<id>/json and /logs."
    )


def test_proxy_blocked_no_consumer_request() -> None:
    # Only the probes above (client 127.0.0.1) may be refused. A refusal for any other client
    # means a consumer needs an endpoint the allowlist lacks: its data is silently missing.
    res = run(["docker", "logs", PROXY_CONTAINER])
    assert res.returncode == 0, f"❌ docker logs {PROXY_CONTAINER} failed:\n{res.stderr}"
    blocked = [
        line
        for line in (res.stdout + res.stderr).splitlines()
        if "blocked request" in line and "client=127.0.0.1:" not in line
    ]
    assert not blocked, (
        "❌ socket-proxy refused requests from its consumers (F30):\n"
        + "\n".join(f" - {line}" for line in blocked[:10])
        + "\nFix: add exactly the refused GET path to -allowGET (ADR-0012), never another method."
    )


def test_vector_has_no_docker_socket_mount() -> None:
    fmt = "{{range .Mounts}}{{.Destination}} {{end}}"
    mounts = _inspect(VECTOR_CONTAINER, fmt).split()
    assert DOCKER_SOCKET not in mounts, (
        f"❌ {VECTOR_CONTAINER} still mounts {DOCKER_SOCKET} (F30).\n"
        "Fix: remove the mount from stacks/monitoring/compose/docker-compose.yml and redeploy."
    )


def test_vector_is_not_in_the_docker_group() -> None:
    docker_gid = str(os.stat(DOCKER_SOCKET).st_gid)
    groups = _inspect(VECTOR_CONTAINER, "{{range .HostConfig.GroupAdd}}{{.}} {{end}}").split()
    assert docker_gid not in groups, (
        f"❌ {VECTOR_CONTAINER} has the Docker group {docker_gid} in GroupAdd {groups} (F30).\n"
        "Fix: remove ${DOCKER_GID} from vector's group_add and redeploy."
    )
