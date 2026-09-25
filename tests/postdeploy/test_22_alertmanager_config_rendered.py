import os
import stat
import subprocess
from pathlib import Path

import pytest

from tests._lib.hostids import resolve_nobody_nogroup

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

    # 2) Host config exists + non-empty. The dir is 0750 root:nogroup (F26b), so only root
    #    (deploy.sh runs postdeploy as root) can look inside; step 3 covers other callers.
    if os.access(host_dir, os.X_OK):
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


def test_alertmanager_config_not_world_readable() -> None:
    """
    Contract (F26, F26b): the rendered config may hold the SMTP password.
      - alertmanager.yml is root:<nogroup> 0640 on the host
      - nothing below the config dir carries other-bits
      - alertmanager runs with that group, so it can still read the file
    """
    host_dir = Path(
        os.environ.get(
            "ALERTMANAGER_CONFIG_HOST_DIR",
            "/srv/data/stacks/monitoring/alertmanager-config",
        )
    )
    filename = os.environ.get("ALERTMANAGER_CONFIG_FILENAME", "alertmanager.yml")
    host_path = host_dir / filename
    if os.geteuid() != 0:
        pytest.skip("Needs root to inspect the 0750 config dir; deploy.sh runs postdeploy as root.")
    _, want_gid = resolve_nobody_nogroup()
    fix = "Fix: sudo ./deploy.sh (init-permissions + renderer reapply the mode)."

    st = host_path.stat()
    have = (stat.S_IMODE(st.st_mode), st.st_uid, st.st_gid)
    assert have == (0o640, 0, want_gid), (
        f"❌ {host_path}: expected 0640 0:{want_gid}, got {have[0]:04o} {have[1]}:{have[2]}\n{fix}"
    )

    exposed = [
        str(p)
        for p in [host_dir, *host_dir.rglob("*")]
        if stat.S_IMODE(p.lstat().st_mode) & stat.S_IRWXO
    ]
    assert not exposed, "❌ Entries with other-bits set:\n" + "\n".join(exposed) + f"\n{fix}"

    container = _detect_alertmanager_container()
    ids = _run(["docker", "exec", container, "sh", "-c", 'echo "$(id -u):$(id -g)"'])
    assert ids == f"65534:{want_gid}", (
        f"❌ {container} runs as {ids}, expected 65534:{want_gid}; "
        "it could not read the 0640 config.\n"
        "Fix: align compose user: with the host nogroup gid."
    )


def test_alertmanager_config_renderer_ran_offline_and_succeeded() -> None:
    """
    Contract (F8, F36): the one-shot renderer exits 0 and ran with no network at all,
    so a deploy never depends on a package mirror.
    """
    out = _run(["docker", "ps", "-a", "--format", "{{.Names}}"])
    names = [n for n in out.splitlines() if "alertmanager-config-render" in n.lower()]
    if len(names) != 1:
        raise AssertionError(
            f"❌ Expected exactly one alertmanager-config-render container, found {names!r}.\n"
            "Fix: sudo ./deploy.sh"
        )
    state = _run(
        [
            "docker",
            "inspect",
            names[0],
            "--format",
            "{{.State.ExitCode}} {{.HostConfig.NetworkMode}}",
        ]
    )
    assert state == "0 none", (
        f"❌ {names[0]}: exit code / network mode is {state!r}, expected '0 none' (F8).\n"
        f"Fix: check `docker logs {names[0]}`; the renderer must run with network_mode: none."
    )


def test_alertmanager_ready_endpoint() -> None:
    """Lightweight runtime check: Alertmanager reports ready."""
    url = os.environ.get("ALERTMANAGER_READY_URL", "http://127.0.0.1:9093/-/ready")
    _run(["curl", "-fsS", url])
