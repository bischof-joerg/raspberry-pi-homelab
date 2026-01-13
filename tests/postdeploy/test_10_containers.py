# Execute "docker compose -f <compose.yml path> ps" and check if it succeeds
import pytest
from tests._helpers import run, which_ok, REPO_ROOT

# Path with docker-compose.yml file
COMPOSE_FILE = REPO_ROOT / "monitoring/compose/docker-compose.yml"

@pytest.mark.postdeploy
def test_compose_ps():
    if not which_ok("docker"):
        pytest.skip("docker not installed")
    # execute docker compose ps on COMPOSE_FILE (see above is path for docker_compose.yml)
    res = run(["docker", "compose", "-f", str(COMPOSE_FILE), "ps"])
    assert res.returncode == 0, f"docker compose ps failed:\n{res.stdout}\n{res.stderr}"

@pytest.mark.postdeploy
def test_alertmanager_config_render_job_exits_cleanly():
    """
    alertmanager-config-render is a one-shot job container.
    It is expected to exit with code 0 after rendering the config.
    """
    if not which_ok("docker"):
        pytest.skip("docker not installed / not available")

    res = run(
        [
            "docker",
            "inspect",
            "-f",
            "{{.State.Status}} exit={{.State.ExitCode}} err={{.State.Error}}",
            "alertmanager-config-render",
        ]
    )
    assert res.returncode == 0, f"docker inspect failed:\n{res.stdout}\n{res.stderr}"

    out = (res.stdout or "").strip()
    assert "exited" in out, f"Expected config-render to be exited (one-shot job), got: {out}"
    assert "exit=0" in out, f"Expected exit code 0, got: {out}"
    assert "err=" in out, f"Expected empty error, got: {out}"
