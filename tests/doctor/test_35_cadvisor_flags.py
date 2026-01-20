from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from tests._helpers import REPO_ROOT, run, which_ok


COMPOSE_FILE = REPO_ROOT / "monitoring" / "compose" / "docker-compose.yml"
SERVICE_NAME = "cadvisor"

def _image_present_locally(image: str) -> bool:
    res = run(["docker", "image", "inspect", image])
    return res.returncode == 0

def _load_compose(path: Path) -> dict:
    if not path.exists():
        raise AssertionError(f"Compose file missing: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise AssertionError(f"Compose file is not a YAML mapping: {path}")
    return data


def _extract_image_and_flags(compose: dict) -> tuple[str, list[str]]:
    services = compose.get("services") or {}
    if not isinstance(services, dict):
        raise AssertionError("compose: 'services' must be a mapping")

    svc = services.get(SERVICE_NAME) or {}
    if not isinstance(svc, dict):
        raise AssertionError(f"compose: services.{SERVICE_NAME} must be a mapping")

    image = svc.get("image")
    if not image or not isinstance(image, str):
        raise AssertionError(f"{SERVICE_NAME}: missing/invalid services.{SERVICE_NAME}.image in {COMPOSE_FILE}")

    cmd = svc.get("command") or []
    if isinstance(cmd, str):
        # Prefer list form in compose; string form is ambiguous (shell quoting).
        # We do a conservative split here for flags only.
        cmd_tokens = cmd.split()
    elif isinstance(cmd, list):
        cmd_tokens = [str(x) for x in cmd]
    else:
        raise AssertionError(f"{SERVICE_NAME}: services.{SERVICE_NAME}.command must be string or list")

    # Convert tokens into flag names (without leading dashes and without "=...").
    flags: list[str] = []
    for token in cmd_tokens:
        if token.startswith("--") and len(token) > 2:
            flags.append(token[2:].split("=", 1)[0])
        elif token.startswith("-") and len(token) > 1:
            # cAdvisor uses single-dash long flags (e.g. -docker_only) in help output.
            flags.append(token[1:].split("=", 1)[0])

    # De-duplicate while preserving order.
    seen: set[str] = set()
    uniq: list[str] = []
    for f in flags:
        if f not in seen:
            seen.add(f)
            uniq.append(f)

    return image, uniq


def _cadvisor_help(image: str) -> str:
    # Use the image itself as the authoritative source for supported flags.
    # We merge stdout+stderr because some images print usage to stderr.
    res = run(["docker", "run", "--rm", image, "--help"])
    out = (res.stdout or "") + "\n" + (res.stderr or "")
    if res.returncode != 0:
        raise AssertionError(
            f"Failed to run '{image} --help' (rc={res.returncode}).\n"
            f"STDOUT:\n{res.stdout}\n\nSTDERR:\n{res.stderr}"
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


@pytest.mark.doctor
def test_cadvisor_flags_are_supported_by_pinned_image():
    if not which_ok("docker"):
        pytest.skip("docker not available in PATH")

    compose = _load_compose(COMPOSE_FILE)
    image, flags = _extract_image_and_flags(compose)

    # If no flags are configured, that's acceptable; nothing to validate.
    if not flags:
        pytest.skip("No cadvisor command flags configured")

    if not _image_present_locally(image):
        pytest.skip(f"cadvisor image not present locally: {image} (run: docker pull {image})")

    help_text = _cadvisor_help(image)

    supported = _supported_flags_from_help(help_text)

    unknown = [f for f in flags if f not in supported]
    assert not unknown, (
        f"cadvisor: unsupported flags for image '{image}': {unknown}\n"
        f"Reproduce: docker run --rm {image} --help\n"
        f"Compose: {COMPOSE_FILE}"
    )
