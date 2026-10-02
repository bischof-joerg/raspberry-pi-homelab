# tests/guards/test_64_postdeploy_summary.py
#
# F56: the deploy log must keep the postdeploy counts, not only "tests: passed". deploy.sh pipes
# `make postdeploy` through tee, takes pytest's final summary line with
# scripts/tests/postdeploy-summary.sh, and logs it to the terminal and to the journal
# (`logger -t homelab-deploy`).
#
# The summary script is pure (stdin to stdout) and runs here. deploy.sh is Pi-only and never
# executed here (C5), so run_postdeploy_tests() is checked statically, as in test_54.

from __future__ import annotations

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


@pytest.mark.xfail(strict=True, reason="R1.26: postdeploy-summary.sh does not exist yet (F56)")
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


@pytest.mark.xfail(strict=True, reason="R1.26: postdeploy-summary.sh does not exist yet (F56)")
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


@pytest.mark.xfail(strict=True, reason="R1.26: run_postdeploy_tests logs no counts (F56)")
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
    # deploy.sh has an ERR trap (on_err): `set +e` around the pipeline would still fire it.
    forbidden = sorted(token for token in ("set +e",) if token in body)
    assert not missing and not forbidden, (
        f"❌ run_postdeploy_tests() lacks {missing}, contains {forbidden} (F56).\n"
        "Fix: tee `make postdeploy` into a mktemp -d dir, catch its rc with `|| …`, log "
        "`tests: passed (<summary>)` or `tests: FAILED (…)` to the terminal and "
        f"`logger -t {JOURNAL_TAG}`, and remove the dir in every path."
    )
