# tests/guards/test_50_docker_socket_mounts.py
#
# Finding F28: container-runtime sockets are mounted read-only.
#
# This is least privilege, NOT isolation: `:ro` protects the socket inode, not the API behind
# it, so any container that can connect to the Docker socket is still host-root equivalent
# (F30, .claude/rules/compose-stacks.md). This test only keeps a writable mount from coming
# back; removing socket access altogether is F30/F46.

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "stacks/monitoring/compose/docker-compose.yml"
SOCKETS = ("/var/run/docker.sock", "/run/docker.sock", "/run/containerd/containerd.sock")


def _socket_mounts() -> list[tuple[str, str]]:
    services = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))["services"]
    return [
        (name, str(volume))
        for name, service in services.items()
        for volume in service.get("volumes", [])
        if str(volume).split(":")[0] in SOCKETS
    ]


def test_socket_mounts_exist_where_expected() -> None:
    # Guards the guard: if the mounts moved or changed syntax, the check below would pass vacuously.
    services = {name for name, _ in _socket_mounts()}
    assert {"cadvisor", "vector"} <= services, (
        f"❌ Expected socket mounts in cadvisor and vector, found them in {sorted(services)}.\n"
        "Fix: update this test if socket access was removed on purpose (F30/F46)."
    )


def test_runtime_sockets_are_mounted_read_only() -> None:
    writable = [
        f"{name}: {volume}" for name, volume in _socket_mounts() if volume.split(":")[-1] != "ro"
    ]
    assert not writable, (
        "❌ Runtime sockets mounted without :ro (F28):\n"
        + "\n".join(f" - {w}" for w in writable)
        + "\nFix: append :ro. Note that :ro does not restrict the Docker API (F30)."
    )
