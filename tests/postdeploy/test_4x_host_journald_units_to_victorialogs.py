# tests/postdeploy/test_4x_host_journald_units_to_victorialogs.py
from __future__ import annotations

import json
import os
import shlex
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest

POSTDEPLOY_ENV = "POSTDEPLOY_ON_TARGET"
VLOG_QUERY_URL_ENV = "VICTORIALOGS_QUERY_URL"
VLOG_QUERY_URL_DEFAULT = "http://127.0.0.1:9428/select/logsql/query"

UNITS = (
    "docker.service",
    "containerd.service",
    "ufw.service",
    "systemd-udevd.service",
)


@dataclass(frozen=True)
class UnitCheck:
    unit: str
    lookback: str
    provoke: Callable[[], None]
    # Optional: if ufw is silent, we allow skip instead of fail.
    allow_skip_if_no_events: bool = False


def _require_postdeploy_on_target() -> None:
    if os.environ.get(POSTDEPLOY_ENV) != "1":
        pytest.skip(f"{POSTDEPLOY_ENV}=1 required (postdeploy on target)")


def _run(cmd: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _curl_victorialogs(query: str, *, timeout: int = 20) -> str:
    url = os.environ.get(VLOG_QUERY_URL_ENV, VLOG_QUERY_URL_DEFAULT)
    cp = _run(["curl", "-fsS", url, "-d", f"query={query}"], timeout=timeout)
    if cp.returncode != 0:
        raise AssertionError(
            "VictoriaLogs query failed\n"
            f"cmd={shlex.join(['curl', '-fsS', url, '-d', f'query={query}'])}\n"
            f"exit={cp.returncode}\n"
            f"stderr={cp.stderr.strip()}\n"
            f"stdout[:400]={cp.stdout[:400]!r}"
        )
    return cp.stdout


def _first_json_obj(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    first_line = text.splitlines()[0].strip()
    if not first_line:
        return None
    try:
        obj = json.loads(first_line)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Could not parse VictoriaLogs JSON: {e}. first_line={first_line!r}")  # noqa: B904
    if not isinstance(obj, dict):
        raise AssertionError(f"Expected JSON object, got {type(obj)}")
    return obj


def _quote_logsql_string(s: str) -> str:
    # LogsQL string literal in double quotes
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _query_one(unit: str, lookback: str) -> dict[str, Any] | None:
    # Prefer the normalized field you already see in VL: systemd_unit:"..."
    q = f"_time:{lookback} systemd_unit:{_quote_logsql_string(unit)} | limit 1"
    body = _curl_victorialogs(q, timeout=20)
    return _first_json_obj(body)


# --- Provoke helpers (safe-ish) -------------------------------------------------


def _provoke_docker() -> None:
    # Deterministic dockerd log: pulling an image emits "image pulled" (as you've already seen).
    # Keep it small.
    cp = _run(
        [
            "sh",
            "-lc",
            "docker pull -q hello-world:latest >/dev/null 2>&1 || docker pull hello-world:latest >/dev/null",
        ],
        timeout=300,
    )
    if cp.returncode != 0:
        raise AssertionError(
            f"Could not provoke docker.service logs via docker pull. stderr={cp.stderr.strip()!r}"
        )


def _provoke_containerd() -> None:
    # Starting/stopping a short-lived container usually produces containerd shim connect/disconnect logs.
    cp = _run(
        ["sh", "-lc", "docker run --rm hello-world:latest >/dev/null 2>&1 || true"], timeout=180
    )
    if cp.returncode != 0:
        # hello-world may exit non-zero on some setups; we only care that docker attempted it.
        pass


def _provoke_udevd() -> None:
    # You already validated this yields udev activity in journald.
    cp = _run(["sh", "-lc", "sudo udevadm trigger && sudo udevadm settle"], timeout=120)
    if cp.returncode != 0:
        raise AssertionError(
            f"Could not provoke systemd-udevd.service logs. stderr={cp.stderr.strip()!r}"
        )


def _provoke_ufw() -> None:
    # ufw.service is often oneshot and silent; we intentionally do NOT restart it from a postdeploy test
    # to avoid any chance of SSH lockout.
    #
    # Best-effort: do something non-invasive. This may still produce zero ufw.service logs.
    _run(["sh", "-lc", "sudo ufw status verbose >/dev/null 2>&1 || true"], timeout=30)


CHECKS = (
    UnitCheck("docker.service", "15m", _provoke_docker),
    UnitCheck("containerd.service", "15m", _provoke_containerd),
    UnitCheck("systemd-udevd.service", "15m", _provoke_udevd),
    # For ufw.service we broaden the time window and allow skip if there are no unit logs at all.
    UnitCheck("ufw.service", "7d", _provoke_ufw, allow_skip_if_no_events=True),
)


@pytest.mark.postdeploy
@pytest.mark.parametrize("check", CHECKS, ids=lambda c: c.unit)
def test_host_journald_units_are_ingested_into_victorialogs(retry, check: UnitCheck) -> None:
    _require_postdeploy_on_target()

    # 1) First, see if we already have logs (avoids unnecessary actions)
    existing = _query_one(check.unit, check.lookback)
    if existing is not None:
        return

    # 2) Provoke + retry until it shows up
    check.provoke()

    def _check() -> None:
        obj = _query_one(check.unit, "30m" if not check.allow_skip_if_no_events else check.lookback)
        if obj is None and check.allow_skip_if_no_events:
            pytest.skip(
                f"No entries for {check.unit} found even after best-effort provoke. "
                "This unit is often oneshot/silent on Debian/RPi. "
                "If you want this to be strictly testable, we'd need a safe, intentional log emission mechanism "
                "(e.g., a dedicated systemd timer that logs under a stable identifier), "
                "or relax the assertion to cover ufw-related kernel logs instead of ufw.service."
            )
        assert obj is not None, (
            f"No entries found in VictoriaLogs for systemd_unit={check.unit} after provoke. "
            f"Query windows tried: {check.lookback} (precheck) and 30m (post-provoke)."
        )

    retry(_check, timeout_s=120, interval_s=3.0)
