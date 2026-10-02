"""
F47: the cadvisor flags check in tests/doctor may skip only when Docker is missing outside CI.

The doctor test is loaded and called directly. Docker is simulated (`subprocess.run` and
`tests._helpers.which`), so no real docker command runs here.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

import tests._helpers as helpers

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCTOR_TEST = REPO_ROOT / "tests/doctor/test_35_cadvisor_flags.py"
IMAGE = "example.invalid/cadvisor:v0.0.1"
CONFIG = {"services": {"cadvisor": {"image": IMAGE, "command": ["--docker_only=true"]}}}


class FakeDocker:
    """Answers the docker commands the doctor test may run; refuses any other command."""

    def __init__(self, *, config_rc=0, image_present=True, pull_rc=0, help_flags=("docker_only",)):
        self.config_rc = config_rc
        self.image_present = image_present
        self.pull_rc = pull_rc
        self.help_flags = help_flags
        self.calls: list[list[str]] = []

    def __call__(self, cmd, *args, **kwargs):
        cmd = [str(part) for part in cmd]
        self.calls.append(cmd)

        def done(rc=0, out="", err=""):
            return subprocess.CompletedProcess(cmd, rc, out, err)

        if cmd[:3] == ["docker", "compose", "version"]:
            return done(out="Docker Compose version v2.0.0")
        if cmd[:2] == ["docker", "compose"] and "config" in cmd:
            if self.config_rc:
                return done(self.config_rc, err="simulated compose error")
            return done(out=json.dumps(CONFIG))
        if cmd[:3] == ["docker", "image", "inspect"]:
            return done(0) if self.image_present else done(1, err="No such image")
        if cmd[:2] == ["docker", "pull"]:
            if self.pull_rc:
                return done(self.pull_rc, err="simulated pull error")
            self.image_present = True
            return done(out=IMAGE)
        if cmd[:2] == ["docker", "run"] and "--help" in cmd:
            return done(out="".join(f"  -{flag}\n" for flag in self.help_flags))
        raise AssertionError(f"FakeDocker: unexpected command {cmd}")

    def pulled(self) -> bool:
        return any(call[:2] == ["docker", "pull"] for call in self.calls)


@pytest.fixture
def doctor(monkeypatch):
    def setup(*, docker=True, ci=False, **fake_kwargs):
        fake = FakeDocker(**fake_kwargs)
        monkeypatch.setattr(subprocess, "run", fake)
        monkeypatch.setattr(
            helpers, "which", lambda binary: f"/usr/bin/{binary}" if docker else None
        )
        if ci:
            monkeypatch.setenv("CI", "true")
        else:
            monkeypatch.delenv("CI", raising=False)
        spec = importlib.util.spec_from_file_location("doctor_cadvisor_flags", DOCTOR_TEST)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, fake

    return setup


def _outcome(module) -> tuple[str, str]:
    try:
        module.test_cadvisor_flags_are_supported_by_pinned_image()
    except pytest.skip.Exception as exc:
        return "skipped", str(exc)
    except pytest.fail.Exception as exc:
        return "failed", str(exc)
    return "passed", ""


@pytest.mark.xfail(strict=True, reason="R1.24: a compose config error is skipped (F47)")
def test_compose_config_error_fails(doctor) -> None:
    module, _ = doctor(config_rc=1)
    outcome, message = _outcome(module)
    assert outcome == "failed" and "simulated compose error" in message, (
        f"❌ A failing `docker compose config` gave {outcome!r}: {message}\n"
        "Fix: fail with compose's stderr; a broken compose file must not read as a skip (F47)."
    )


@pytest.mark.xfail(strict=True, reason="R1.24: a missing image is skipped, not pulled (F47)")
def test_missing_image_is_pulled(doctor) -> None:
    module, fake = doctor(image_present=False)
    outcome, message = _outcome(module)
    assert outcome == "passed" and fake.pulled(), (
        f"❌ With the image missing locally the check gave {outcome!r} ({message}), "
        f"pulled={fake.pulled()}.\n"
        "Fix: `docker pull` the pinned image before `--help`, as tests/guards/test_32 does (F47)."
    )


@pytest.mark.xfail(strict=True, reason="R1.24: a failed pull is skipped (F47)")
def test_failed_pull_fails(doctor) -> None:
    module, _ = doctor(image_present=False, pull_rc=1)
    outcome, message = _outcome(module)
    assert outcome == "failed" and "simulated pull error" in message, (
        f"❌ A failed `docker pull` gave {outcome!r}: {message}\n"
        "Fix: fail with the pull's stderr; an unreachable pinned image is a defect (F47)."
    )


@pytest.mark.xfail(strict=True, reason="R1.24: missing Docker is skipped in CI too (F47)")
def test_ci_without_docker_fails(doctor) -> None:
    module, _ = doctor(docker=False, ci=True)
    outcome, message = _outcome(module)
    assert outcome == "failed", (
        f"❌ In CI without Docker the check gave {outcome!r}: {message}\n"
        "Fix: fail when CI=true and Docker is missing, as tests/guards/test_32 does (F47)."
    )


def test_local_run_without_docker_skips(doctor) -> None:
    module, _ = doctor(docker=False)
    outcome, message = _outcome(module)
    assert outcome == "skipped", (
        f"❌ Outside CI without Docker the check gave {outcome!r}: {message}\n"
        "Fix: skip with a reason; a laptop without Docker is not a defect."
    )


def test_supported_flags_pass(doctor) -> None:
    module, _ = doctor()
    outcome, message = _outcome(module)
    assert outcome == "passed", f"❌ Supported flags gave {outcome!r}: {message}"


def test_unsupported_flag_fails(doctor) -> None:
    module, _ = doctor(help_flags=("housekeeping_interval",))
    with pytest.raises(AssertionError, match="docker_only"):
        _outcome(module)
