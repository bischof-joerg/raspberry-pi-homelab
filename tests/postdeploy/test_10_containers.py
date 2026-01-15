# Execute "docker compose -f <compose.yml path> ps" and check if it succeeds
import time
import pytest

from tests._helpers import REPO_ROOT, compose_ps_json, compose_services_by_name, run, which_ok

COMPOSE_FILE = REPO_ROOT / "monitoring" / "compose" / "docker-compose.yml"


def get_rows_with_retry(expected_services: set[str], retries: int = 5, sleep_s: float = 0.5) -> dict[str, dict]:
    last_rows: dict[str, dict] = {}
    last_keys: list[str] = []

    for _ in range(retries):
        ps_rows = compose_ps_json(compose_file=COMPOSE_FILE)
        rows = compose_services_by_name(ps_rows)
        last_rows = rows
        last_keys = sorted(rows.keys())

        if expected_services.issubset(rows.keys()):
            return rows

        time.sleep(sleep_s)

    pytest.fail(
        f"Missing services after retries.\n"
        f"Expected: {sorted(expected_services)}\n"
        f"Got: {last_keys}\n"
        f"Hint: one-shot jobs require `docker compose ps --all` (enabled) and may race right after `up -d`."
    )

def wait_for_healthy(service: str, compose_file: str, timeout_s: int = 90, interval_s: int = 5) -> str:
    deadline = time.time() + timeout_s
    last = ""
    while time.time() < deadline:
        ps_rows = compose_ps_json(compose_file=compose_file)
        rows = compose_services_by_name(ps_rows)
        h = (rows.get(service, {}).get("Health") or "").lower()
        last = h
        if h == "healthy" or h == "":
            return h
        if h == "unhealthy":
            return h
        time.sleep(interval_s)
    return last

@pytest.mark.postdeploy
def test_compose_services_state_json():
    expected = {
        "prometheus": "running",
        "grafana": "running",
        "alertmanager": "running",
        "node-exporter": "running",
        "cadvisor": "running",
        # one-shot job:
        "alertmanager-config-render": "exited",
    }

    rows = get_rows_with_retry(set(expected.keys()), retries=5, sleep_s=0.5)

    for svc, want in expected.items():
        row = rows[svc]
        state = (row.get("State") or row.get("state") or "").lower()
        assert want in state, f"{svc}: expected state '{want}', got '{state}'. Full row: {row}"

        # Extra strictness for the one-shot job
        if svc == "alertmanager-config-render":
            exit_code = row.get("ExitCode")

            # Some compose versions omit ExitCode in ps output; fall back to docker inspect
            if exit_code is None:
                if not which_ok("docker"):
                    pytest.fail("docker required to inspect ExitCode")
                name = row.get("Name") or "alertmanager-config-render"
                insp = run(["docker", "inspect", "-f", "{{.State.ExitCode}}", name])
                assert insp.returncode == 0, f"docker inspect failed:\n{insp.stdout}\n{insp.stderr}"
                exit_code = (insp.stdout or "").strip()

            assert str(exit_code) == "0", f"{svc}: expected ExitCode 0, got {exit_code}. Full row: {row}"

@pytest.mark.postdeploy
def test_compose_services_not_restarting_or_unhealthy():
    ps_rows = compose_ps_json(compose_file=COMPOSE_FILE)
    rows = compose_services_by_name(ps_rows)

    # only check services we care about in this stack
    services = ["prometheus", "grafana", "alertmanager", "node-exporter", "cadvisor"]

    missing = [s for s in services if s not in rows]
    assert not missing, f"Missing services in compose ps: {missing}\nGot: {sorted(rows.keys())}"

    for svc in services:
        row = rows[svc]
        state = (row.get("State") or "").lower()
        status = (row.get("Status") or "").lower()
        health = (row.get("Health") or "").lower()

        assert "restarting" not in state, f"{svc}: restarting state detected. Row: {row}"
        assert "unhealthy" not in status, f"{svc}: unhealthy status detected. Row: {row}"

        # If Health field exists (non-empty), enforce healthy
        if health:
            final = wait_for_healthy(svc, compose_file=COMPOSE_FILE, timeout_s=90, interval_s=5)
            assert final == "healthy", f"{svc}: expected health=healthy, got health={final} after waiting. Row: {row}"
            