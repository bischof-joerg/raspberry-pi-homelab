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
from tests._lib.compose_services import ONE_SHOT_SERVICES, load_services, long_running_services

COMPOSE_FILE: Path = find_monitoring_compose_file()

# F7 (R1.16): derived from the compose file. The hand-kept lists here checked 7 of 10
# long-running services and passed while VictoriaLogs stayed stopped after a reboot.
LONG_RUNNING = long_running_services(load_services(COMPOSE_FILE))

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


def _state(row: dict) -> str:
    return (row.get("State") or row.get("state") or "").lower()


def _health(row: dict) -> str:
    return (row.get("Health") or row.get("health") or "").lower()


@pytest.mark.postdeploy
def test_compose_services_state_json(retry):
    expected = {svc: "running" for svc in LONG_RUNNING}
    expected.update({svc: "exited" for svc in ONE_SHOT_SERVICES})

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
        state = _state(row)
        assert want in state, (
            f"❌ {svc}: expected state '{want}', got '{state}' (F7). Full row: {row}\n"
            "A long-running service that is not running after a reboot usually lacks "
            "`restart: unless-stopped`; `sudo ./deploy.sh` starts it again."
        )

        if svc in ONE_SHOT_SERVICES:
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
    banned: set[str] = {"prometheus"}

    def _assert_services_ok():
        ps_rows = compose_ps_json(compose_file=COMPOSE_FILE)
        rows = compose_services_by_name(ps_rows)

        present_banned = sorted(banned & set(rows.keys()))
        assert not present_banned, "Banned services present:\n" + "\n".join(present_banned)

        missing = sorted(set(LONG_RUNNING) - set(rows.keys()))
        assert not missing, "Missing services in compose ps:\n" + "\n".join(missing)

        bad = {
            svc: f"state={_state(rows[svc])} health={_health(rows[svc]) or '-'}"
            for svc in LONG_RUNNING
            if "restarting" in _state(rows[svc]) or _health(rows[svc]) == "unhealthy"
        }
        assert not bad, f"❌ Restarting or unhealthy services ({_now_ts()}): {bad}\n" + "\n".join(
            f"--- {svc} logs ---\n{_docker_logs_tail(compose_container_name(rows, svc) or svc)}"
            for svc in bad
        )

    retry(
        _assert_services_ok,
        timeout_s=POSTDEPLOY_HEALTH_TIMEOUT_S,
        interval_s=POSTDEPLOY_HEALTH_INTERVAL_S,
    )


@pytest.mark.postdeploy
def test_long_running_containers_restart_unless_stopped():
    """F7: the running containers carry `unless-stopped`, so they come back after a reboot."""
    if not which_ok("docker"):
        pytest.skip("docker not available")

    rows = compose_services_by_name(compose_ps_json(compose_file=COMPOSE_FILE))
    policies: dict[str, str] = {}
    for svc in LONG_RUNNING:
        name = compose_container_name(rows, svc)
        assert name, f"❌ No container for long-running service {svc} in compose ps."
        res = run(["docker", "inspect", "-f", "{{.HostConfig.RestartPolicy.Name}}", name])
        assert res.returncode == 0, f"❌ docker inspect {name} failed:\n{res.stderr}"
        policies[svc] = res.stdout.strip()

    wrong = {svc: policy for svc, policy in policies.items() if policy != "unless-stopped"}
    assert not wrong, (
        f"❌ Containers without restart policy `unless-stopped` (F7): {wrong}\n"
        "They stay down after a reboot.\nFix: `restart: unless-stopped` in "
        "stacks/monitoring/compose/docker-compose.yml, then sudo ./deploy.sh (recreates them)."
    )
