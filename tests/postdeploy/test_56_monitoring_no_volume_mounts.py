# tests/postdeploy/test_56_monitoring_no_volume_mounts.py
#
# Postdeploy guardrail: ensure monitoring containers do not use Docker volumes.
# We enforce "bind mounts only" for deterministic host storage layout and backups.
#
# Container selection:
# 1) Prefer Docker Compose label: com.docker.compose.project=<COMPOSE_PROJECT_NAME>
# 2) Fallback: container name prefix (default "homelab-home-prod-mon-")

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass

import pytest


def _on_target() -> bool:
    return os.environ.get("POSTDEPLOY_ON_TARGET", "") == "1"


def _docker() -> str:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("docker CLI not found in PATH")
    return docker


def _run(cmd: list[str], timeout: int = 25) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(
            f"Command failed ({p.returncode}): {' '.join(cmd)}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
        )
    return p.stdout


def _compose_project() -> str:
    # Prefer explicit env (deploy.sh usually sources /etc/.../monitoring.env)
    # Fallback to your default project name.
    return os.environ.get("COMPOSE_PROJECT_NAME", "homelab-home-prod-mon")


def _container_prefix(project: str) -> str:
    # Allow override, but default to "<project>-".
    # If COMPOSE_PROJECT_NAME isn't available, the project default above yields "homelab-home-prod-mon-".
    return os.environ.get("MONITORING_CONTAINER_PREFIX", f"{project}-")


def _list_container_ids_by_label(docker: str, project: str) -> list[str]:
    out = _run(
        [docker, "ps", "-aq", "--filter", f"label=com.docker.compose.project={project}"]
    ).strip()
    return [line.strip() for line in out.splitlines() if line.strip()]


def _list_container_ids_by_name_filter(docker: str, prefix: str) -> list[str]:
    # docker ps name filter supports regex-like matching on the container name.
    # Using ^prefix gives a deterministic match.
    out = _run([docker, "ps", "-aq", "--filter", f"name=^{prefix}"]).strip()
    return [line.strip() for line in out.splitlines() if line.strip()]


def _list_container_ids_by_inspecting_all(docker: str, prefix: str) -> list[str]:
    # Last-resort fallback: list all containers and filter by inspected .Name startswith prefix.
    all_ids_out = _run([docker, "ps", "-aq"]).strip()
    all_ids = [line.strip() for line in all_ids_out.splitlines() if line.strip()]
    matched: list[str] = []

    for cid in all_ids:
        inspect_raw = _run([docker, "inspect", cid])
        data = json.loads(inspect_raw)
        if not data or not isinstance(data, list):
            continue
        name = (data[0].get("Name") or "").lstrip("/")
        if name.startswith(prefix):
            matched.append(cid)

    return matched


@dataclass(frozen=True)
class OffendingMount:
    container: str
    container_id: str
    name: str | None
    source: str | None
    destination: str | None
    driver: str | None


@pytest.mark.postdeploy
def test_monitoring_containers_have_no_volume_mounts() -> None:
    if not _on_target():
        pytest.skip(
            "POSTDEPLOY_ON_TARGET is not set; this test is intended to run on the Pi target."
        )

    docker = _docker()
    project = _compose_project()
    prefix = _container_prefix(project)

    # 1) Label-based selection (preferred)
    ids = _list_container_ids_by_label(docker, project)
    selection = f"label com.docker.compose.project={project}"

    # 2) Fallback: name prefix filter
    if not ids:
        ids = _list_container_ids_by_name_filter(docker, prefix)
        selection = f"name prefix {prefix!r} (docker ps filter)"

    # 3) Last resort: inspect all container names
    if not ids:
        ids = _list_container_ids_by_inspecting_all(docker, prefix)
        selection = f"name prefix {prefix!r} (inspect-all fallback)"

    if not ids:
        raise AssertionError(
            "No monitoring containers found.\n"
            f"Tried selection methods:\n"
            f"- label com.docker.compose.project={project}\n"
            f"- name prefix {prefix!r}\n"
            "Hints:\n"
            "- Ensure the monitoring stack is up.\n"
            "- Ensure COMPOSE_PROJECT_NAME (or MONITORING_CONTAINER_PREFIX) matches the deployed stack.\n"
        )

    offenders: list[OffendingMount] = []

    for cid in ids:
        inspect_raw = _run([docker, "inspect", cid])
        data = json.loads(inspect_raw)
        if not data or not isinstance(data, list):
            raise RuntimeError(f"Unexpected docker inspect output for {cid}")

        info = data[0]
        name = (info.get("Name") or "").lstrip("/") or cid
        mounts = info.get("Mounts", []) or []

        for m in mounts:
            if m.get("Type") == "volume":
                offenders.append(
                    OffendingMount(
                        container=name,
                        container_id=cid[:12],
                        name=m.get("Name"),
                        source=m.get("Source"),
                        destination=m.get("Destination"),
                        driver=m.get("Driver"),
                    )
                )

    if offenders:
        lines = [
            "Found Docker volume mounts in monitoring containers (expected bind mounts only).",
            f"Container selection used: {selection}",
            "",
        ]
        for o in offenders:
            lines.append(
                f"- {o.container} ({o.container_id}): "
                f"volume={o.name!r} driver={o.driver!r} source={o.source!r} dest={o.destination!r}"
            )
        lines.append("")
        lines.append(
            "Hint: check the compose file for named/anonymous volumes and recreate affected containers "
            "(docker compose up -d --force-recreate <service>)."
        )
        raise AssertionError("\n".join(lines))
