# tests/guards/test_52_docker_api_network.py
#
# R1.9 (F30/F57 preparation): scripts/network/bootstrap-networks.sh ensures the external network
# `docker-api`, created with `--internal`, for the Docker socket proxy and its consumers. An
# existing `docker-api` that is not internal must fail the bootstrap, not be used silently.
#
# Static on purpose: scripts under scripts/network/ are never executed off the Pi, not even with
# stubs (.claude/rules/shell-scripts.md). Behaviour is proven on the Pi by
# tests/postdeploy/test_35_network_and_ufw.py::test_docker_api_network_is_internal.

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts/network/bootstrap-networks.sh"


def _text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def _function(name: str) -> str:
    m = re.search(rf"^{name}\(\) \{{\n(.*?)^\}}", _text(), flags=re.MULTILINE | re.DOTALL)
    assert m, f"❌ {SCRIPT.name} has no function {name}().\nFix: restore it."
    return m.group(1)


def test_docker_api_network_name_defaults_to_docker_api() -> None:
    assert 'DOCKER_API_NETWORK="${DOCKER_API_NETWORK:-docker-api}"' in _text(), (
        f"❌ {SCRIPT.name} does not define DOCKER_API_NETWORK with default `docker-api`.\n"
        'Fix: add DOCKER_API_NETWORK="${DOCKER_API_NETWORK:-docker-api}" next to APPS_NETWORK.'
    )


def test_main_ensures_docker_api_as_internal() -> None:
    calls = [
        line.strip()
        for line in _function("main").splitlines()
        if line.strip().startswith('ensure_network "$DOCKER_API_NETWORK"')
    ]
    assert len(calls) == 1, (
        f"❌ main() must call ensure_network for $DOCKER_API_NETWORK exactly once, found {calls}.\n"
        "Fix: add the call after the apps network."
    )
    assert calls[0].split()[-1] == "internal", (
        f"❌ docker-api is not ensured as internal: {calls[0]!r}\n"
        "Fix: pass `internal` as the last argument of its ensure_network call."
    )


def test_create_network_passes_internal_flag() -> None:
    body = _function("create_network")
    assert re.search(r"args\+=\(--internal\)", body), (
        "❌ create_network() never adds --internal.\n"
        "Fix: append --internal to args when the internal argument is set."
    )


def test_validate_network_checks_internal() -> None:
    body = _function("validate_network")
    assert "{{.Internal}}" in body and "die" in body, (
        "❌ validate_network() does not compare the network's .Internal flag.\n"
        "Fix: read `docker network inspect --format '{{.Internal}}'` and die on a mismatch."
    )
