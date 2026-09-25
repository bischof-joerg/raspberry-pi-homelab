# tests/guards/test_32_alertmanager_renderer_container.py
#
# Runs render-config.sh inside the real, pinned image with the runtime flags read from the
# compose file (user, group_add, cap_drop, security_opt, read_only, network none), then checks
# the result with amtool and stat. This is the class of failure the first R1.1 deploy hit
# (apk exit 10 under user 0:65534 without CAP_CHOWN) - caught before merge instead of on the Pi.
#
# /out is a tmpfs inside the container, so nothing root-owned is left on the host. The only
# host mounts are the template and the script, both read-only and required to exist. Skips without Docker, except in
# CI, where a missing Docker is a failure.

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "stacks/monitoring/compose/docker-compose.yml"
ALERTMANAGER_DIR = REPO_ROOT / "stacks/monitoring/alertmanager"
RENDER_SCRIPT = ALERTMANAGER_DIR / "render-config.sh"
TEMPLATE = ALERTMANAGER_DIR / "alertmanager.yml.tmpl"
RENDERER = "alertmanager-config-render"

pytestmark = pytest.mark.xfail(strict=True, reason="R1.2: contract pinned before the fix (F36, F8)")

FIXTURE_ENV = {
    "ALERT_EMAIL_ENABLED": "1",
    "ALERT_EMAIL_TO": "ops+alerts@example.org",
    "ALERT_SMTP_FROM": 'Homelab "Pi" <pi@example.org>',
    "ALERT_SMTP_SMARTHOST": "smtp.example.org:587",
    "ALERT_SMTP_AUTH_USERNAME": "domain\\user: #1",
    "ALERT_SMTP_AUTH_PASSWORD": "p\"a\\s:s #w'o$rd & *y",
    "ALERT_SMTP_REQUIRE_TLS": "true",
}


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    return subprocess.run(["docker", "info"], capture_output=True, check=False).returncode == 0


def _renderer() -> dict:
    return yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))["services"][RENDERER]


def _docker_run_args(service: dict) -> list[str]:
    args = ["docker", "run", "--rm", "--network", "none", "--tmpfs", "/out"]
    if service.get("user"):
        args += ["--user", str(service["user"])]
    for group in service.get("group_add", []):
        args += ["--group-add", str(group)]
    for cap in service.get("cap_drop", []):
        args += ["--cap-drop", str(cap)]
    for opt in service.get("security_opt", []):
        args += ["--security-opt", str(opt)]
    if service.get("read_only"):
        args.append("--read-only")
    for key, value in FIXTURE_ENV.items():
        args += ["-e", f"{key}={value}"]
    # --mount, not -v: -v silently creates a root-owned directory for a missing source file
    # inside the repository; --mount refuses instead.
    for source in (TEMPLATE, RENDER_SCRIPT):
        args += ["--mount", f"type=bind,source={source},target=/in/{source.name},readonly"]
    args += [
        "--entrypoint",
        "/bin/sh",
        str(service["image"]),
        "-c",
        # Same script as the compose entrypoint, then prove the result inside the container.
        f"sh /in/{RENDER_SCRIPT.name}"
        " && amtool check-config /out/alertmanager.yml >/dev/null"
        " && stat -c '%a %u:%g' /out/alertmanager.yml",
    ]
    return args


def test_renderer_succeeds_in_pinned_image_with_compose_flags() -> None:
    if not _docker_available():
        if os.environ.get("CI") == "true":
            pytest.fail("❌ Docker is required in CI for the renderer container test.")
        pytest.skip("Docker not available; the renderer container test runs in CI.")

    missing = [str(p) for p in (TEMPLATE, RENDER_SCRIPT) if not p.is_file()]
    assert not missing, f"❌ Missing renderer inputs: {missing} (F36).\nFix: extract the renderer."

    service = _renderer()
    proc = subprocess.run(
        _docker_run_args(service), text=True, capture_output=True, check=False, timeout=180
    )
    assert proc.returncode == 0, (
        f"❌ {RENDERER} failed in {service.get('image')} with the compose flags "
        f"(exit {proc.returncode}):\n{proc.stderr[-2000:]}\n"
        "Fix: the renderer must run offline, read-only and without capabilities."
    )
    last = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
    assert last == "640 0:65534", (
        f"❌ Rendered config is {last!r}, expected '640 0:65534' (F26).\n"
        "Fix: chgrp 65534 and chmod 0640 before the rename."
    )
