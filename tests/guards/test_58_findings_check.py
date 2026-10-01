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

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKER = REPO_ROOT / ".claude/tools/check_findings.py"

FIELDS = ("Evidence", "Impact", "Proposed fix", "Test", "Acceptance")
LOG_HEADER = (
    "| Increment | Date | Commit | CI | Deploy + postdeploy | Notes |\n|---|---|---|---|---|---|\n"
)
NEWEST = "| R1.2 second | 2026-10-02 | `bbb` | green | ok | newest |"
OLDER = "| R1.1 first | 2026-10-01 | `aaa` | green | ok | older |"


def _entry(fid: str, title: str, evidence: str = "`deploy.sh` does it", skip: str = "") -> str:
    lines = [f"### {fid} – {title}", ""]
    for name in FIELDS:
        if name == skip:
            continue
        value = evidence if name == "Evidence" else "x"
        lines.append(f"- **{name}:** {value}")
    return "\n".join(lines) + "\n"


def _write(
    tmp_path: Path,
    *,
    index: list[tuple[str, str]],
    report: list[str],
    archive: list[str],
    groups: tuple[str, str] = ("F1", "F2"),
    roadmap_rows: tuple[str, ...] = (NEWEST,),
    log_rows: tuple[str, ...] = (NEWEST, OLDER),
) -> list[str]:
    """Write a report, archive, roadmap and log; return the checker's arguments."""
    index_rows = "".join(
        f"| {fid} | Title {fid} | Host | Med | {status} | a |\n" for fid, status in index
    )
    report_text = (
        "# Repository findings\n\n## Index\n\n"
        "| ID | Title | Area | Sev | Status | R1 |\n|---|---|---|---|---|---|\n"
        f"{index_rows}\n## Host\n\n" + "\n".join(report) + "\n## R1 increments\n\nx\n"
    )
    archive_text = "# Archived findings\n\n## Host\n\n" + "\n".join(archive)
    roadmap_text = (
        "# Roadmap\n\n## 6. R1 plan\n\n| Group | Scope | Open | Done | Why |\n"
        f"|---|---|---|---|---|\n| a | Test | {groups[0]} | {groups[1]} | x |\n\n"
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
