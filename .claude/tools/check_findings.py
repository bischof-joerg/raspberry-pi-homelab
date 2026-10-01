#!/usr/bin/env python3
"""Validate .claude/reports/repo-findings.md and its archive mechanically (V6.2).

Open and partly addressed findings live in the report; `addressed` ones move to
.claude/reports/repo-findings-archive.md, so the files read in every session stay small. The
report's index keeps one row per finding, archived or not.

Every finding entry (`### F<n> - title`), in either file, must carry non-empty **Evidence**,
**Impact**, **Proposed fix**, **Test** and **Acceptance** fields, and from F64 on **Prevention**
(IN17). Every repository path cited in
backticks on the Evidence line must exist, and a path written as `path` (absent) must NOT exist --
some findings are about a missing file, and that claim is checked too. The entries of both files
together must equal the index; an entry sits in exactly one file; the archive holds only
`addressed` findings and the report none.

The R1 group table in .claude/roadmap.md section 6 must agree with the index: every ID it lists
exists; an ID under "Open" is not `addressed`, one under "Done" is; every finding that is not
`addressed` sits under "Open" of exactly one group, and every `addressed` finding with a group sits
under "Done" of it; the group matches the index's R1 column. So "what is still open" stays complete.

The increment log lives in .claude/increment-log.md, newest row first; roadmap section 7 keeps
exactly one row, the newest one.

What this cannot do: prove that a cited file *says* what the finding claims. That needs a human
read, and is the lesson recorded in ClaudeTransition.md 5.2 (archive).

Run: python3 .claude/tools/check_findings.py [REPORT [ROADMAP [ARCHIVE [LOG]]]]
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
ARCHIVE = (
    pathlib.Path(sys.argv[3])
    if len(sys.argv) > 3
    else ROOT / ".claude/reports/repo-findings-archive.md"
)
LOG = pathlib.Path(sys.argv[4]) if len(sys.argv) > 4 else ROOT / ".claude/increment-log.md"

REQUIRED = ("Evidence", "Impact", "Proposed fix", "Test", "Acceptance")
# Findings up to LEGACY_MAX predate the findings lifecycle (IN14-IN17): no Prevention field, and
# R1 schedules them by group (stage Due, no Found date needed).
LEGACY_MAX = 63
REQUIRED_NEW = ("Prevention",)
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


def check_entries(text: str) -> list[str]:
    """Check every entry's fields and evidence paths; return the entry IDs in order."""
    heads = list(ENTRY.finditer(text))
    for i, head in enumerate(heads):
        fid = head.group(1)
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        block = text[head.start() : end]
        fields = {}
        legacy = int(re.match(r"F(\d+)", fid).group(1)) <= LEGACY_MAX
        for name in REQUIRED if legacy else REQUIRED + REQUIRED_NEW:
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
        if re.search(r"^- \*\*Scheduling:\*\*\s*\S", block, re.MULTILINE):
            overridden.add(fid)
    return [m.group(1) for m in heads]


overridden: set[str] = set()  # entries with an operator's **Scheduling:** line (IN16)


report = REPORT.read_text(encoding="utf-8")
report_ids = check_entries(report)
archive_ids = check_entries(ARCHIVE.read_text(encoding="utf-8"))
entry_ids = report_ids + archive_ids

for name, ids in (("report", report_ids), ("archive", archive_ids)):
    dupes = sorted({f for f in ids if ids.count(f) > 1})
    if dupes:
        fail(f"duplicate entries in the {name}: {dupes}")
for fid in sorted(set(report_ids) & set(archive_ids)):
    fail(f"{fid}: in both the report and the archive")

index_text = section(report, "## Index", "\n## ")
own_index = INDEX_ROW.findall(index_text)
for fid in own_index:
    if fid not in entry_ids:
        fail(f"index lists {fid}, which is in neither the report nor the archive")
for fid in sorted(set(entry_ids) - set(own_index)):
    fail(f"{fid}: has an entry but no row in the report's index")

# Index row: | ID | Title | Area | Sev | Found | Due | Status | R1 |
status: dict[str, str] = {}
group_of: dict[str, str] = {}
triage: dict[str, tuple[str, str, str]] = {}  # fid -> (Sev, Found, Due)
for line in index_text.splitlines():
    if INDEX_ROW.match(line):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        status[cells[0]], group_of[cells[0]] = cells[-2], cells[-1]
        if len(cells) == 8:
            triage[cells[0]] = (cells[3], cells[4], cells[5])
        else:
            fail(f"{cells[0]}: index row has {len(cells)} columns, expected 8")

for fid in archive_ids:
    if fid in status and status[fid] != "addressed":
        fail(f"{fid}: in the archive but '{status[fid]}'; only addressed findings are archived")
for fid in report_ids:
    if status.get(fid) == "addressed":
        fail(f"{fid}: 'addressed' but still in the report; move its entry to the archive")

