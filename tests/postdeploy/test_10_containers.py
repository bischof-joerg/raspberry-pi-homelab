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
