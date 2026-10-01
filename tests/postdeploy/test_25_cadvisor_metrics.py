# tests/postdeploy/test_25_cadvisor_metrics.py
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from tests._helpers import run, which_ok

MONITORING_NETWORK = "monitoring"
PROJECT = os.environ.get("COMPOSE_PROJECT_NAME", "homelab-home-prod-mon")
CADVISOR_CONTAINER = f"{PROJECT}-cadvisor-1"
# Same pinned helper image as tests/postdeploy/test_20_health_endpoints.py.
CURL_IMAGE = "curlimages/curl:8.11.1"
# Long-running services whose container metrics must carry the Docker container name.
NAMED_SERVICES = ("alertmanager", "grafana", "victoriametrics")
# Families that vmalert rules (stacks/monitoring/vmalert/rules/basic-alerts.yml) and the Docker
# overview dashboard use. All present for NAMED_SERVICES while privileged (measured on the Pi,
# 2026-09-29); F46 step 4 must keep every one of them.
REQUIRED_FAMILIES = (
    "container_last_seen",
    "container_cpu_usage_seconds_total",
    "container_memory_working_set_bytes",
    "container_memory_rss",
    "container_memory_cache",
    "container_network_receive_bytes_total",
    "container_network_transmit_bytes_total",
)


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
    F46 step 4: without `privileged`, single families can vanish (e.g. network counters read
    from /proc/<pid>/net of other UIDs), so every family in REQUIRED_FAMILIES is checked.
    Queried live from cadvisor, not from VictoriaMetrics, whose lookback would still return
    series scraped before a cadvisor restart.
    """
    if not which_ok("docker"):
        pytest.skip("docker not available")

    missing: list[str] = []

    def _check():
        nonlocal missing
        lines = _cadvisor_metrics().splitlines()
        missing = [
            f"{svc}/{family}"
            for svc in NAMED_SERVICES
            for family in REQUIRED_FAMILIES
            if not any(
                line.startswith(f"{family}{{") and f'name="{PROJECT}-{svc}-1"' in line
                for line in lines
            )
        ]
        assert not missing, (
            f"❌ cadvisor exports these families without a name= series: {missing} (F28, F46).\n"
            f"Check `docker logs {CADVISOR_CONTAINER}`. All missing: the Docker integration "
            "(/var/run/docker.sock mount). Only some: a privilege gap since privileged was dropped "
            "- add the smallest cap_add set (ADR-0011)."
        )

    # cadvisor needs a housekeeping cycle (30-60 s) after a restart to discover containers.
    retry(_check, timeout_s=120, interval_s=5)


@pytest.mark.postdeploy
def test_cadvisor_container_is_not_privileged():
    """F46 step 4: the running cadvisor container is not privileged (ADR-0011)."""
    if not which_ok("docker"):
        pytest.skip("docker not available")

    res = run(["docker", "inspect", CADVISOR_CONTAINER, "--format", "{{.HostConfig.Privileged}}"])
    assert res.returncode == 0, f"❌ docker inspect {CADVISOR_CONTAINER} failed:\n{res.stderr}"
    privileged = res.stdout.strip()
    assert privileged == "false", (
        f"❌ {CADVISOR_CONTAINER}: HostConfig.Privileged={privileged!r}, expected 'false' (F46).\n"
        "Fix: drop `privileged: true` from stacks/monitoring/compose/docker-compose.yml and "
        "redeploy so the container is recreated."
    )


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


# F57: cap_drop [ALL] plus the measured set (ADR-0011, amendment 2026-10-01). Bit 1 = DAC_OVERRIDE.
EXPECTED_CAP_ADD = {"DAC_OVERRIDE"}
EXPECTED_CAP_EFF = 1 << 1


def _caps(raw: str) -> set[str]:
    # Docker may store a capability with or without the CAP_ prefix.
    return {cap.upper().removeprefix("CAP_") for cap in json.loads(raw) or []}


@pytest.mark.postdeploy
def test_cadvisor_runs_with_measured_capabilities():
    """F57: cadvisor runs with cap_drop ALL and only DAC_OVERRIDE, in config and in the process."""
    if not which_ok("docker"):
        pytest.skip("docker not available")

    fmt = "{{json .HostConfig.CapDrop}}|{{json .HostConfig.CapAdd}}|{{.State.Pid}}"
    res = run(["docker", "inspect", CADVISOR_CONTAINER, "--format", fmt])
    assert res.returncode == 0, f"❌ docker inspect {CADVISOR_CONTAINER} failed:\n{res.stderr}"
    cap_drop, cap_add, pid = res.stdout.strip().split("|")
    assert _caps(cap_drop) == {"ALL"} and _caps(cap_add) == EXPECTED_CAP_ADD, (
        f"❌ {CADVISOR_CONTAINER}: CapDrop={cap_drop}, CapAdd={cap_add}; expected CapDrop "
        f"[ALL] and CapAdd {sorted(EXPECTED_CAP_ADD)} (F57).\n"
        "Fix: redeploy so the container is recreated from stacks/monitoring/compose/"
        "docker-compose.yml."
    )

    status = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
    match = re.search(r"^CapEff:\s*([0-9a-f]+)$", status, flags=re.MULTILINE)
    assert match, f"❌ /proc/{pid}/status has no CapEff line:\n{status}"
    cap_eff = int(match.group(1), 16)
    assert cap_eff == EXPECTED_CAP_EFF, (
        f"❌ cadvisor (pid {pid}) has CapEff {cap_eff:#x}, expected {EXPECTED_CAP_EFF:#x} (F57).\n"
        "Fix: compare `grep Cap /proc/<pid>/status` with cap_drop/cap_add in the compose file."
    )


@pytest.mark.postdeploy
def test_cadvisor_runs_without_new_privileges():
    """F57: cadvisor sets no-new-privileges, in config and in the process (ADR-0011)."""
    if not which_ok("docker"):
        pytest.skip("docker not available")

    fmt = "{{json .HostConfig.SecurityOpt}}|{{.State.Pid}}"
    res = run(["docker", "inspect", CADVISOR_CONTAINER, "--format", fmt])
    assert res.returncode == 0, f"❌ docker inspect {CADVISOR_CONTAINER} failed:\n{res.stderr}"
    security_opt, pid = res.stdout.strip().split("|")
    assert any(
        opt.startswith("no-new-privileges") and not opt.endswith("false")
        for opt in json.loads(security_opt) or []
    ), (
        f"❌ {CADVISOR_CONTAINER}: SecurityOpt={security_opt}, expected no-new-privileges (F57).\n"
        "Fix: redeploy so the container is recreated from stacks/monitoring/compose/"
        "docker-compose.yml."
    )

    status = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
    match = re.search(r"^NoNewPrivs:\s*(\d)$", status, flags=re.MULTILINE)
    assert match and match.group(1) == "1", (
        f"❌ cadvisor (pid {pid}) has NoNewPrivs={match and match.group(1)!r}, expected '1' (F57).\n"
        "Fix: check `grep NoNewPrivs /proc/<pid>/status` and security_opt in the compose file."
    )
