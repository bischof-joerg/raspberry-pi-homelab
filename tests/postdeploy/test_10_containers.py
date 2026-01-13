# Execute "docker compose -f <compose.yml path> ps" and check if it succeeds
import pytest

from tests._helpers import REPO_ROOT, compose_ps_json, compose_services_by_name, run, which_ok


COMPOSE_FILE = REPO_ROOT / "monitoring" / "compose" / "docker-compose.yml"


@pytest.mark.postdeploy
def test_compose_services_state_json():
    try:
        ps_rows = compose_ps_json(compose_file=COMPOSE_FILE)
    except Exception as e:
        pytest.fail(str(e))

    rows = compose_services_by_name(ps_rows)

    expected = {
        "prometheus": "running",
        "grafana": "running",
        "alertmanager": "running",
        "node-exporter": "running",
        "cadvisor": "running",
        # one-shot job:
        "alertmanager-config-render": "exited",
    }

    missing = [svc for svc in expected if svc not in rows]
    assert not missing, f"Missing services in compose ps: {missing}\nGot: {sorted(rows.keys())}"

    for svc, want in expected.items():
        row = rows[svc]
        state = (row.get("State") or row.get("state") or "").lower()

        assert want in state, f"{svc}: expected state '{want}', got '{state}'. Full row: {row}"

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
