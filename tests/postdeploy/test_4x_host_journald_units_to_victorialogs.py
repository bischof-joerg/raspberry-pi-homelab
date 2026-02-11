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


@dataclass(frozen=True)
class UnitCheck:
    unit: str
    precheck_lookback: str
    postcheck_lookback: str
    provoke: Callable[[], None]
    query_expr: str  # LogsQL expression WITHOUT _time
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


def _quote(s: str) -> str:
    # LogsQL double-quoted string
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _query_one(expr: str, lookback: str) -> dict[str, Any] | None:
    q = f"_time:{lookback} ({expr}) | limit 1"
    body = _curl_victorialogs(q, timeout=20)
    return _first_json_obj(body)


# --- Provoke helpers -----------------------------------------------------------


def _provoke_docker() -> None:
    # Pull emits dockerd log lines reliably (and is harmless).
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
    # Starting a short-lived container usually yields containerd shim logs.
    _run(["sh", "-lc", "docker run --rm hello-world:latest >/dev/null 2>&1 || true"], timeout=180)


def _provoke_udevd() -> None:
    # Increase udevd verbosity and trigger events. Guard against rare hangs:
    # udevadm settle can block for a long time on some systems.
    cp = _run(
        [
            "sh",
            "-lc",
            # Best-effort log-level change; never fail if it can't be set.
            # Hard timeouts ensure the test cannot stall indefinitely.
            "sudo udevadm control --log-level=info >/dev/null 2>&1 || true; "
            "timeout 20s sudo udevadm trigger >/dev/null 2>&1 || true; "
            "timeout 20s sudo udevadm settle >/dev/null 2>&1 || true",
        ],
        timeout=90,
    )
    # We accept timeouts (124) as "best effort". Ingestion assertion happens later.
    if cp.returncode not in (0, 124):
        raise AssertionError(f"Could not provoke udevd logs. stderr={cp.stderr.strip()!r}")


def _provoke_ufw() -> None:
    # Do NOT restart ufw.service (risk of firewall disruption). Best-effort only.
    _run(["sh", "-lc", "sudo ufw status verbose >/dev/null 2>&1 || true"], timeout=30)


CHECKS = (
    UnitCheck(
        unit="docker.service",
        precheck_lookback="24h",
        postcheck_lookback="30m",
        provoke=_provoke_docker,
        query_expr=f"systemd_unit:{_quote('docker.service')}",
    ),
    UnitCheck(
        unit="containerd.service",
        precheck_lookback="24h",
        postcheck_lookback="30m",
        provoke=_provoke_containerd,
        query_expr=f"systemd_unit:{_quote('containerd.service')}",
    ),
    UnitCheck(
        unit="systemd-udevd.service",
        precheck_lookback="24h",
        postcheck_lookback="30m",
        provoke=_provoke_udevd,
        # udev messages can appear as systemd-udevd *or* udev-worker; not always normalized to systemd_unit.
        query_expr=(
            f"systemd_unit:{_quote('systemd-udevd.service')} "
            f"OR SYSLOG_IDENTIFIER:{_quote('systemd-udevd')} "
            f"OR SYSLOG_IDENTIFIER:{_quote('udev-worker')}"
        ),
    ),
    UnitCheck(
        unit="ufw.service",
        precheck_lookback="7d",
        postcheck_lookback="7d",
        provoke=_provoke_ufw,
        query_expr=f"systemd_unit:{_quote('ufw.service')}",
        allow_skip_if_no_events=True,
    ),
)


@pytest.mark.postdeploy
@pytest.mark.parametrize("check", CHECKS, ids=lambda c: c.unit)
def test_host_journald_units_are_ingested_into_victorialogs(
    retry: Callable[..., None], check: UnitCheck
) -> None:
    _require_postdeploy_on_target()

    # 1) precheck (avoid actions if data already exists)
    if _query_one(check.query_expr, check.precheck_lookback) is not None:
        return

    # 2) provoke + retry
    check.provoke()

    def _check() -> None:
        obj = _query_one(check.query_expr, check.postcheck_lookback)
        if obj is None and check.allow_skip_if_no_events:
            pytest.skip(
                f"No entries for {check.unit} found. "
                "ufw.service is commonly oneshot/silent; this is treated as non-fatal."
            )
        assert obj is not None, (
            f"No entries found in VictoriaLogs after provoke for unit={check.unit}. "
            f"Expr={check.query_expr!r}, precheck=_time:{check.precheck_lookback}, postcheck=_time:{check.postcheck_lookback}"
        )

    retry(_check, timeout_s=120, interval_s=3.0)
