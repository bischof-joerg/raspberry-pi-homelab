# helper for robust shell/tool calls in tests
import os
import subprocess
from pathlib import Path
from shutil import which

# define root of repository. This is two levels up from this file
REPO_ROOT = Path(__file__).resolve().parents[1]

# checks if a binary/tool is available in the PATH
def which_ok(binary: str) -> bool:
    return which(binary) is not None

# wrapper function to call command-line applications with subprocess.run()
def run(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
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
