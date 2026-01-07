#!/usr/bin/env python3
import sys
from pathlib import Path

BLOCKED_EXACT = {
    ".env",
    ".env.local",
    ".env.prod",
    ".env.production",
    ".env.development",
    "alertmanager.env",
}
BLOCKED_SUFFIXES = (".pem", ".key", ".p12", ".pfx")

def is_blocked(p: Path) -> bool:
    name = p.name
    if name in BLOCKED_EXACT:
        return True
    if name.endswith(BLOCKED_SUFFIXES):
        return True
    parts_lower = [x.lower() for x in p.parts]
    return "secrets" in parts_lower

def main(argv: list[str]) -> int:
    blocked = [f for f in argv if is_blocked(Path(f))]
    if blocked:
        print("❌ Commit blocked: detected secret/env-like files staged:")
        for f in blocked:
            print(f"  - {f}")
        print("\nFix:")
        print("  - Remove from git: git rm --cached <file>")
        print("  - Add to .gitignore")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
