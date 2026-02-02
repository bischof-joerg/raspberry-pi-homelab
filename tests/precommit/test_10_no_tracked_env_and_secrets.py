from __future__ import annotations

from pathlib import Path

import pytest

from tests._helpers import run

BLOCKED_EXACT = {
    ".env",
    ".env.local",
    ".env.prod",
    ".env.production",
    ".env.development",
}
BLOCKED_SUFFIXES = (".pem", ".key", ".p12", ".pfx")

ALLOWED_ENV_EXAMPLES = {
    ".env.example",
    "env.example",
    "alertmanager.env.example",
}


def is_blocked(path: Path) -> bool:
    name = path.name

    # allow examples
    if name in ALLOWED_ENV_EXAMPLES or name.endswith(".env.example"):
        return False

    if name in BLOCKED_EXACT:
        return True

    if name.endswith(BLOCKED_SUFFIXES):
        return True

    # block any *.env except *.env.example
    if name.endswith(".env"):
        return True

    parts_lower = [p.lower() for p in path.parts]
    # block any folder named secrets anywhere
    return "secrets" in parts_lower


@pytest.mark.precommit
def test_no_secret_like_files_tracked():
    res = run(["git", "ls-files"])
    assert res.returncode == 0, res.stderr

    blocked: list[str] = []
    for line in res.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        p = Path(line)
        if is_blocked(p):
            blocked.append(line)

    assert not blocked, (
        "❌ Secret/env-like files are tracked by git:\n" + "\n".join(f" - {f}" for f in blocked) + "\n\nFix:\n"
        " - Remove from git index: git rm --cached <file>\n"
        " - Add it to .gitignore\n"
    )
