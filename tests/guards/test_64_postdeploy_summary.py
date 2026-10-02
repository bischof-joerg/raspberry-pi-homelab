# tests/guards/test_64_postdeploy_summary.py
#
# F56: the deploy log must keep the postdeploy counts, not only "tests: passed". deploy.sh pipes
# `make postdeploy` through tee, takes pytest's final summary line with
# scripts/tests/postdeploy-summary.sh, and logs it to the terminal and to the journal
# (`logger -t homelab-deploy`).
#
# The summary script is pure (stdin to stdout) and runs here. deploy.sh is Pi-only and never
# executed here (C5). run_postdeploy_tests() is checked statically, as in test_54, and its body
# alone runs in bash with deploy.sh's own ERR trap, log() and die(), and stubs for `make` and
# `logger` in tmp_path (operator, 2026-10-02: F56's Test field). Nothing else of deploy.sh runs.

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY = REPO_ROOT / "deploy.sh"
SUMMARY = REPO_ROOT / "scripts/tests/postdeploy-summary.sh"
JOURNAL_TAG = "homelab-deploy"

# pytest prints section headers in the same `=== … ===` form; only the last count line counts.
GREEN_RUN = """\
============================= test session starts ==============================
collected 102 items

tests/postdeploy/test_05_docker_daemon_json_and_metrics.py ....          [  3%]
==================================== PASSES ====================================
=========================== short test summary info ============================
PASSED tests/postdeploy/test_25_cadvisor_metrics.py::test_cadvisor_has_its_own_pid_namespace
SKIPPED [1] tests/postdeploy/test_21_vm_queries.py:118: VM_EXPECT_METRICS not set (or disabled).
======================= 98 passed, 4 skipped in 18.23s ========================
"""
STOPPED_RUN = """\
=========================== short test summary info ============================
FAILED tests/postdeploy/test_10_containers.py::test_all_running - AssertionError
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
================== 1 failed, 50 passed, 2 skipped in 9.87s ==================
"""
LONG_RUN = "============= 98 passed, 4 skipped in 75.02s (0:01:15) =============\n"
NO_SUMMARY = "ERROR: pytest not found\nmake: *** [Makefile:280: postdeploy] Error 2\n"


def _summary(text: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SUMMARY)], input=text, text=True, capture_output=True, check=False
    )


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        (GREEN_RUN, "98 passed, 4 skipped"),
        (STOPPED_RUN, "1 failed, 50 passed, 2 skipped"),
        (LONG_RUN, "98 passed, 4 skipped"),
    ],
    ids=["green", "stopped-by-maxfail", "long-run"],
)
def test_summary_is_the_last_count_line(output: str, expected: str) -> None:
    res = _summary(output)
    assert res.returncode == 0 and res.stdout.strip() == expected, (
        f"❌ postdeploy-summary.sh gave rc={res.returncode} {res.stdout.strip()!r}, "
        f"expected {expected!r} (F56).\nstderr: {res.stderr}\n"
        "Fix: print the counts of pytest's last `=== … in <n>s ===` line."
    )


def test_missing_summary_exits_non_zero() -> None:
    res = _summary(NO_SUMMARY)
    assert res.returncode == 1 and not res.stdout.strip(), (
        f"❌ Without a pytest summary the script gave rc={res.returncode} "
        f"{res.stdout.strip()!r}; expected rc=1 and no output (F56).\n"
        "Fix: exit 1, so deploy.sh logs `tests: FAILED (no pytest summary …)`."
    )


def _function(name: str) -> str:
    m = re.search(
        rf"^{name}\(\) \{{\n(.*?)^\}}",
        DEPLOY.read_text(encoding="utf-8"),
        flags=re.MULTILINE | re.DOTALL,
    )
    assert m, f"❌ deploy.sh has no function {name}().\nFix: add it."
    return m.group(1)


def test_run_postdeploy_tests_records_the_counts() -> None:
    body = _function("run_postdeploy_tests")
    required = {
        "the summary script": "postdeploy-summary.sh",
        "output kept while shown (tee)": "tee",
        "a private temp dir": "mktemp -d",
        "temp dir removed": "rm -rf",
        "the journal": f"logger -t {JOURNAL_TAG}",
        "the success line": "tests: passed (",
        "the failure line": "tests: FAILED (",
    }
    missing = sorted(what for what, token in required.items() if token not in body)
    # errexit stays on: make's rc is caught with `|| …`; toggling it inside a function would leak
    # to the rest of deploy.sh if a path forgot to restore it.
    forbidden = sorted(token for token in ("set +e",) if token in body)
    assert not missing and not forbidden, (
        f"❌ run_postdeploy_tests() lacks {missing}, contains {forbidden} (F56).\n"
        "Fix: tee `make postdeploy` into a mktemp -d dir, catch its rc with `|| …`, log "
        "`tests: passed (<summary>)` or `tests: FAILED (…)` to the terminal and "
        f"`logger -t {JOURNAL_TAG}`, and remove the dir in every path."
    )


