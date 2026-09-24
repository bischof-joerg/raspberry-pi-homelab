#!/usr/bin/env python3
"""Validate .claude/rules/: frontmatter parses, `paths` is present, globs match real files.

An unparsable frontmatter is the dangerous case: Claude Code ignores it silently and loads the
rule unconditionally, which is exactly what the path scoping is meant to avoid.

Also V3.1: every repository path a rule cites in backticks must exist. This proves a cited file
exists, not that it says what the rule claims -- that still needs a human read (5.2).

Run: .venv/bin/python .claude/tools/check_rules.py   (read-only, exit 1 on any failure)
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

try:
    import yaml
except ImportError:
    print("PyYAML missing; run with .venv/bin/python")
    raise SystemExit(1) from None

ROOT = pathlib.Path(__file__).resolve().parents[2]
RULES = ROOT / ".claude" / "rules"

# Deliberately absent: a naming template, and a file whose whole point is never to exist in Git.
PLACEHOLDERS = {"ADR-NNNN-kebab-title.md", "settings.local.json"}
CITED_FILE = re.compile(r"`([A-Za-z0-9_.\-/]+\.(?:md|py|sh|yml|yaml|json|json5|toml|txt|example))`")
CITED_DIR = re.compile(r"`((?:docs|tests|scripts|stacks)/[A-Za-z0-9_.\-/]*/)`")


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Minimal gitignore-style glob. Python 3.12 has no PurePath.full_match."""
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def known(token: str, siblings: set[str], basenames: set[str]) -> bool:
    """True if a cited token names something that exists (or is exempt by design)."""
    if token.startswith("/"):  # absolute host path, not a repo file
        return True
    if token in PLACEHOLDERS or token in siblings:
        return True
    if (ROOT / token).exists():
        return True
    # bare filename used as shorthand for a file that exists somewhere
    return "/" not in token and token in basenames


tracked = subprocess.run(
    ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
).stdout.split()
basenames = {pathlib.PurePosixPath(f).name for f in tracked}
siblings = {p.name for p in RULES.glob("*.md")}

failures = 0
for rule in sorted(RULES.glob("*.md")):
    text = rule.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        print(f"FAIL {rule.name}: no frontmatter -> would load unconditionally")
        failures += 1
        continue
    end = text.index("\n---\n", 3)
    raw = text[4:end]
    try:
        meta = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        print(f"FAIL {rule.name}: frontmatter does not parse -> loads unconditionally: {exc}")
        failures += 1
        continue
    if not isinstance(meta, dict) or "paths" not in meta:
        print(f"FAIL {rule.name}: no `paths` key -> loads unconditionally")
        failures += 1
        continue
    patterns = meta["paths"]
    if isinstance(patterns, str):
        patterns = [p.strip() for p in patterns.split(",")]
    unknown = [k for k in meta if k != "paths"]
    body = text[end + 5 :]
    line_count = len(text.splitlines())
    hits_total = 0
    empty = []
    for pattern in patterns:
        if "[" in pattern:
            print(f"FAIL {rule.name}: `[` in glob {pattern!r} is a bracket expression")
            failures += 1
        rx = glob_to_regex(pattern)
        hits = [f for f in tracked if rx.match(f)]
        hits_total += len(hits)
        if not hits:
            empty.append(pattern)
    note = f"  ignored keys: {unknown}" if unknown else ""
    counts = f"{len(patterns)} pattern(s), {hits_total:3} file(s), {line_count:3} lines"
    print(f"OK   {rule.name:22} {counts}{note}")
    if empty:
        print(f"     WARN patterns matching nothing: {empty}")
    if not body.strip():
        print("     WARN empty body")

    cited = set(CITED_FILE.findall(body)) | set(CITED_DIR.findall(body))
    missing = sorted(c for c in cited if not known(c, siblings, basenames))
    if missing:
        print(f"     FAIL cited but missing: {missing}")
        failures += 1

print(f"\n{failures} failure(s)")
sys.exit(1 if failures else 0)
