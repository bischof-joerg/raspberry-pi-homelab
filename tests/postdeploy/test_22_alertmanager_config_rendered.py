import os
import subprocess

import pytest

# Post-deploy tests run on the Raspberry Pi target.
pytestmark = pytest.mark.postdeploy


def _run(cmd: list[str]) -> str:
    p = subprocess.run(cmd, check=True, text=True, capture_output=True)
    return p.stdout.strip()


def _require_env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(
            f"Missing env var {name}. Set it explicitly for deterministic postdeploy runs."
        )
    return v


def test_alertmanager_config_rendered_exists_on_host_and_in_container() -> None:
    """
    Contract:
      - alertmanager loads --config.file=/etc/alertmanager/alertmanager.yml
      - /etc/alertmanager is a bind mount from the host
      - the rendered config file must exist and be non-empty on host and in container
    """

    # Deterministic inputs (explicit container name; defaults match your inspected setup)
    container = _require_env("ALERTMANAGER_CONTAINER")
    host_dir = os.environ.get(
        "ALERTMANAGER_CONFIG_HOST_DIR",
        "/srv/data/stacks/monitoring/alertmanager-config",
    )
    container_dir = os.environ.get("ALERTMANAGER_CONFIG_DIR", "/etc/alertmanager")
    filename = os.environ.get("ALERTMANAGER_CONFIG_FILENAME", "alertmanager.yml")

    host_path = os.path.join(host_dir, filename)
    container_path = os.path.join(container_dir, filename)

    # 1) Container exists
    _run(["docker", "inspect", container])

    # 2) Host config exists + non-empty
    if not os.path.isfile(host_path):
        raise AssertionError(f"Rendered Alertmanager config missing on host: {host_path}")
    if os.path.getsize(host_path) <= 0:
        raise AssertionError(f"Rendered Alertmanager config is empty on host: {host_path}")

    # 3) Container config exists + non-empty
    _run(["docker", "exec", container, "sh", "-lc", f"test -s {container_path}"])

    # 4) Basic YAML structure sanity (no secrets, just shape)
    # Require top-level keys commonly present in Alertmanager configs.
    _run(["docker", "exec", container, "sh", "-lc", f"grep -q '^route:' {container_path}"])
    _run(["docker", "exec", container, "sh", "-lc", f"grep -q '^receivers:' {container_path}"])

    # 5) Ensure bind mount is as expected (host_dir -> container_dir)
    mounts = _run(
        [
            "docker",
            "inspect",
            container,
            "--format",
            '{{range .Mounts}}{{printf "%s -> %s (%s)\\n" .Source .Destination .Type}}{{end}}',
        ]
    )
    expected = f"{host_dir} -> {container_dir} (bind)"
    if expected not in mounts.splitlines():
        raise AssertionError(
            "Alertmanager config dir is not bind-mounted as expected.\n"
            f"Expected mount line: {expected}\n"
            f"Actual mounts:\n{mounts}"
        )


def test_alertmanager_ready_endpoint() -> None:
    """
    Lightweight runtime check: Alertmanager reports ready.
    Assumes host can reach localhost:9093.
    """
    url = os.environ.get("ALERTMANAGER_READY_URL", "http://localhost:9093/-/ready")
    _run(["curl", "-fsS", url])