# Roadmap row: | Group | Scope | Open | Done | Why |  (group: R1 letter a-z, or a stage like R3, R2d)
GROUP_ROW = re.compile(r"^\| ([a-z]|R\d[a-z]?) \|", re.MULTILINE)
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


# Increment log: roadmap section 7 keeps exactly the newest row of the log file.
def log_rows(text: str) -> list[str]:
    return [
        line.rstrip()
        for line in text.splitlines()
        if line.startswith("| ") and not line.startswith("| Increment |")
    ]


roadmap_rows = log_rows(section(ROADMAP.read_text(encoding="utf-8"), "## 7.", "\n## "))
full_log = log_rows(LOG.read_text(encoding="utf-8"))
if len(roadmap_rows) != 1:
    fail(f"roadmap §7 must hold exactly one log row, found {len(roadmap_rows)}")
elif not full_log or roadmap_rows[0] != full_log[0]:
    fail(f"roadmap §7 row differs from the newest row of {LOG.name}")

# Triage by severity (roadmap §2, IN14-IN16). Due is `next`, an increment `R<x>.<y>` or a stage
# `R<x>`: Critical -> next; High -> an increment; Med/Low -> a stage. An operator's **Scheduling:**
# line overrides the form, never the deadline. Findings up to LEGACY_MAX predate the model: R1
# schedules that backlog by group, so they may keep a stage Due and need no Found date.
SEVERITIES = ("Critical", "High", "Med", "Low")
NONE = {"—", "–", "-", ""}
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
INCREMENT_DUE = re.compile(r"^R(\d+)\.(\d+)$")
STAGE_DUE = re.compile(r"^R(\d+)$")

status_text = section(ROADMAP.read_text(encoding="utf-8"), "## 1.", "\n## ")
m = re.search(r"^- \*\*Stage:\*\* R(\d+)", status_text, re.MULTILINE)
current_stage = int(m.group(1)) if m else 0
if not m:
    fail("roadmap §1 has no '- **Stage:** R<n>' line")
m = re.search(r"^- \*\*Next increment:\*\*(.*?)(?=^- \*\*|\Z)", status_text, re.M | re.S)
next_ids = set(FID.findall(m.group(1))) if m else set()
logged = {m.group(1) for row in full_log if (m := re.match(r"^\| (R\d+\.\d+)\b", row))}


def group_stage(group: str) -> int | None:
    """R1 groups are single letters; the others name their stage (R2d -> 2, R3 -> 3)."""
    if re.fullmatch(r"[a-z]", group):
        return 1
    m = re.fullmatch(r"R(\d)[a-z]?", group)
    return int(m.group(1)) if m else None


for fid, (sev, found, due) in triage.items():
    legacy = int(re.match(r"F(\d+)", fid).group(1)) <= LEGACY_MAX
    override = fid in overridden
    if sev not in SEVERITIES:
        fail(f"{fid}: severity '{sev}' is not one of {', '.join(SEVERITIES)}")
    if not DATE.match(found) and not (legacy and found in NONE):
        fail(f"{fid}: no Found date" if found in NONE else f"{fid}: Found '{found}' is not a date")
    if status.get(fid) == "addressed":
        if due not in NONE:
            fail(f"{fid}: addressed, so Due must be '—', found '{due}'")
        continue
    if due in NONE:
        fail(f"{fid}: open but has no Due")
        continue
    inc, stg = INCREMENT_DUE.match(due), STAGE_DUE.match(due)
    if due != "next" and not inc and not stg:
        fail(f"{fid}: Due '{due}' is not 'next', an increment R<x>.<y> or a stage R<x>")
        continue
    if due == "next" and fid not in next_ids:
        fail(f"{fid}: {sev}, but roadmap §1 'Next increment' does not name it")
    if not override:
        if sev == "Critical" and due != "next":
            fail(f"{fid}: Critical must be due 'next', found '{due}'")
        elif sev == "High" and stg and not legacy:
            fail(f"{fid}: High must be due at an increment (R<x>.<y>), found '{due}'")
        elif sev in ("Med", "Low") and not stg:
            fail(f"{fid}: {sev} must be due at a stage (R<x>), found '{due}'")
    due_stage = int((inc or stg).group(1)) if (inc or stg) else current_stage
    stage_of_group = group_stage(group_of.get(fid, ""))
    if stage_of_group and due_stage != stage_of_group and not override:
        fail(
            f"{fid}: due in R{due_stage}, but its group {group_of[fid]} belongs to R{stage_of_group}"
        )
    if inc and due in logged:
        fail(f"{fid}: overdue, due at {due}, which the increment log already holds")
    if due_stage < current_stage:
        fail(f"{fid}: overdue, due in stage R{due_stage}, the roadmap is at R{current_stage}")

print(f"{len(report_ids)} report entries, {len(archive_ids)} archived, {len(own_index)} index rows")
print(f"{len(full_log)} increment log rows")
print(f"{len(open_seen)} open and {len(done_seen)} done findings in the roadmap groups")
print(f"{failures} failure(s)")
sys.exit(1 if failures else 0)
