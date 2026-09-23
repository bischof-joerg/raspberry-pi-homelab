#!/usr/bin/env python3
"""Validate .claude/agents/: required fields, and above all that `tools` is PRESENT.

`tools` is an allowlist. Omitting it does not mean "no tools" -- the subagent then inherits every
tool available to subagents, including Edit, Write and Bash. So the dangerous case is an absent
field, not a wrong one, and V5.3 ("no Edit/Write in the definitions") would pass a file that grants
everything. This check closes that gap (D5-a).

Run: .venv/bin/python .claude/tools/check_agents.py   (read-only, exit 1 on any failure)
"""

from __future__ import annotations

import pathlib
import sys

try:
    import yaml
except ImportError:
    print("PyYAML missing; run with .venv/bin/python")
    raise SystemExit(1) from None

ROOT = pathlib.Path(__file__).resolve().parents[2]
AGENTS = ROOT / ".claude" / "agents"

READ_ONLY = {"Read", "Grep", "Glob"}
FORBIDDEN = {"Edit", "Write", "MultiEdit", "NotebookEdit", "Bash", "Task", "Agent"}
# Documented subagent frontmatter keys (https://code.claude.com/docs/en/sub-agents, 2026-09-23).
KNOWN = {
    "name",
    "description",
    "tools",
    "disallowedTools",
    "model",
    "permissionMode",
    "maxTurns",
    "skills",
    "mcpServers",
    "hooks",
    "memory",
    "background",
    "omitClaudeMd",
    "effort",
    "isolation",
    "color",
    "initialPrompt",
    "experimental",
}

failures = 0
total_desc = 0

for path in sorted(AGENTS.rglob("*.md")):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        print(f"FAIL {path.name}: no frontmatter")
        failures += 1
        continue
    end = text.index("\n---\n", 3)
    try:
        meta = yaml.safe_load(text[4:end])
    except yaml.YAMLError as exc:
        print(f"FAIL {path.name}: frontmatter does not parse: {exc}")
        failures += 1
        continue

    for required in ("name", "description"):
        if not meta.get(required):
            print(f"FAIL {path.name}: `{required}` is required")
            failures += 1

    # The point of this script.
    if "tools" not in meta:
        print(f"FAIL {path.name}: no `tools` field -> inherits EVERY tool, incl. Edit/Write/Bash")
        failures += 1
        tools: set[str] = set()
    else:
        raw = meta["tools"]
        tools = set(raw if isinstance(raw, list) else [t.strip() for t in raw.split(",")])

    granted_forbidden = sorted(tools & FORBIDDEN)
    if granted_forbidden:
        print(f"FAIL {path.name}: grants {granted_forbidden} (V5.3 requires read-only)")
        failures += 1
    beyond = sorted(tools - READ_ONLY)
    if beyond and not granted_forbidden:
        print(f"WARN {path.name}: grants {beyond} beyond Read/Grep/Glob -- justify in the body")

    unknown = sorted(set(meta) - KNOWN)
    if unknown:
        print(f"FAIL {path.name}: unknown frontmatter keys {unknown}")
        failures += 1

    name = meta.get("name", "")
    if name.startswith("-") or ":" in name:
        print(f"FAIL {path.name}: name {name!r} may not start with '-' or contain ':'")
        failures += 1

    desc = str(meta.get("description", ""))
    total_desc += len(desc)
    body = len(text[end + 5 :].splitlines())
    print(f"OK   {name:20} tools={sorted(tools)} desc {len(desc):3} chars, body {body:3} lines")

print(f"\nalways-loaded description total: {total_desc} chars")
print(f"{failures} failure(s)")
sys.exit(1 if failures else 0)
