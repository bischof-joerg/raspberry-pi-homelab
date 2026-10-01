# tests/guards/test_58_findings_check.py
#
# Findings lifecycle, increment A: .claude/reports/repo-findings.md and .claude/roadmap.md grow with
# every increment, and the roadmap is read in full at the start of every session. Addressed
# findings move to .claude/reports/repo-findings-archive.md; the increment log moves to
# .claude/increment-log.md, and roadmap §7 keeps only its newest row. The index in the report stays
# complete, so every ID remains findable.
#
# .claude/tools/check_findings.py enforces the split. It runs here against the real files - so
# `make ci` and CI now run it - and against fixtures under tmp_path that each break one rule.

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKER = REPO_ROOT / ".claude/tools/check_findings.py"

FIELDS = ("Evidence", "Impact", "Proposed fix", "Test", "Acceptance", "Prevention")
LOG_HEADER = (
    "| Increment | Date | Commit | CI | Deploy + postdeploy | Notes |\n|---|---|---|---|---|---|\n"
)
NEWEST = "| R1.2 second | 2026-10-02 | `bbb` | green | ok | newest |"
OLDER = "| R1.1 first | 2026-10-01 | `aaa` | green | ok | older |"


SCHEDULING = "2026-10-01, operator: taken along with group a"


def _entry(
    fid: str,
    title: str,
    evidence: str = "`deploy.sh` does it",
    skip: str = "",
    scheduling: str = "",
) -> str:
    lines = [f"### {fid} – {title}", ""]
    for name in FIELDS:
        if name == skip:
            continue
        value = evidence if name == "Evidence" else "x"
        lines.append(f"- **{name}:** {value}")
    if scheduling:
        lines.append(f"- **Scheduling:** {scheduling}")
    return "\n".join(lines) + "\n"


def _row(fid: str, status: str, **cells: str) -> dict[str, str]:
    """One index row; defaults: Med, found 2026-10-01, due R1 (or — when addressed), group a."""
    row = {"fid": fid, "sev": "Med", "found": "2026-10-01", "status": status, "group": "a"}
    row["due"] = "—" if status == "addressed" else "R1"
    row.update(cells)
    return row


def _write(
    tmp_path: Path,
    *,
    index: list,
    report: list[str],
    archive: list[str],
    stage: str = "R1",
    next_increment: str = "R1.3 something",
    roadmap_rows: tuple[str, ...] = (NEWEST,),
    log_rows: tuple[str, ...] = (NEWEST, OLDER),
) -> list[str]:
    """Write a report, archive, roadmap and log; return the checker's arguments.

    `index` holds `_row` dicts or `(fid, status)` pairs; roadmap §6 gets one row per group, with
    every non-addressed ID under Open and every addressed one under Done.
    """
    rows = [r if isinstance(r, dict) else _row(*r) for r in index]
    index_rows = "".join(
        f"| {r['fid']} | Title {r['fid']} | Host | {r['sev']} | {r['found']} | {r['due']} "
        f"| {r['status']} | {r['group']} |\n"
        for r in rows
    )
    report_text = (
        "# Repository findings\n\n## Index\n\n"
        "| ID | Title | Area | Sev | Found | Due | Status | R1 |\n"
        "|---|---|---|---|---|---|---|---|\n"
        f"{index_rows}\n## Host\n\n" + "\n".join(report) + "\n## R1 increments\n\nx\n"
    )
    archive_text = "# Archived findings\n\n## Host\n\n" + "\n".join(archive)
    group_rows = ""
    for group in dict.fromkeys(r["group"] for r in rows):
        members = [r for r in rows if r["group"] == group]
        open_ids = ", ".join(r["fid"] for r in members if r["status"] != "addressed") or "—"
        done_ids = ", ".join(r["fid"] for r in members if r["status"] == "addressed") or "—"
        group_rows += f"| {group} | Test | {open_ids} | {done_ids} | x |\n"
    roadmap_text = (
        f"# Roadmap\n\n## 1. Status\n\n- **Stage:** {stage} — x\n"
        f"- **Next increment:** {next_increment}\n- **Other:** x\n\n"
        "## 6. R1 plan\n\n| Group | Scope | Open | Done | Why |\n"
        f"|---|---|---|---|---|\n{group_rows}\n"
        "## 7. Increment log\n\nFull log: `.claude/increment-log.md`.\n\n"
        + LOG_HEADER
        + "".join(f"{row}\n" for row in roadmap_rows)
        + "\n## 8. Lessons\n\nx\n"
    )
    log_text = "# Increment log\n\n" + LOG_HEADER + "".join(f"{row}\n" for row in log_rows)
    paths = []
    for name, text in (
        ("repo-findings.md", report_text),
        ("roadmap.md", roadmap_text),
        ("repo-findings-archive.md", archive_text),
        ("increment-log.md", log_text),
    ):
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        paths.append(str(path))
    return paths


