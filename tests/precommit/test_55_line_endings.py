"""F11: every tracked text file is stored with LF line endings.

A CRLF shebang breaks a script on the Pi with a confusing error, and a file edited on the Windows
side of the operator's machine can bring CRLF in (K9 in `.claude/ClaudeTransition.md`).
`.gitattributes` pins LF for all text; the index must hold no CRLF.
"""

from __future__ import annotations

import pytest

from tests._helpers import REPO_ROOT, run

GITATTRIBUTES = REPO_ROOT / ".gitattributes"
DEFAULT_RULE = "* text=auto eol=lf"


@pytest.mark.precommit
def test_gitattributes_pins_lf_for_all_text() -> None:
    lines = [line.strip() for line in GITATTRIBUTES.read_text(encoding="utf-8").splitlines()]
    assert DEFAULT_RULE in lines, (
        f"❌ .gitattributes lacks `{DEFAULT_RULE}` (F11).\n"
        "Fix: add it as the first rule; mark binary types with `binary`."
    )


@pytest.mark.precommit
def test_no_tracked_file_has_crlf_in_the_index() -> None:
    res = run(["git", "ls-files", "--eol"])
    assert res.returncode == 0, f"❌ git ls-files --eol failed:\n{res.stderr}"
    # Each line: "i/<index eol> w/<worktree eol> attr/<attributes>\t<path>"
    wrong = sorted(
        f"{line.split(chr(9), 1)[1]} ({line.split()[0]})"
        for line in res.stdout.splitlines()
        if line.split()[0] not in {"i/lf", "i/none", "i/-text"}
    )
    assert not wrong, (
        "❌ Tracked files stored with other than LF line endings (F11):\n"
        + "\n".join(f" - {w}" for w in wrong)
        + "\nFix: `git add --renormalize <file>` (or convert it to LF) and commit."
    )
