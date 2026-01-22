import pytest
from tests._helpers import run, which_ok

## This test is no longer need and covered by pre-commit hooks.
# Keeping it here for historical reasons.
# See: .pre-commit-config.yaml (jsonlint hook)
# For this reason changed marker from @pytest.mark.precommit to @pytest.mark.lint

@pytest.mark.lint
def test_yamllint():
    if not which_ok("yamllint"):
        pytest.skip("yamllint not installed")
    res = run(["yamllint", "-c", ".yamllint.yml", "."])
    assert res.returncode == 0, f"yamllint failed:\n{res.stdout}\n{res.stderr}"