def _one_liner(name: str) -> str:
    m = re.search(rf"^{name}\(\)\{{.*\}}$", DEPLOY.read_text(encoding="utf-8"), flags=re.MULTILINE)
    assert m, f"❌ deploy.sh has no one-line function {name}().\nFix: update this test."
    return m.group(0)


STUB_MAKE = """#!/usr/bin/env bash
echo "make $*" >>"$STUB_DIR/make.calls"
printf '%s\\n' "collected 3 items" "$STUB_LINE"
exit "${STUB_RC:-0}"
"""
STUB_LOGGER = """#!/usr/bin/env bash
echo "$*" >>"$STUB_DIR/logger.calls"
"""


def _run_postdeploy_tests(tmp_path: Path, *, rc: int, line: str, run_tests: str = "1"):
    """Run deploy.sh's run_postdeploy_tests() body with its own trap, log() and die()."""
    bin_dir, scratch = tmp_path / "bin", tmp_path / "tmp"
    bin_dir.mkdir()
    scratch.mkdir()
    for name, text in {"make": STUB_MAKE, "logger": STUB_LOGGER}.items():
        (bin_dir / name).write_text(text, encoding="utf-8")
        (bin_dir / name).chmod(0o755)
    script = "\n".join(
        [
            "set -euo pipefail",
            _one_liner("log"),
            _one_liner("die"),
            "on_err() {\n" + _function("on_err") + "}",
            "trap 'on_err $LINENO' ERR",
            f'REPO_ROOT="{REPO_ROOT}"',
            f'RUN_TESTS="{run_tests}"',
            "run_postdeploy_tests() {\n" + _function("run_postdeploy_tests") + "}",
            "run_postdeploy_tests",
            'echo "AFTER: returned"',
        ]
    )
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "TMPDIR": str(scratch),
        "STUB_DIR": str(tmp_path),
        "STUB_RC": str(rc),
        "STUB_LINE": line,
    }
    res = subprocess.run(
        ["bash", "-c", script], env=env, text=True, capture_output=True, check=False
    )
    calls = {
        name: (tmp_path / f"{name}.calls").read_text(encoding="utf-8")
        if (tmp_path / f"{name}.calls").exists()
        else ""
        for name in ("make", "logger")
    }
    return res, calls, sorted(p.name for p in scratch.iterdir())


@pytest.mark.parametrize(
    ("rc", "line", "exit_code", "result"),
    [
        (0, "=== 98 passed, 4 skipped in 18.23s ===", 0, "tests: passed (98 passed, 4 skipped)"),
        (1, "=== 1 failed, 50 passed in 9.87s ===", 2, "tests: FAILED (1 failed, 50 passed, rc=1)"),
        (0, "no summary at all", 2, "tests: FAILED (no pytest summary, rc=0)"),
        (
            2,
            "make: *** [Makefile:280: postdeploy] Error 2",
            2,
            "tests: FAILED (no pytest summary, rc=2)",
        ),
    ],
    ids=["green", "red", "no-summary", "make-error"],
)
def test_run_postdeploy_tests_behaviour(tmp_path, rc, line, exit_code, result) -> None:
    res, calls, leftovers = _run_postdeploy_tests(tmp_path, rc=rc, line=line)
    problems = []
    if res.returncode != exit_code:
        problems.append(f"exit {res.returncode}, expected {exit_code}")
    if result not in res.stdout:
        problems.append(f"no `{result}` in the output")
    if f"-t {JOURNAL_TAG} -- {result}" not in calls["logger"]:
        problems.append(f"journal got {calls['logger']!r}")
    if line not in res.stdout:
        problems.append("make's output did not reach the terminal (tee)")
    if "deploy.sh failed" in res.stderr:
        problems.append("the ERR trap fired instead of the explicit result")
    if exit_code and "ERROR: postdeploy tests failed" not in res.stderr:
        problems.append("no `die` message on failure")
    if not exit_code and "AFTER: returned" not in res.stdout:
        problems.append("the function did not return")
    if leftovers:
        problems.append(f"temp files left: {leftovers}")
    assert not problems, (
        f"❌ run_postdeploy_tests() with make rc={rc}: {problems} (F56).\n"
        f"stdout:\n{res.stdout}\nstderr:\n{res.stderr}"
    )


def test_run_postdeploy_tests_honours_run_tests_0(tmp_path) -> None:
    res, calls, _ = _run_postdeploy_tests(tmp_path, rc=0, line="", run_tests="0")
    assert res.returncode == 0 and "tests: skipped (RUN_TESTS=0)" in res.stdout, (
        f"❌ RUN_TESTS=0 gave rc={res.returncode}:\n{res.stdout}\n{res.stderr}"
    )
    assert not calls["make"], f"❌ RUN_TESTS=0 still ran make: {calls['make']!r}"
