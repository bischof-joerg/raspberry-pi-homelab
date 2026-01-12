import pytest
from tests._helpers import run, which_ok

@pytest.mark.precommit
def test_yamllint():
    if not which_ok("yamllint"):
        pytest.skip("yamllint not installed")
    res = run(["yamllint", "-c", ".yamllint.yml", "."])
    assert res.returncode == 0, f"yamllint failed:\n{res.stdout}\n{res.stderr}"
