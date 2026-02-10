# tests/postdeploy/test_4x_host_journald_units_to_victorialogs.py
from __future__ import annotations

import json
import os
import shlex
import subprocess
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
    lookback: str  # VictoriaLogs _time window, e.g. "24h", "10m"


CHECKS = (
    UnitCheck("docker.service", "24h"),
    UnitCheck("containerd.service", "24h"),
    UnitCheck("ufw.service", "30m"),
    UnitCheck("systemd-udevd.service", "10m"),
)


def _require_postdeploy_on_target() -> None:
    if os.environ.get(POSTDEPLOY_ENV) != "1":
        pytest.skip(f"{POSTDEPLOY_ENV}=1 required (postdeploy on target)")


def _run(cmd: list[str], *, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    # Tests are typically executed under sudo in this repo, but don't assume it.
    return subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _curl_victorialogs(query: str, *, timeout: int = 15) -> str:
    url = os.environ.get(VLOG_QUERY_URL_ENV, VLOG_QUERY_URL_DEFAULT)
    # Use curl because it's already a project dependency in your stack workflow.
    # VictoriaLogs accepts the query via form field `query=...`.
    cp = _run(
        ["curl", "-fsS", url, "-d", f"query={query}"],
        timeout=timeout,
    )
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
    # VictoriaLogs often returns newline-delimited JSON objects (one per match).
    # If there are no matches, curl returns an empty body.
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


def _emit_activity_for_unit(unit: str) -> None:
    """
    Try to create at least one journal entry for units that may be quiet.
    Keep it safe: do NOT touch ssh/sshd here.
    """
    if unit == "systemd-udevd.service":
        # Generate udev activity.
        _run(["udevadm", "trigger"], timeout=60)
        _run(["udevadm", "settle"], timeout=60)
    elif unit == "ufw.service":
        # Ensure a ufw.service journal entry (start/stop) exists.
        # This is usually safe on a homelab host; it should re-apply the same rules.
        # If ufw is not enabled/installed, this will fail and the test will report it.
        _run(["systemctl", "restart", "ufw.service"], timeout=60)
    else:
        # docker.service and containerd.service usually log during deploy/pulls; no extra activity here.
        pass


@pytest.mark.postdeploy
@pytest.mark.parametrize("check", CHECKS, ids=lambda c: c.unit)
def test_host_journald_units_are_ingested_into_victorialogs(retry, check: UnitCheck) -> None:
    """
    Verify that journald entries for key host units are ingested into VictoriaLogs.

    Covered units (exactly four):
      - docker.service
      - containerd.service
      - ufw.service
      - systemd-udevd.service
    """
    _require_postdeploy_on_target()

    # Emit activity once (avoid flapping services repeatedly inside retry loop).
    _emit_activity_for_unit(check.unit)

    def _check() -> None:
        # Query newest matching entry and assert it contains the expected unit label.
        q = f"_time:{check.lookback} systemd_unit:{check.unit} | limit 1"
        body = _curl_victorialogs(q, timeout=15)
        obj = _first_json_obj(body)
        assert obj is not None, (
            f"No entries found in VictoriaLogs for systemd_unit={check.unit} "
            f"within _time:{check.lookback}. "
            f"Query was: {q!r}"
        )

        # Your Vector normalization typically maps journald `_SYSTEMD_UNIT` -> `systemd_unit`.
        unit_val = obj.get("systemd_unit") or obj.get("_SYSTEMD_UNIT")
        assert unit_val == check.unit, (
            f"Expected systemd_unit={check.unit!r}, got {unit_val!r}. obj keys={sorted(obj.keys())}"
        )

    # Match existing repo style: retry with a bounded timeout to allow ingestion latency.
    retry(_check, timeout_s=90, interval_s=3.0)
