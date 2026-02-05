from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tests._helpers import find_monitoring_compose_file, run, which_ok

COMPOSE_FILE: Path = find_monitoring_compose_file()
SERVICE_NAME = "cadvisor"


def _compose_cmd() -> list[str] | None:
    if not which_ok("docker"):
        return None
    r = run(["docker", "compose", "version"])
    if r.returncode == 0:
        return ["docker", "compose"]
    return None


def _compose_config_json(compose_file: Path) -> dict:
    """
    Read rendered compose config as JSON to avoid requiring PyYAML in the pre-commit pytest env.
    """
    cmd = _compose_cmd()
    if not cmd:
        pytest.skip("docker compose plugin not available")

    if not compose_file.exists():
        pytest.skip(f"compose file not found: {compose_file}")

    # Provide safe placeholders for variable expansion (no secrets).
    env = {
        "COMPOSE_PROJECT_NAME": "homelab-home-prod-mon",
        "TZ": "Europe/Berlin",
        "GRAFANA_ADMIN_USER": "admin",
        "GRAFANA_ADMIN_PASSWORD": "changeme",
        "ALERT_EMAIL_TO": "devnull@example.invalid",
        "ALERT_SMTP_AUTH_USERNAME": "devnull@example.invalid",
        "ALERT_SMTP_AUTH_PASSWORD": "changeme",
        "ALERT_SMTP_FROM": "alerts@example.invalid",
        "ALERT_SMTP_SMARTHOST": "smtp.example.invalid:587",
        "ALERT_SMTP_REQUIRE_TLS": "true",
    }

    res = run([*cmd, "-f", str(compose_file), "config", "--format", "json"], env=env)
    if res.returncode != 0:
        # Some older compose builds may not support --format json.
        pytest.skip(
            f"docker compose config --format json not supported or config failed.\nstderr:\n{res.stderr}"
        )

    try:
        data = json.loads(res.stdout)
    except Exception as e:
        pytest.skip(f"Failed to parse compose config JSON: {e}")

    if not isinstance(data, dict):
        pytest.skip(f"Unexpected compose config JSON type: {type(data)}")

    return data


def _image_present_locally(image: str) -> bool:
    res = run(["docker", "image", "inspect", image])
    return res.returncode == 0


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
    if not which_ok("docker"):
        pytest.skip("docker not available in PATH")

    cfg = _compose_config_json(COMPOSE_FILE)
    image, flags = _extract_image_and_flags(cfg)

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
