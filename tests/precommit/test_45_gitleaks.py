from __future__ import annotations

import pytest

from tests._helpers import run, which_ok


@pytest.mark.precommit
def test_gitleaks_detect():
    if not which_ok("gitleaks"):
        pytest.skip("gitleaks not installed")

    # --no-git: scan working tree (good for local dev)
    # alternative: without --no-git scans git history, can take a while.
    res = run(["gitleaks", "detect", "--no-banner", "--no-git"])
    assert res.returncode == 0, f"❌ gitleaks detected secrets:\n{res.stdout}\n{res.stderr}"
