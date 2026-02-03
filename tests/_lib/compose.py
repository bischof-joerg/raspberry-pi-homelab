from __future__ import annotations

import subprocess
from pathlib import Path

import yaml


def render_compose(compose_file: Path, env_file: Path | None = None) -> dict:
    cmd = ["docker", "compose"]
    if env_file is not None:
        cmd += ["--env-file", str(env_file)]
    cmd += ["-f", str(compose_file), "config"]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"docker compose config failed:\n{res.stderr}")

    return yaml.safe_load(res.stdout)