def _valid(tmp_path: Path, **override) -> list[str]:
    spec = {
        "index": [("F1", "open"), ("F2", "addressed")],
        "report": [_entry("F1", "Open one")],
        "archive": [_entry("F2", "Done one")],
    }
    spec.update(override)
    return _write(tmp_path, **spec)


def _check(args: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), *(args or [])],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _fails_with(args: list[str], message: str) -> None:
    proc = _check(args)
    assert proc.returncode == 1 and message in proc.stdout, (
        f"❌ check_findings.py did not report '{message}' (rc={proc.returncode}):\n{proc.stdout}"
        f"{proc.stderr}"
    )


def test_real_findings_and_roadmap_pass() -> None:
    proc = _check()
    assert proc.returncode == 0, (
        f"❌ .claude/tools/check_findings.py fails on the repository:\n{proc.stdout}{proc.stderr}\n"
        "Fix: correct the report, archive, roadmap §6/§7 or increment log as the FAIL lines say."
    )


def test_valid_split_passes(tmp_path: Path) -> None:
    proc = _check(_valid(tmp_path))
    assert proc.returncode == 0, f"❌ A valid report/archive split fails:\n{proc.stdout}"


def test_archived_entry_must_be_addressed(tmp_path: Path) -> None:
    args = _valid(tmp_path, index=[("F1", "open"), ("F2", "partly")], archive=[_entry("F2", "x")])
    _fails_with(args, "F2: in the archive but 'partly'")


def test_addressed_entry_must_leave_the_report(tmp_path: Path) -> None:
    args = _valid(tmp_path, report=[_entry("F1", "Open one"), _entry("F2", "Done one")], archive=[])
    _fails_with(args, "F2: 'addressed' but still in the report")


def test_entry_must_not_be_in_both_files(tmp_path: Path) -> None:
    args = _valid(tmp_path, report=[_entry("F1", "Open one"), _entry("F2", "Done one")])
    _fails_with(args, "F2: in both the report and the archive")


def test_index_id_needs_an_entry(tmp_path: Path) -> None:
    args = _valid(tmp_path, index=[("F1", "open"), ("F2", "addressed"), ("F3", "open")])
    _fails_with(args, "index lists F3, which is in neither the report nor the archive")


def test_archived_entry_keeps_its_required_fields(tmp_path: Path) -> None:
    args = _valid(tmp_path, archive=[_entry("F2", "Done one", skip="Test")])
    _fails_with(args, "F2: missing or empty **Test**")


def test_archived_entry_paths_are_checked(tmp_path: Path) -> None:
    args = _valid(tmp_path, archive=[_entry("F2", "Done one", "`scripts/does-not-exist.sh`")])
    _fails_with(args, "F2: cited evidence path does not exist")


def test_roadmap_keeps_only_the_newest_log_row(tmp_path: Path) -> None:
    args = _valid(tmp_path, roadmap_rows=(NEWEST, OLDER))
    _fails_with(args, "roadmap §7 must hold exactly one log row, found 2")


def test_roadmap_row_is_the_newest_log_row(tmp_path: Path) -> None:
    args = _valid(tmp_path, roadmap_rows=(OLDER,))
    _fails_with(args, "roadmap §7 row differs from the newest row of")


# --- findings lifecycle, increment B: triage by severity (IN14-IN16) ------------------------------


def _one(tmp_path: Path, row: dict[str, str], scheduling: str = "", **roadmap) -> list[str]:
    """A report with one finding under test plus the archived F2."""
    return _write(
        tmp_path,
        index=[row, ("F2", "addressed")],
        report=[_entry(row["fid"], "Under test", scheduling=scheduling)],
        archive=[_entry("F2", "Done one")],
        **roadmap,
    )


def test_severity_must_be_known(tmp_path: Path) -> None:
    args = _one(tmp_path, _row("F1", "open", sev="Severe"))
    _fails_with(args, "F1: severity 'Severe' is not one of Critical, High, Med, Low")


def test_open_finding_needs_a_due(tmp_path: Path) -> None:
    args = _one(tmp_path, _row("F1", "open", due="—"))
    _fails_with(args, "F1: open but has no Due")


def test_critical_must_be_due_next(tmp_path: Path) -> None:
    row = _row("F70", "open", sev="Critical", due="R1")
    args = _one(tmp_path, row, next_increment="R1.3 F70 fix")
    _fails_with(args, "F70: Critical must be due 'next', found 'R1'")


def test_critical_must_be_the_next_increment(tmp_path: Path) -> None:
    row = _row("F70", "open", sev="Critical", due="next")
    args = _one(tmp_path, row, next_increment="R1.3 something else")
    _fails_with(args, "F70: Critical, but roadmap §1 'Next increment' does not name it")


def test_critical_due_next_and_named_passes(tmp_path: Path) -> None:
    row = _row("F70", "open", sev="Critical", due="next")
    proc = _check(_one(tmp_path, row, next_increment="R1.3 F70 fix"))
    assert proc.returncode == 0, f"❌ A correctly scheduled Critical finding fails:\n{proc.stdout}"


