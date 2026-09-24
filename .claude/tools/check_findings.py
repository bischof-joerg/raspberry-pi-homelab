#!/usr/bin/env python3
"""Validate .claude/reports/repo-findings.md mechanically (V6.2).

Every finding entry (`### F<n> - title`) must carry non-empty **Evidence**, **Test** and
**Acceptance** fields. Every repository path cited in backticks on the Evidence line must exist,
and a path written as `path` (absent) must NOT exist -- some findings are about a missing file,
and that claim is checked too. The set of entry IDs must equal both the report's own index table
and the index in ClaudeTransition.md section 3.6, so the three cannot drift apart.

What this cannot do: prove that a cited file *says* what the finding claims. That needs a human
read, and is the lesson recorded in ClaudeTransition.md 5.2.

Run: python3 .claude/tools/check_findings.py   (stdlib only, read-only, exit 1 on any failure)
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
REPORT = ROOT / ".claude" / "reports" / "repo-findings.md"
PLAN = ROOT / ".claude" / "ClaudeTransition.md"

REQUIRED = ("Evidence", "Impact", "Proposed fix", "Test", "Acceptance")
ENTRY = re.compile(r"^### (F\d+b?) ", re.MULTILINE)
INDEX_ROW = re.compile(r"^\| (F\d+b?) \|", re.MULTILINE)
BACKTICK = re.compile(r"`([^`]+)`(\s*\(absent\))?")
PATHLIKE = re.compile(r"[A-Za-z0-9_.\-/]+")
EXTENSIONS = (".md", ".py", ".sh", ".yml", ".yaml", ".json", ".json5", ".toml", ".txt", ".tmpl")


def repo_path(token: str) -> str | None:
    """Return the repo-relative path a backticked token names, or None if it is not a path.

    A token with a slash counts as a path only if its first component is a top-level entry of the
    repository, so a CIDR (`172.20.0.0/16`) or an image name (`renovate/renovate:43`) is skipped.
    The trade-off: a typo in the top-level directory itself goes unnoticed.
    """
    token = re.sub(r":[0-9][0-9,\-]*$", "", token)  # strip a :line or :a-b,c suffix
    if not PATHLIKE.fullmatch(token) or token.startswith(("/", "~", "..")):
        return None
    if "/" in token:
        return token.rstrip("/") if (ROOT / token.split("/", 1)[0]).exists() else None
    if token.endswith(EXTENSIONS) or token in {"Makefile", "deploy.sh"}:
        return token
    return None


def section(text: str, start: str, stop: str) -> str:
    begin = text.index(start)
    return text[begin : text.index(stop, begin)]


failures = 0


def fail(msg: str) -> None:
    global failures
    print(f"FAIL {msg}")
    failures += 1


report = REPORT.read_text(encoding="utf-8")
heads = list(ENTRY.finditer(report))
entry_ids = [m.group(1) for m in heads]

for i, head in enumerate(heads):
    fid = head.group(1)
    end = heads[i + 1].start() if i + 1 < len(heads) else len(report)
    block = report[head.start() : end]
    fields = {}
    for name in REQUIRED:
        m = re.search(rf"^- \*\*{re.escape(name)}:\*\*(.*)$", block, re.MULTILINE)
        fields[name] = m.group(1).strip() if m else ""
        if not fields[name]:
            fail(f"{fid}: missing or empty **{name}**")
    checked = 0
    for token, absent in BACKTICK.findall(fields["Evidence"]):
        path = repo_path(token)
        if path is None:
            continue
        checked += 1
        exists = (ROOT / path).exists()
        if absent and exists:
            fail(f"{fid}: `{path}` is cited as absent but exists")
        elif not absent and not exists:
            fail(f"{fid}: cited evidence path does not exist: `{path}`")
    if checked == 0:
        fail(f"{fid}: Evidence cites no repository path")

dupes = sorted({f for f in entry_ids if entry_ids.count(f) > 1})
if dupes:
    fail(f"duplicate entries: {dupes}")

own_index = INDEX_ROW.findall(section(report, "## Index", "\n## "))
plan_index = INDEX_ROW.findall(section(PLAN.read_text(encoding="utf-8"), "### 3.6", "### 3.7"))
for label, ids in (("report index", own_index), ("ClaudeTransition.md 3.6", plan_index)):
    if set(ids) != set(entry_ids):
        missing = sorted(set(entry_ids) - set(ids))
        extra = sorted(set(ids) - set(entry_ids))
        fail(f"{label} differs from entries: missing {missing}, extra {extra}")

counts = f"{len(entry_ids)} entries, {len(own_index)} report index rows"
print(f"{counts}, {len(plan_index)} rows in ClaudeTransition.md 3.6")
print(f"{failures} failure(s)")
sys.exit(1 if failures else 0)
