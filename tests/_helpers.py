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
    Return `docker compose ps --all --format json` output as list of dict rows.

    Compose versions differ:
    - Some return a single JSON array: [ {...}, {...} ]
    - Others return NDJSON (one JSON object per line).
    This helper supports both.

    We use --all to include one-shot/exited containers (e.g. config render jobs).
    """
    cmd = compose_cmd()
    if not cmd:
        raise RuntimeError("docker compose not available")

    if not compose_file.exists():
        raise FileNotFoundError(f"Compose file missing: {compose_file}")

    res = run([*cmd, "-f", str(compose_file), "ps", "--all", "--format", "json"])
    if res.returncode != 0:
        raise RuntimeError(f"docker compose ps failed:\n{res.stdout}\n{res.stderr}")

    raw = (res.stdout or "").strip()
    if not raw:
        return []

    # 1) Try JSON array/dict first
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
        raise RuntimeError(f"Unexpected compose ps json type: {type(data)}")
    except json.JSONDecodeError:
        pass

    # 2) Fallback: NDJSON (one object per line)
    rows: list[dict] = []
    for i, line in enumerate(raw.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception as e:
            raise RuntimeError(f"Failed to parse compose ps NDJSON at line {i}: {e}\nLine:\n{line}") from e
        if not isinstance(obj, dict):
            raise RuntimeError(f"Unexpected NDJSON row type at line {i}: {type(obj)}\nLine:\n{line}")
        rows.append(obj)

    return rows


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
