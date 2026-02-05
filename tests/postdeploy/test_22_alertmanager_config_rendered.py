import os
import subprocess

import pytest

pytestmark = pytest.mark.postdeploy


def _run(cmd: list[str]) -> str:
    p = subprocess.run(cmd, check=True, text=True, capture_output=True)
    return p.stdout.strip()


def _detect_alertmanager_container() -> str:
    """
    Resolve the alertmanager container deterministically:
      - Prefer explicit env var ALERTMANAGER_CONTAINER
      - Else find a single running container whose name includes 'alertmanager'
        but does not include 'config-render'
    """
    explicit = os.environ.get("ALERTMANAGER_CONTAINER")
    if explicit:
        return explicit

    out = _run(["docker", "ps", "--format", "{{.Names}}"])
    names = [
        n
        for n in out.splitlines()
        if "alertmanager" in n.lower() and "config-render" not in n.lower()
    ]
    if len(names) != 1:
        raise RuntimeError(
            "Could not uniquely determine alertmanager container.\n"
            f"Found: {names!r}\n"
            "Set ALERTMANAGER_CONTAINER=<container_name> to disambiguate."
        )
    return names[0]


def test_alertmanager_config_rendered_exists_on_host_and_in_container() -> None:
    """
    Contract:
      - alertmanager loads --config.file=/etc/alertmanager/alertmanager.yml
      - /etc/alertmanager is a bind mount from the host
      - the rendered config file must exist and be non-empty on host and in container
    """
    container = _detect_alertmanager_container()

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

    # 4) Basic structure sanity (avoid secrets)
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
    """Lightweight runtime check: Alertmanager reports ready."""
    url = os.environ.get("ALERTMANAGER_READY_URL", "http://127.0.0.1:9093/-/ready")
    _run(["curl", "-fsS", url])
