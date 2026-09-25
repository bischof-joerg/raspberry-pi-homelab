# tests/postdeploy/test_25_cadvisor_metrics.py
import os
import subprocess

import pytest

from tests._helpers import run, which_ok

MONITORING_NETWORK = "monitoring"
PROJECT = os.environ.get("COMPOSE_PROJECT_NAME", "homelab-home-prod-mon")
CADVISOR_CONTAINER = f"{PROJECT}-cadvisor-1"
# Same pinned helper image as tests/postdeploy/test_20_health_endpoints.py.
CURL_IMAGE = "curlimages/curl:8.11.1"
# Long-running services whose container metrics must carry the Docker container name.
NAMED_SERVICES = ("alertmanager", "grafana", "victoriametrics")


@pytest.mark.postdeploy
def test_cadvisor_metrics_endpoint_responds(retry):
    if not which_ok("docker"):
        pytest.skip("docker not available")

    cmd = [
        "docker",
        "run",
        "--rm",
        "--network",
        MONITORING_NETWORK,
        "alpine:3.20",
        "sh",
        "-lc",
        "apk add --no-cache curl >/dev/null && curl -fsSI --max-time 3 http://cadvisor:8080/metrics | grep -qi '^content-type: '",
    ]

    last = None

    def _check():
        nonlocal last
        last = run(cmd)
        assert last.returncode == 0, (
            "cadvisor /metrics not responding from within monitoring network.\n"
            f"last rc={last.returncode}\nstdout:\n{last.stdout}\nstderr:\n{last.stderr}"
        )

    retry(_check, timeout_s=20, interval_s=0.5)


def _cadvisor_metrics() -> str:
    """GET /metrics inside cadvisor's network namespace - live output of the running process."""
    cp = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            f"container:{CADVISOR_CONTAINER}",
            CURL_IMAGE,
            "-fsS",
            "--max-time",
            "10",
            "http://127.0.0.1:8080/metrics",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert cp.returncode == 0, f"❌ GET cadvisor /metrics failed (rc={cp.returncode}):\n{cp.stderr}"
    return cp.stdout


@pytest.mark.postdeploy
def test_cadvisor_exports_named_container_metrics(retry):
    """
    F28: the `name` label comes from cadvisor's Docker integration (the Docker API over the
    socket). /metrics keeps answering without it, so the endpoint test above cannot tell.
    Queried live from cadvisor, not from VictoriaMetrics, whose lookback would still return
    series scraped before a cadvisor restart.
    """
    if not which_ok("docker"):
        pytest.skip("docker not available")

    missing: list[str] = []

    def _check():
        nonlocal missing
        body = _cadvisor_metrics()
        missing = [
            svc
            for svc in NAMED_SERVICES
            if not any(
                line.startswith("container_memory_usage_bytes{")
                and f'name="{PROJECT}-{svc}-1"' in line
                for line in body.splitlines()
            )
        ]
        assert not missing, (
            f"❌ cadvisor exports no container_memory_usage_bytes with name= for {missing} (F28).\n"
            "Its Docker integration is not working - check `docker logs "
            f"{CADVISOR_CONTAINER}` and the /var/run/docker.sock mount."
        )

    # cadvisor needs a housekeeping cycle (30-60 s) after a restart to discover containers.
    retry(_check, timeout_s=120, interval_s=5)


@pytest.mark.postdeploy
def test_cadvisor_docker_socket_is_read_only():
    """F28: the Docker socket is mounted read-only (least privilege; see F30 on its limits)."""
    if not which_ok("docker"):
        pytest.skip("docker not available")

    fmt = '{{range .Mounts}}{{if eq .Destination "/var/run/docker.sock"}}{{.RW}}{{end}}{{end}}'
    res = run(["docker", "inspect", CADVISOR_CONTAINER, "--format", fmt])
    assert res.returncode == 0, f"❌ docker inspect {CADVISOR_CONTAINER} failed:\n{res.stderr}"
    rw = res.stdout.strip()
    assert rw == "false", (
        f"❌ {CADVISOR_CONTAINER}: /var/run/docker.sock mount RW={rw!r}, expected 'false' (F28).\n"
        "Fix: mount it with :ro in stacks/monitoring/compose/docker-compose.yml and redeploy."
    )
