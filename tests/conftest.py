from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure repository root is on sys.path so "import tests._helpers" works reliably
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_env_file_if_present(path: Path) -> None:
    """
    Best-effort: load KEY=VALUE pairs into os.environ.
    This is only for postdeploy tests running on the Pi. If the file is missing,
    tests should still run (without secrets).
    """
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not k:
            continue
        # Do not overwrite existing env vars (explicit env wins)
        os.environ.setdefault(k, v)


# Host-only secrets/config (GitOps policy): load if present on the Pi
_load_env_file_if_present(Path("/etc/raspberry-pi-homelab/monitoring.env"))
