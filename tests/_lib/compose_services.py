"""Service classes of the monitoring compose stack, derived from the compose file (F7).

A hand-kept list of expected services drifts from the compose file: until R1.16,
tests/postdeploy/test_10_containers.py checked 7 of 10 long-running services and missed a stopped
VictoriaLogs after a reboot. Guards and postdeploy derive the list from here instead.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import yaml

# Services that run once per deploy and exit. Every other service is long-running and must
# restart after a reboot (`restart: unless-stopped`). tests/guards/test_10 checks that each entry
# exists and does not restart, so a renamed service cannot silently change class.
ONE_SHOT_SERVICES = frozenset({"alertmanager-config-render"})


def load_services(compose_file: Path) -> dict:
    """The raw `services` mapping; no interpolation needed for names and restart policies."""
    data = yaml.safe_load(compose_file.read_text(encoding="utf-8")) or {}
    return data.get("services") or {}


def long_running_services(services: Iterable[str]) -> list[str]:
    """All service names except the one-shot ones, sorted."""
    return sorted(set(services) - ONE_SHOT_SERVICES)
