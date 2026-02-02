from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from tests._helpers import find_monitoring_compose_file, run, which_ok


def compose_cmd() -> list[str] | None:
    r = run(["docker", "compose", "version"])
    if r.returncode == 0:
        return ["docker", "compose"]
    return None


ENV_DEFAULTS: dict[str, str] = {
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


def strip_env_file_blocks(compose_text: str) -> tuple[str, list[int]]:
    """
    Remove any `env_file:` blocks from a compose YAML text without needing a YAML parser.

    Handles:
      env_file:
        - /etc/raspberry-pi-homelab/monitoring.env
      env_file: /path/to/file

    Returns: (patched_text, removed_line_numbers_1based)
    """
    lines = compose_text.splitlines()
    out: list[str] = []
    removed: list[int] = []

    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^(\s*)env_file\s*:(.*)$", line)
        if not m:
            out.append(line)
            i += 1
            continue

        indent = m.group(1)
        removed.append(i + 1)

        # Case 1: inline value -> remove just this line
        rest = (m.group(2) or "").strip()
        i += 1
        if rest:
            continue

        # Case 2: block list below -> remove consecutive "- ..." lines with greater indent
        while i < len(lines):
            nxt = lines[i]
            # Stop when indentation is <= env_file indent (new key or outdent)
            if re.match(rf"^{re.escape(indent)}\S", nxt):
                break
            # Remove list items with more indent
            if re.match(rf"^{re.escape(indent)}\s+-\s+.+$", nxt):
                removed.append(i + 1)
                i += 1
                continue
            # Some empty/comment lines inside the block: remove them too to avoid dangling block
            if nxt.strip() == "" or nxt.lstrip().startswith("#"):
                removed.append(i + 1)
                i += 1
                continue
            # Any other content with greater indent: conservatively stop
            break

    return "\n".join(out) + "\n", removed


@pytest.mark.precommit
def test_compose_config(tmp_path: Path):
    compose_file = find_monitoring_compose_file()
    if not compose_file.exists():
        pytest.fail(f"Compose file missing: {compose_file}")

    if not which_ok("docker"):
        pytest.fail("docker is required for this repo's precommit suite")

    cmd = compose_cmd()
    if not cmd:
        pytest.fail("docker compose plugin not available")

    base_text = compose_file.read_text(encoding="utf-8")
    patched_text, removed_lines = strip_env_file_blocks(base_text)

    patched = tmp_path / "docker-compose.patched.no-env-file.yml"
    patched.write_text(patched_text, encoding="utf-8")

    env = os.environ.copy()
    for k, v in ENV_DEFAULTS.items():
        env.setdefault(k, v)

    # Prefer JSON output to avoid any YAML parsing in test env
    args = [*cmd, "-f", str(patched), "config", "--format", "json"]
    res = run(args, env=env)

    # Some compose versions may not support --format json; fall back to plain config
    if res.returncode != 0 and "unknown flag: --format" in (res.stderr or "").lower():
        res = run([*cmd, "-f", str(patched), "config"], env=env)

    assert res.returncode == 0, (
        "Compose config invalid.\n"
        f"compose_file={compose_file}\n"
        f"patched_compose={patched}\n"
        f"removed_env_file_lines={removed_lines}\n\n"
        f"stdout:\n{res.stdout}\n\nstderr:\n{res.stderr}"
    )
