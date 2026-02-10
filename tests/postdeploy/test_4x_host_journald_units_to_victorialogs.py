# tests/postdeploy/test_4x_host_journald_units_to_victorialogs.py
from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from typing import Any

import pytest

POSTDEPLOY_ENV = "POSTDEPLOY_ON_TARGET"
VLOG_QUERY_URL_ENV = "VICTORIALOGS_QUERY_URL"
VLOG_QUERY_URL_DEFAULT = "http://127.0.0.1:9428/select/logsql/query"

# Exactly these four units
UNITS = (
    "docker.service",
    "containerd.service",
    "ufw.service",
    "systemd-udevd.service",
)


@dataclass(frozen=True)
class UnitCheck:
    unit: str
    lookback: str  # VictoriaLogs _time window, e.g. "10m"


# Deterministic: we emit our own journald marker and then query for it.
CHECKS = tuple(UnitCheck(u, "10m") for u in UNITS)


def _require_postdeploy_on_target() -> None:
    if os.environ.get(POSTDEPLOY_ENV) != "1":
        pytest.skip(f"{POSTDEPLOY_ENV}=1 required (postdeploy on target)")


def _run(cmd: list[str], *, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _which(cmd: str) -> bool:
    cp = _run(["sh", "-lc", f"command -v {shlex.quote(cmd)} >/dev/null 2>&1"])
    return cp.returncode == 0


def _curl_victorialogs(query: str, *, timeout: int = 15) -> str:
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


def _emit_journald_marker(tag: str, marker: str) -> None:
    """
    Emit a harmless log line into journald with SYSLOG_IDENTIFIER=<tag>.

    We avoid restarting services (ufw especially), so this cannot affect the host.
    """
    if _which("systemd-cat"):
        # systemd-cat can run a command and capture its stdout into journald.
        cp = _run(
            ["systemd-cat", "-t", tag, "sh", "-lc", f"echo {shlex.quote(marker)}"], timeout=10
        )
        if cp.returncode == 0:
            return
        # fall through to logger with useful diagnostics if systemd-cat fails
    if _which("logger"):
        cp = _run(["logger", "-t", tag, marker], timeout=10)
        if cp.returncode == 0:
            return

    raise AssertionError(
        "Could not emit journald marker: neither systemd-cat nor logger worked.\n"
        f"tag={tag!r} marker={marker!r}"
    )


def _quote_logsql_string(s: str) -> str:
    # LogsQL string literals use double quotes; escape backslash and quote.
    # See VictoriaLogs LogsQL docs for string literal rules.  :contentReference[oaicite:1]{index=1}
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


@pytest.mark.postdeploy
@pytest.mark.parametrize("check", CHECKS, ids=lambda c: c.unit)
def test_host_journald_units_are_ingested_into_victorialogs(retry, check: UnitCheck) -> None:
    """
    Deterministic ingestion check:
      1) emit a journald entry tagged with SYSLOG_IDENTIFIER=<unit>
      2) assert the marker appears in VictoriaLogs within a bounded time

    Covered units (exactly four):
      - docker.service
      - containerd.service
      - ufw.service
      - systemd-udevd.service
    """
    _require_postdeploy_on_target()

    marker = f"postdeploy_journald_smoke::{check.unit}::{int(time.time())}"
    _emit_journald_marker(check.unit, marker)

    def _check() -> None:
        # Prefer SYSLOG_IDENTIFIER + exact marker match to avoid false positives.
        q = (
            f"_time:{check.lookback} "
            f"SYSLOG_IDENTIFIER:{_quote_logsql_string(check.unit)} "
            f"_msg:{_quote_logsql_string(marker)} | limit 1"
        )
        body = _curl_victorialogs(q, timeout=15)
        obj = _first_json_obj(body)
        assert obj is not None, (
            f"No entries found in VictoriaLogs for tag={check.unit} within _time:{check.lookback}. "
            f"Marker={marker!r}. Query was: {q!r}"
        )

        got_ident = obj.get("SYSLOG_IDENTIFIER")
        got_msg = obj.get("_msg")
        assert got_ident == check.unit, (
            f"Expected SYSLOG_IDENTIFIER={check.unit!r}, got {got_ident!r}"
        )
        assert marker in (got_msg or ""), f"Expected marker in _msg. _msg={got_msg!r}"

    retry(_check, timeout_s=90, interval_s=3.0)
