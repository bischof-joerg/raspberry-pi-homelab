# tests/postdeploy/conftest.py
from __future__ import annotations

import os
import pathlib
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest


def _is_deploy_target() -> bool:
    # Heuristic: marker file exists on the Pi
    return pathlib.Path("/etc/raspberry-pi-homelab/.env").exists()


@pytest.fixture(autouse=True)
def _enforce_postdeploy_target(request: pytest.FixtureRequest) -> None:
    """Auto-skip postdeploy tests unless we're on the deploy target (or forced)."""
    if request.node.get_closest_marker("postdeploy") is None:
        return

    if os.environ.get("POSTDEPLOY_ON_TARGET") == "1":
        return

    if _is_deploy_target():
        return

    pytest.skip(
        "postdeploy tests must run on the deploy target (set POSTDEPLOY_ON_TARGET=1 to force)"
    )


@pytest.fixture
def http_get():
    """HTTP GET helper returning (status_code, body_text). Does not raise on HTTP status errors."""

    def _get(url: str, headers: dict | None = None, timeout: int = 8) -> tuple[int, str]:
        req = urllib.request.Request(url, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode()
            except Exception:
                body = ""
            return e.code, body
        except urllib.error.URLError as e:
            raise AssertionError(f"network error for {url}: {e}") from e

    return _get


@pytest.fixture
def retry():
    """Retry helper for eventual consistency (scrapes, rule loads)."""

    def _retry(assert_fn, timeout_s: int = 60, interval_s: float = 2.5) -> None:
        deadline = time.time() + timeout_s
        last_err: AssertionError | None = None
        while time.time() < deadline:
            try:
                assert_fn()
                return
            except AssertionError as e:
                last_err = e
                time.sleep(interval_s)
        raise last_err or AssertionError("retry timeout")

    return _retry


def _load_env_file_if_present(path: Path) -> None:
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except PermissionError:
        return
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


# Host-only secrets/config (GitOps policy): load if present on the Pi
env_path = Path("/etc/raspberry-pi-homelab/monitoring.env")
if env_path.exists() and os.access(env_path, os.R_OK):
    _load_env_file_if_present(env_path)