def test_high_needs_an_increment_due(tmp_path: Path) -> None:
    args = _one(tmp_path, _row("F70", "open", sev="High", due="R1"))
    _fails_with(args, "F70: High must be due at an increment (R<x>.<y>), found 'R1'")


def test_med_needs_a_stage_due(tmp_path: Path) -> None:
    args = _one(tmp_path, _row("F70", "open", due="R1.5"))
    _fails_with(args, "F70: Med must be due at a stage (R<x>), found 'R1.5'")


def test_scheduling_override_allows_another_due(tmp_path: Path) -> None:
    proc = _check(_one(tmp_path, _row("F70", "open", due="R1.5"), scheduling=SCHEDULING))
    assert proc.returncode == 0, f"❌ A Scheduling override is not honoured:\n{proc.stdout}"


def test_high_is_overdue_once_its_increment_is_logged(tmp_path: Path) -> None:
    args = _one(tmp_path, _row("F70", "open", sev="High", due="R1.2"))
    _fails_with(args, "F70: overdue, due at R1.2, which the increment log already holds")


def test_med_is_overdue_after_its_stage(tmp_path: Path) -> None:
    args = _one(tmp_path, _row("F70", "open", due="R1"), stage="R2")
    _fails_with(args, "F70: overdue, due in stage R1, the roadmap is at R2")


def test_new_finding_needs_a_found_date(tmp_path: Path) -> None:
    args = _one(tmp_path, _row("F70", "open", found="—"))
    _fails_with(args, "F70: no Found date")


def test_due_stage_matches_the_group_stage(tmp_path: Path) -> None:
    args = _one(tmp_path, _row("F70", "open", due="R2"))
    _fails_with(args, "F70: due in R2, but its group a belongs to R1")


def test_legacy_high_may_keep_a_stage_due(tmp_path: Path) -> None:
    proc = _check(_one(tmp_path, _row("F5", "open", sev="High", found="—", due="R1")))
    assert proc.returncode == 0, (
        f"❌ A legacy finding (≤ F63) with a stage Due fails; R1 schedules the backlog by group:\n"
        f"{proc.stdout}"
    )


# --- findings lifecycle, increment B4: prevention (IN17) ------------------------------------------


def _without_prevention(tmp_path: Path, fid: str) -> list[str]:
    return _write(
        tmp_path,
        index=[_row(fid, "open", found="—" if fid == "F5" else "2026-10-01"), ("F2", "addressed")],
        report=[_entry(fid, "Under test", skip="Prevention")],
        archive=[_entry("F2", "Done one")],
    )


def test_new_finding_needs_a_prevention(tmp_path: Path) -> None:
    _fails_with(_without_prevention(tmp_path, "F70"), "F70: missing or empty **Prevention**")


def test_legacy_finding_needs_no_prevention(tmp_path: Path) -> None:
    proc = _check(_without_prevention(tmp_path, "F5"))
    assert proc.returncode == 0, (
        f"❌ A legacy finding (≤ F63) without **Prevention** fails; the field starts with F64:\n"
        f"{proc.stdout}"
    )


# --- leave no trace on the Pi (IN18, F66) ---------------------------------------------------------

BASELINE = "| R1.20 baseline | 2026-10-01 | `ccc` | green | ok | last row before IN18 |"


def _log_with(tmp_path: Path, newest: str) -> list[str]:
    """A log whose newest row sits above the R1.20 baseline row; roadmap §7 repeats it."""
    return _valid(tmp_path, roadmap_rows=(newest,), log_rows=(newest, BASELINE, OLDER))


def test_row_above_the_baseline_needs_a_footprint(tmp_path: Path) -> None:
    row = "| R1.21 next | 2026-10-02 | `ddd` | green | ok | no footprint |"
    _fails_with(_log_with(tmp_path, row), "R1.21 next: log row has no 'Footprint:' (IN18)")


def test_footprint_must_be_none_or_cleaned(tmp_path: Path) -> None:
    row = "| Process change | 2026-10-02 | `ddd` | green | ok | Footprint: later |"
    _fails_with(
        _log_with(tmp_path, row),
        "Process change: 'Footprint:' must be 'none' or 'cleaned — <evidence>' (IN18)",
    )


@pytest.mark.parametrize(
    "footprint", ["Footprint: none", "Footprint: cleaned — /tmp empty (find output)"]
)
def test_footprint_none_or_cleaned_passes(tmp_path: Path, footprint: str) -> None:
    row = f"| R1.21 next | 2026-10-02 | `ddd` | green | ok | x. {footprint}. |"
    proc = _check(_log_with(tmp_path, row))
    assert proc.returncode == 0, f"❌ A valid footprint is refused:\n{proc.stdout}"


def test_rows_up_to_the_baseline_need_no_footprint(tmp_path: Path) -> None:
    proc = _check(_valid(tmp_path, roadmap_rows=(BASELINE,), log_rows=(BASELINE, OLDER)))
    assert proc.returncode == 0, (
        f"❌ A log row up to R1.20 without 'Footprint:' fails; IN18 starts after it:\n{proc.stdout}"
    )
