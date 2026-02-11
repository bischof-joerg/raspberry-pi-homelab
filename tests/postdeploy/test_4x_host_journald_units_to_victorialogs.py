from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from typing import Any

import pytest

POSTDEPLOY_ENV = "POSTDEPLOY_ON_TARGET"

VLOG_QUERY_URL_ENV = "VICTORIALOGS_QUERY_URL"
VLOG_QUERY_URL_DEFAULT = "http://127.0.0.1:9428/select/logsql/query"


def _require_postdeploy_on_target() -> None:
    if os.environ.get(POSTDEPLOY_ENV) != "1":
        pytest.skip(f"{POSTDEPLOY_ENV}=1 required (postdeploy on target)")


def _run(cmd: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=timeout)


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
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _query_one(expr: str, lookback: str) -> dict[str, Any] | None:
    q = f"_time:{lookback} ({expr}) | limit 1"
    body = _curl_victorialogs(q, timeout=20)
    return _first_json_obj(body)


# --- Deterministic journald sentinel (hard) ------------------------------------


def _provoke_journald_marker() -> str:
    marker = f"postdeploy_journald_smoke::{int(time.time())}::{os.getpid()}"
    tag = "postdeploy-journald-smoke"
    cp = _run(["sh", "-lc", f"logger -t {shlex.quote(tag)} {shlex.quote(marker)}"], timeout=15)
    if cp.returncode != 0:
        raise AssertionError(
            f"Could not write journald marker via logger. stderr={cp.stderr.strip()!r}"
        )
    return marker


def _expr_for_journald_marker(marker: str) -> str:
    return f"SYSLOG_IDENTIFIER:{_quote('postdeploy-journald-smoke')} {_quote(marker)}"


@pytest.mark.postdeploy
def test_host_journald_marker_is_ingested_into_victorialogs(retry) -> None:
    _require_postdeploy_on_target()

    marker = _provoke_journald_marker()

    def _assert_ingested() -> None:
        obj = _query_one(_expr_for_journald_marker(marker), "10m")
        assert obj is not None, (
            "No entries found in VictoriaLogs for journald sentinel marker.\n"
            f"Expr={_expr_for_journald_marker(marker)!r}"
        )

    retry(_assert_ingested, timeout_s=60, interval_s=3.0)


# --- Real-world signals (best-effort) ------------------------------------------


def _expr_for_docker_service() -> str:
    return f"systemd_unit:{_quote('docker.service')}"


def _expr_for_containerd_service() -> str:
    return f"systemd_unit:{_quote('containerd.service')}"


def _provoke_docker_pull() -> None:
    cp = _run(
        [
            "sh",
            "-lc",
            "docker pull -q hello-world:latest >/dev/null 2>&1 || docker pull hello-world:latest >/dev/null",
        ],
        timeout=300,
    )
    if cp.returncode != 0:
        # Best-effort: if provoke itself fails, report but do not fail the whole suite.
        pytest.skip(
            f"Could not provoke docker.service logs (docker pull failed). stderr={cp.stderr.strip()!r}"
        )


def _provoke_containerd_run() -> None:
    _run(["sh", "-lc", "docker run --rm hello-world:latest >/dev/null 2>&1 || true"], timeout=180)


@pytest.mark.postdeploy
def test_host_docker_service_logs_are_ingested_into_victorialogs_best_effort(retry) -> None:
    _require_postdeploy_on_target()

    # If present already, accept (do not spam).
    if _query_one(_expr_for_docker_service(), "24h") is not None:
        return

    _provoke_docker_pull()

    def _assert_ingested_or_skip() -> None:
        obj = _query_one(_expr_for_docker_service(), "30m")
        if obj is None:
            pytest.skip(
                "No docker.service entries found in VictoriaLogs after provoke. "
                "Some setups do not emit stable systemd_unit mapping for docker logs; treated as non-fatal."
            )

    retry(_assert_ingested_or_skip, timeout_s=90, interval_s=3.0)


@pytest.mark.postdeploy
def test_host_containerd_service_logs_are_ingested_into_victorialogs_best_effort(retry) -> None:
    _require_postdeploy_on_target()

    if _query_one(_expr_for_containerd_service(), "24h") is not None:
        return

    _provoke_containerd_run()

    def _assert_ingested_or_skip() -> None:
        obj = _query_one(_expr_for_containerd_service(), "30m")
        if obj is None:
            pytest.skip(
                "No containerd.service entries found in VictoriaLogs after provoke. "
                "Some setups do not emit stable systemd_unit mapping for containerd logs; treated as non-fatal."
            )

    retry(_assert_ingested_or_skip, timeout_s=90, interval_s=3.0)
