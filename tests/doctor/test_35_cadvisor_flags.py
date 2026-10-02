from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from tests._helpers import find_monitoring_compose_file, run, which_ok
from tests._lib.compose import render_compose

COMPOSE_FILE: Path = find_monitoring_compose_file()
# Placeholders for every variable the compose file expands (no secrets), as the guards use.
ENV_EXAMPLE = COMPOSE_FILE.parent / ".env.example"
SERVICE_NAME = "cadvisor"


def _require_docker() -> None:
    # F47: skip only on a machine without Docker outside CI; in CI a missing Docker is a defect.
    if which_ok("docker"):
        return
    if os.environ.get("CI") == "true":
        pytest.fail("❌ Docker is required in CI for the cadvisor flags check (F47).")
    pytest.skip("Docker not available; the cadvisor flags check runs in CI.")


def _compose_config() -> dict:
    try:
        return render_compose(COMPOSE_FILE, env_file=ENV_EXAMPLE)
    except RuntimeError as exc:
        pytest.fail(f"❌ {exc}\nFix: the monitoring stack must render with {ENV_EXAMPLE} (F47).")


def _pull(image: str) -> None:
    # F47: pull the pinned image instead of skipping when it is missing, as tests/guards/test_32
    # does; after a Renovate bump the new tag is never present locally.
    res = run(["docker", "pull", "-q", image])
    if res.returncode != 0:
        pytest.fail(
            f"❌ docker pull {image} failed (rc={res.returncode}):\n{res.stderr}\n"
            f"Fix: check the pin in {COMPOSE_FILE} and the network (F47)."
        )


def _cadvisor_help(image: str) -> str:
    res = run(["docker", "run", "--rm", image, "--help"])
    out = (res.stdout or "") + "\n" + (res.stderr or "")
    if res.returncode != 0:
        raise AssertionError(
            f"Failed to run '{image} --help' (rc={res.returncode}).\nSTDOUT:\n{res.stdout}\n\nSTDERR:\n{res.stderr}"
        )
    return out


def _supported_flags_from_help(help_text: str) -> set[str]:
    # Matches help output lines like:
    #   -housekeeping_interval duration
    #   -docker_only
    supported: set[str] = set()
    for line in help_text.splitlines():
        line = line.strip()
        m = re.match(r"^-([A-Za-z0-9_]+)\b", line)
        if m:
            supported.add(m.group(1))
    return supported


def _extract_image_and_flags(cfg: dict) -> tuple[str, list[str]]:
    services = cfg.get("services") or {}
    if not isinstance(services, dict):
        raise AssertionError("compose config: 'services' must be a mapping")

    svc = services.get(SERVICE_NAME) or {}
    if not isinstance(svc, dict):
        raise AssertionError(f"compose config: services.{SERVICE_NAME} must be a mapping")

    image = svc.get("image")
    if not image or not isinstance(image, str):
        raise AssertionError(f"{SERVICE_NAME}: missing/invalid image")

    cmd = svc.get("command") or []
    if isinstance(cmd, str):
        cmd_tokens = cmd.split()
    elif isinstance(cmd, list):
        cmd_tokens = [str(x) for x in cmd]
    else:
        raise AssertionError(f"{SERVICE_NAME}: command must be string or list")

    flags: list[str] = []
    for token in cmd_tokens:
        if token.startswith("--") and len(token) > 2:
            flags.append(token[2:].split("=", 1)[0])
        elif token.startswith("-") and len(token) > 1:
            # cAdvisor help uses single-dash long flags
            flags.append(token[1:].split("=", 1)[0])

    # De-duplicate while preserving order.
    seen: set[str] = set()
    uniq: list[str] = []
    for f in flags:
        if f not in seen:
            seen.add(f)
            uniq.append(f)

    return image, uniq


@pytest.mark.doctor
def test_cadvisor_flags_are_supported_by_pinned_image():
    _require_docker()
    image, flags = _extract_image_and_flags(_compose_config())
    assert flags, f"❌ {SERVICE_NAME} has no command flags in {COMPOSE_FILE}; nothing to check."

    _pull(image)
    help_text = _cadvisor_help(image)
    supported = _supported_flags_from_help(help_text)

    unknown = [f for f in flags if f not in supported]
    assert not unknown, (
        f"cadvisor: unsupported flags for image '{image}': {unknown}\n"
        f"Reproduce: docker run --rm {image} --help\n"
        f"Compose: {COMPOSE_FILE}"
    )
