#!/usr/bin/env python3
"""Validate .claude/skills/: frontmatter parses, description budget, layout, tool grants.

`description` + `when_to_use` are loaded into context on **every turn** (capped at 1,536 chars per
skill), so their total across all skills is the standing cost of phase 4. The body is free until
the skill is invoked. Unknown frontmatter keys are ignored by Claude Code without an error, so
they are a failure here.

Run: .venv/bin/python .claude/tools/check_skills.py   (read-only, exit 1 on any failure)
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
SKILLS = ROOT / ".claude" / "skills"
CAP = 1536  # per-skill cap on description + when_to_use
# Documented SKILL.md frontmatter keys (https://code.claude.com/docs/en/skills, 2026-09-23).
KNOWN = {
    "name",
    "description",
    "when_to_use",
    "argument-hint",
    "arguments",
    "disable-model-invocation",
    "user-invocable",
    "allowed-tools",
    "disallowed-tools",
    "model",
    "effort",
    "context",
    "agent",
    "background",
    "hooks",
    "paths",
    "shell",
    "metadata",
    "license",
    "compatibility",
}

failures = 0
total_desc = 0
rows = []

for skill_dir in sorted(p for p in SKILLS.iterdir() if p.is_dir()):
    md = skill_dir / "SKILL.md"
    if not md.exists():
        print(f"FAIL {skill_dir.name}: no SKILL.md")
        failures += 1
        continue
    text = md.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        print(f"FAIL {skill_dir.name}: no frontmatter")
        failures += 1
        continue
    end = text.index("\n---\n", 3)
    try:
        meta = yaml.safe_load(text[4:end])
    except yaml.YAMLError as exc:
        print(f"FAIL {skill_dir.name}: frontmatter does not parse: {exc}")
        failures += 1
        continue

    body_lines = len(text[end + 5 :].splitlines())
    desc = str(meta.get("description", ""))
    weight = len(desc) + len(str(meta.get("when_to_use", "")))
    total_desc += weight

    if not desc:
        print(f"FAIL {skill_dir.name}: no description -> Claude cannot decide when to use it")
        failures += 1
    if weight > CAP:
        print(f"FAIL {skill_dir.name}: description+when_to_use {weight} > {CAP}")
        failures += 1
    if meta.get("name") != skill_dir.name:
        print(f"FAIL {skill_dir.name}: name {meta.get('name')!r} != directory name")
        failures += 1
    unknown = sorted(set(meta) - KNOWN)
    if unknown:
        print(f"FAIL {skill_dir.name}: unknown frontmatter keys {unknown} (silently ignored)")
        failures += 1
    if body_lines > 500:
        print(f"FAIL {skill_dir.name}: body {body_lines} lines > 500 (docs guidance)")
        failures += 1

    grants = meta.get("allowed-tools") or []
    rows.append((skill_dir.name, weight, body_lines, len(grants)))

for name, weight, body, grants in rows:
    note = f"  allowed-tools: {grants}" if grants else ""
    print(f"OK   {name:24} desc {weight:4} chars, body {body:3} lines{note}")

print(f"\nalways-loaded description budget: {total_desc} chars across {len(rows)} skills")
print(f"{failures} failure(s)")
sys.exit(1 if failures else 0)
