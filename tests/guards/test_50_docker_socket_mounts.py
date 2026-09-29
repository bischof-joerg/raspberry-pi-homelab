# tests/guards/test_50_docker_socket_mounts.py
#
# Finding F28: container-runtime sockets are mounted read-only.
#
# This is least privilege, NOT isolation: `:ro` protects the socket inode, not the API behind
# it, so any container that can connect to the Docker socket is still host-root equivalent
# (F30, .claude/rules/compose-stacks.md).
#
# F30 (R1.10): only the services in SOCKET_ALLOWLIST mount a runtime socket. socket-proxy is the
# one intended holder (ADR-0012); every other consumer reads the Docker API through it.

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "stacks/monitoring/compose/docker-compose.yml"
SOCKETS = ("/var/run/docker.sock", "/run/docker.sock", "/run/containerd/containerd.sock")
# Each entry names why the service may hold a runtime socket.
SOCKET_ALLOWLIST: dict[str, str] = {
    "socket-proxy": "the filtering proxy itself (ADR-0012, F30)",
    "cadvisor": "containerd image store requires the containerd socket (F57, R1.11 reverted)",
}


def _socket_mounts() -> list[tuple[str, str]]:
    services = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))["services"]
    return [
        (name, str(volume))
        for name, service in services.items()
        for volume in service.get("volumes", [])
        if str(volume).split(":")[0] in SOCKETS
    ]


def test_socket_mounts_exist_where_expected() -> None:
    # Guards the guard: if the mounts moved or changed syntax, the checks below pass vacuously,
    # and an allowlist entry for a service without a socket keeps a stale exception alive.
    services = {name for name, _ in _socket_mounts()}
    assert services == SOCKET_ALLOWLIST.keys(), (
        f"❌ Socket mounts found in {sorted(services)}, allowlisted: {sorted(SOCKET_ALLOWLIST)}.\n"
        "Fix: update SOCKET_ALLOWLIST if socket access was removed on purpose (F30/F57)."
    )


def test_only_allowlisted_services_mount_runtime_sockets() -> None:
    offenders = sorted({name for name, _ in _socket_mounts()} - SOCKET_ALLOWLIST.keys())
    assert not offenders, (
        f"❌ Services mount a runtime socket without an allowlist entry: {offenders} (F30).\n"
        "Fix: read the Docker API through socket-proxy (http://socket-proxy:2375) instead."
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
