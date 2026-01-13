# helper for robust shell/tool calls in tests
import json
import os
import subprocess
from pathlib import Path
from shutil import which

# define root of repository. This is two levels up from this file
REPO_ROOT = Path(__file__).resolve().parents[1]


def which_ok(binary: str) -> bool:
    """Check if a binary/tool is available in PATH."""
    return which(binary) is not None

# wrapper function to call command-line applications with subprocess.run()
def run(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run a command and capture stdout/stderr (no exception on non-zero)."""
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        cmd,
        cwd=str(cwd or REPO_ROOT),
        env=merged_env,
        text=True,
        capture_output=True,
        check=False,
    )


def compose_cmd() -> list[str] | None:
    """
    Return docker compose command as list, or None if not available.
    Prefers plugin-style: `docker compose`.
    Falls back to legacy `docker-compose` if installed.
    """
    if not which_ok("docker"):
        return None

    res = run(["docker", "compose", "version"])
    if res.returncode == 0:
        return ["docker", "compose"]

    if which_ok("docker-compose"):
        return ["docker-compose"]

    return None


def compose_ps_json(*, compose_file: Path) -> list[dict]:
    """
    Return `docker compose ps --format json` output as list of dict rows.
    """
    cmd = compose_cmd()
    if not cmd:
        raise RuntimeError("docker compose not available")

    if not compose_file.exists():
        raise FileNotFoundError(f"Compose file missing: {compose_file}")

    res = run([*cmd, "-f", str(compose_file), "ps", "--format", "json"])
    if res.returncode != 0:
        raise RuntimeError(f"docker compose ps failed:\n{res.stdout}\n{res.stderr}")

    try:
        data = json.loads(res.stdout)
    except Exception as e:
        raise RuntimeError(f"Failed to parse compose ps json: {e}\nRaw:\n{res.stdout}") from e

    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected compose ps json type: {type(data)}\nRaw:\n{res.stdout}")

    return data


def compose_services_by_name(ps_rows: list[dict]) -> dict[str, dict]:
    """
    Key compose `ps --format json` rows by service name.
    Compose v2 typically uses keys like 'Service', 'Name', 'State', 'Status', 'ExitCode'.
    """
    out: dict[str, dict] = {}
    for row in ps_rows:
        svc = row.get("Service") or row.get("service")
        if svc:
            out[svc] = row
    return out
