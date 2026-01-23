import os
import shutil
import pytest

from tests._helpers import run, which_ok, REPO_ROOT

COMPOSE_FILE = REPO_ROOT / "monitoring/compose/docker-compose.yml"

COMPOSE_ENV = REPO_ROOT / "monitoring/compose/.env"
COMPOSE_ENV_EXAMPLE = REPO_ROOT / "monitoring/compose/.env.example"

ALERTMANAGER_ENV = REPO_ROOT / "monitoring/alertmanager/alertmanager.env"
ALERTMANAGER_ENV_EXAMPLE = REPO_ROOT / "monitoring/alertmanager/alertmanager.env.example"


def compose_cmd():
    r = run(["docker", "compose", "version"])
    if r.returncode == 0:
        return ["docker", "compose"]
    return None


def ensure_env_from_example(example_path, target_path, created_files):
    """
    Ensure target env file exists. If missing and example exists, copy it.
    Track created files so we can clean up after the test.
    """
    if example_path.exists() and not target_path.exists():
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(example_path, target_path)
        created_files.append(target_path)


@pytest.mark.precommit
def test_compose_config(tmp_path):
    if not COMPOSE_FILE.exists():
        pytest.fail(f"Compose file missing: {COMPOSE_FILE}")

    if not which_ok("docker"):
        pytest.fail("docker is required for this repo's precommit suite")

    cmd = compose_cmd()
    if not cmd:
        pytest.fail("docker compose plugin not available")

    created_files = []
    try:
        # Compose file references env_file paths that must exist for `docker compose config`.
        # We create temporary runtime env files from their tracked examples if needed.
        ensure_env_from_example(COMPOSE_ENV_EXAMPLE, COMPOSE_ENV, created_files)
        ensure_env_from_example(ALERTMANAGER_ENV_EXAMPLE, ALERTMANAGER_ENV, created_files)

        env = os.environ.copy()

        # Provide non-secret defaults that may be referenced in compose or templates
        env.setdefault("GRAFANA_ADMIN_USER", "admin")
        env.setdefault("GRAFANA_ADMIN_PASSWORD", "changeme")

        # Validate compose syntactically and with env_file resolution
        compose_args = [*cmd, "-f", str(COMPOSE_FILE)]

        # Optional: also feed Compose variable interpolation from the example env.
        # This is independent from `env_file:` entries and helps if compose uses ${VARS}.
        if COMPOSE_ENV_EXAMPLE.exists():
            compose_args += ["--env-file", str(COMPOSE_ENV_EXAMPLE)]

        res = run([*compose_args, "config"], env=env)
        assert res.returncode == 0, f"Compose config invalid:\n{res.stdout}\n{res.stderr}"

    finally:
        # Clean up only what we created
        for f in created_files:
            try:
                f.unlink()
            except FileNotFoundError:
                pass
