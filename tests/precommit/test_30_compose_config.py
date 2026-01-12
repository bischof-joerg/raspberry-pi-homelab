import pytest
from pathlib import Path
from tests._helpers import run, which_ok, REPO_ROOT

COMPOSE_FILE = REPO_ROOT / "monitoring/compose/docker-compose.yml"

def compose_cmd():
    r = run(["docker", "compose", "version"])
    if r.returncode == 0:
        return ["docker", "compose"]
    return None

@pytest.mark.precommit
def test_compose_config():
    if not COMPOSE_FILE.exists():
        pytest.fail(f"Compose file missing: {COMPOSE_FILE}")

    if not which_ok("docker"):
        pytest.skip("docker not installed / not available in this environment")

    cmd = compose_cmd()
    if not cmd:
        pytest.skip("docker compose plugin not available")

    res = run([*cmd, "-f", str(COMPOSE_FILE), "config"])
    assert res.returncode == 0, f"Compose config invalid:\n{res.stdout}\n{res.stderr}"
