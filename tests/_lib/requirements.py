"""Parse the dev dependency pins (requirements-dev.txt, constraints-dev.txt).

Stdlib only: tests/precommit also runs inside the pre-commit hook environment.
"""

from __future__ import annotations

import re
from pathlib import Path

_REQ_LINE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(.*?)\s*(?:#.*)?$")


def normalize(name: str) -> str:
    """PEP 503 name normalization."""
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_specs(path: Path) -> dict[str, str]:
    """Map normalized package name -> version specifier; option lines (`-c ...`) are skipped."""
    specs: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "-")):
            continue
        match = _REQ_LINE.match(line)
        if match:
            specs[normalize(match.group(1))] = match.group(2).replace(" ", "")
    return specs


def option_lines(path: Path) -> list[str]:
    """pip option lines such as `-c constraints-dev.txt`, whitespace-normalized."""
    return [
        " ".join(raw.split())
        for raw in path.read_text(encoding="utf-8").splitlines()
        if raw.strip().startswith("-")
    ]
