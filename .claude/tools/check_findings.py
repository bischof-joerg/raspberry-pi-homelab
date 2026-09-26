#!/usr/bin/env python3
"""Validate .claude/reports/repo-findings.md mechanically (V6.2).

Every finding entry (`### F<n> - title`) must carry non-empty **Evidence**, **Test** and
**Acceptance** fields. Every repository path cited in backticks on the Evidence line must exist,
and a path written as `path` (absent) must NOT exist -- some findings are about a missing file,
and that claim is checked too. The set of entry IDs must equal the report's own index table.

The R1 group table in .claude/roadmap.md section 6 must agree with the index: every ID it lists
exists; an ID under "Open" is not `addressed`, one under "Done" is; every finding that is not
`addressed` sits under "Open" of exactly one group, and every `addressed` finding with a group sits
under "Done" of it; the group matches the index's R1 column. So "what is still open" stays complete.

What this cannot do: prove that a cited file *says* what the finding claims. That needs a human
read, and is the lesson recorded in ClaudeTransition.md 5.2 (archive).

Run: python3 .claude/tools/check_findings.py [REPORT [ROADMAP]]
     (stdlib only, read-only, exit 1 on any failure; the optional paths serve negative controls)
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
REPORT = (
    pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / ".claude/reports/repo-findings.md"
)
ROADMAP = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / ".claude/roadmap.md"

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

index_text = section(report, "## Index", "\n## ")
own_index = INDEX_ROW.findall(index_text)
if set(own_index) != set(entry_ids):
    missing = sorted(set(entry_ids) - set(own_index))
    extra = sorted(set(own_index) - set(entry_ids))
    fail(f"report index differs from entries: missing {missing}, extra {extra}")

# Index row: | ID | Title | Area | Sev | Status | R1 |
status: dict[str, str] = {}
group_of: dict[str, str] = {}
for line in index_text.splitlines():
    if INDEX_ROW.match(line):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        status[cells[0]], group_of[cells[0]] = cells[-2], cells[-1]

# Roadmap row: | Group | Scope | Open | Done | Why |
GROUP_ROW = re.compile(r"^\| ([a-z]|R\d) \|", re.MULTILINE)
FID = re.compile(r"\bF\d+b?\b")
groups_text = section(ROADMAP.read_text(encoding="utf-8"), "## 6.", "\n## 7.")
open_seen: dict[str, list[str]] = {}
done_seen: dict[str, list[str]] = {}
for line in groups_text.splitlines():
    if not GROUP_ROW.match(line):
        continue
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    group = cells[0]
    for column, want_done, seen in (
        (cells[2], False, open_seen),
        (cells[3], True, done_seen),
    ):
        for fid in FID.findall(column):
            seen.setdefault(fid, []).append(group)
            if fid not in status:
                fail(f"roadmap group {group}: unknown finding {fid}")
                continue
            if (status[fid] == "addressed") != want_done:
                where = "Done" if want_done else "Open"
                fail(f"roadmap group {group}: {fid} is '{status[fid]}' but listed under {where}")
            if group_of[fid] != group:
                fail(f"roadmap group {group}: {fid} has R1 group '{group_of[fid]}' in the index")

for fid in entry_ids:
    if fid not in status:
        continue
    seen = done_seen if status[fid] == "addressed" else open_seen
    if status[fid] == "addressed" and group_of[fid] in {"–", "-", ""}:
        continue
    groups = seen.get(fid, [])
    if len(groups) != 1:
        where = "Done" if status[fid] == "addressed" else "Open"
        fail(
            f"{fid} ({status[fid]}) must be under {where} of exactly one roadmap group, found {groups}"
        )

print(f"{len(entry_ids)} entries, {len(own_index)} report index rows")
print(f"{len(open_seen)} open and {len(done_seen)} done findings in the roadmap groups")
print(f"{failures} failure(s)")
sys.exit(1 if failures else 0)
