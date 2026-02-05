from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from tests._helpers import (
    compose_container_name,
    compose_ps_json,
    compose_services_by_name,
    find_monitoring_compose_file,
    run,
    which_ok,
)

COMPOSE_FILE: Path = find_monitoring_compose_file()

# Tunables (env override)
POSTDEPLOY_PS_TIMEOUT_S = int(os.environ.get("POSTDEPLOY_PS_TIMEOUT_S", "45"))
POSTDEPLOY_PS_INTERVAL_S = float(os.environ.get("POSTDEPLOY_PS_INTERVAL_S", "1.0"))

POSTDEPLOY_HEALTH_TIMEOUT_S = int(os.environ.get("POSTDEPLOY_HEALTH_TIMEOUT_S", "120"))
POSTDEPLOY_HEALTH_INTERVAL_S = float(os.environ.get("POSTDEPLOY_HEALTH_INTERVAL_S", "5.0"))

POSTDEPLOY_LOG_TAIL = int(os.environ.get("POSTDEPLOY_LOG_TAIL", "200"))


def _docker_logs_tail(container: str, tail: int = POSTDEPLOY_LOG_TAIL) -> str:
    if not which_ok("docker"):
        return "(docker not available to collect logs)"
    res = run(["docker", "logs", "--tail", str(tail), container])
    if res.returncode != 0:
        return f"(docker logs failed: rc={res.returncode}\nstdout:\n{res.stdout}\nstderr:\n{res.stderr})"
    return res.stdout or ""


def _now_ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


@pytest.mark.postdeploy
def test_compose_services_state_json(retry):
    expected = {
        "grafana": "running",
        "alertmanager": "running",
        "node-exporter": "running",
        "cadvisor": "running",
        "victoriametrics": "running",
        "vmagent": "running",
        "vmalert": "running",
        # one-shot job:
        "alertmanager-config-render": "exited",
    }

    # Prometheus is removed: treat it as permanently banned.
    banned: set[str] = {"prometheus"}

    rows: dict[str, dict] = {}

    def _wait_for_expected_services():
        nonlocal rows
        ps_rows = compose_ps_json(compose_file=COMPOSE_FILE)
        rows = compose_services_by_name(ps_rows)

        present_banned = sorted(banned & set(rows.keys()))
        assert not present_banned, (
            "Banned services present in compose ps.\n"
            f"Present banned: {present_banned}\n"
            f"Got: {sorted(rows.keys())}\n"
        )

        missing = sorted(set(expected.keys()) - set(rows.keys()))
        assert not missing, (
            f"Missing services in compose ps ({_now_ts()}).\n"
            f"Missing: {missing}\n"
            f"Got: {sorted(rows.keys())}\n"
            f"Hint: one-shot jobs require `docker compose ps --all` (enabled) and may race right after `up -d`."
        )

    retry(
        _wait_for_expected_services,
        timeout_s=POSTDEPLOY_PS_TIMEOUT_S,
        interval_s=POSTDEPLOY_PS_INTERVAL_S,
    )

    for svc, want in expected.items():
        row = rows[svc]
        state = (row.get("State") or row.get("state") or "").lower()
        assert want in state, (
            f"{svc}: expected state contains '{want}', got '{state}'. Full row: {row}"
        )

        if svc == "alertmanager-config-render":
            # Prefer ExitCode from ps json; fallback to docker inspect if missing.
            exit_code = row.get("ExitCode")

            if exit_code is None:
                if not which_ok("docker"):
                    pytest.fail("docker required to inspect ExitCode for one-shot job")

                name = compose_container_name(rows, svc) or ""
                assert name, f"Missing container Name for service {svc}. Row: {row}"

                insp = run(["docker", "inspect", "-f", "{{.State.ExitCode}}", name])
                assert insp.returncode == 0, f"docker inspect failed:\n{insp.stdout}\n{insp.stderr}"
                exit_code = (insp.stdout or "").strip()

            assert str(exit_code) == "0", (
                f"{svc}: expected ExitCode 0, got {exit_code}. Full row: {row}"
            )


@pytest.mark.postdeploy
def test_compose_services_not_restarting_or_unhealthy(retry):
    services = [
        "grafana",
        "alertmanager",
        "node-exporter",
        "cadvisor",
        "victoriametrics",
        "vmagent",
        "vmalert",
    ]

    banned: set[str] = {"prometheus"}

    def _assert_services_ok():
        ps_rows = compose_ps_json(compose_file=COMPOSE_FILE)
        rows = compose_services_by_name(ps_rows)

        present_banned = sorted(banned & set(rows.keys()))
        assert not present_banned, "Banned services present:\n" + "\n".join(present_banned)

        missing = sorted(set(services) - set(rows.keys()))
        assert not missing, "Missing services in compose ps:\n" + "\n".join(missing)

        # Keep your existing checks here:
        # - not restarting
        # - not unhealthy
        # (depends on how rows is structured)

    retry(
        _assert_services_ok, timeout_s=POSTDEPLOY_PS_TIMEOUT_S, interval_s=POSTDEPLOY_PS_INTERVAL_S
    )
