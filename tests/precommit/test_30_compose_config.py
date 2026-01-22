import os
import shutil
import pytest
from pathlib import Path

from tests._helpers import run, which_ok, REPO_ROOT

GRAFANA_ENV = REPO_ROOT / "monitoring/grafana/grafana.env"
GRAFANA_ENV_EXAMPLE = REPO_ROOT / "monitoring/grafana/grafana.env.example"

COMPOSE_FILE = REPO_ROOT / "monitoring/compose/docker-compose.yml"
ENV_EXAMPLE = REPO_ROOT / "monitoring/compose/env.example"

ALERTMANAGER_ENV = REPO_ROOT / "monitoring/alertmanager/alertmanager.env"
ALERTMANAGER_ENV_EXAMPLE = REPO_ROOT / "monitoring/alertmanager/alertmanager.env.example"


def compose_cmd():
    r = run(["docker", "compose", "version"])
    if r.returncode == 0:
        return ["docker", "compose"]
    return None


@pytest.mark.precommit
def test_compose_config(tmp_path):
    if not COMPOSE_FILE.exists():
        pytest.fail(f"Compose file missing: {COMPOSE_FILE}")

    if not which_ok("docker"):
        pytest.fail("docker is required for this repo's precommit suite")

    cmd = compose_cmd()
    if not cmd:
        pytest.fail("docker compose plugin not available")

    # Prepare a minimal env context for config validation
    # - use repo's env.example if present
    # - ensure alertmanager.env exists (copy from example) for the duration of the test
    # - provide dummy Grafana admin creds (non-secret) to avoid blank defaults
    created_files = []
    try:
        if ALERTMANAGER_ENV_EXAMPLE.exists() and not ALERTMANAGER_ENV.exists():
            ALERTMANAGER_ENV.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ALERTMANAGER_ENV_EXAMPLE, ALERTMANAGER_ENV)
            created_files.append(ALERTMANAGER_ENV)

        if GRAFANA_ENV_EXAMPLE.exists() and not GRAFANA_ENV.exists():
            GRAFANA_ENV.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(GRAFANA_ENV_EXAMPLE, GRAFANA_ENV)
            created_files.append(GRAFANA_ENV)

        env = os.environ.copy()
        env.setdefault("GRAFANA_ADMIN_USER", "admin")
        env.setdefault("GRAFANA_ADMIN_PASSWORD", "changeme")

        compose_args = [*cmd, "-f", str(COMPOSE_FILE)]
        if ENV_EXAMPLE.exists():
            compose_args += ["--env-file", str(ENV_EXAMPLE)]

        res = run([*compose_args, "config"], env=env)
        assert res.returncode == 0, f"Compose config invalid:\n{res.stdout}\n{res.stderr}"

    finally:
        # Clean up only what we created
        for f in created_files:
            try:
                f.unlink()
            except FileNotFoundError:
                pass
