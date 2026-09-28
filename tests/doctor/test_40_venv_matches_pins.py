# tests/doctor/test_40_venv_matches_pins.py
#
# Finding F21: the repository .venv holds exactly the pinned dev toolchain - every installed
# package pinned in requirements-dev.txt (direct) or constraints-dev.txt (transitive), at the
# pinned version. `pip install -r` never removes packages, so a dropped dependency or a stray
# `pip install` stays in .venv until `make venv-clean venv`; this test makes that drift visible.
#
# pip itself is excluded until it is pinned as well (F21, R1.6).

from __future__ import annotations

import sys
from importlib import metadata
from pathlib import Path

import pytest

from tests._helpers import REPO_ROOT
from tests._lib.requirements import normalize, requirement_specs

VENV = REPO_ROOT / ".venv"
PIN_FILES = (REPO_ROOT / "requirements-dev.txt", REPO_ROOT / "constraints-dev.txt")
NOT_YET_PINNED = {"pip"}

pytestmark = pytest.mark.doctor


def _in_repo_venv() -> bool:
    return Path(sys.prefix).resolve() == VENV.resolve()


def _installed() -> dict[str, str]:
    return {
        normalize(dist.metadata["Name"]): dist.version
        for dist in metadata.distributions()
        if normalize(dist.metadata["Name"]) not in NOT_YET_PINNED
    }


def _pins() -> dict[str, str]:
    """Exact pins only; a range pins nothing (tests/precommit/test_50 rejects ranges)."""
    pins: dict[str, str] = {}
    for path in PIN_FILES:
        if path.is_file():
            pins.update(
                {
                    name: spec.removeprefix("==")
                    for name, spec in requirement_specs(path).items()
                    if spec.startswith("==")
                }
            )
    return pins


@pytest.fixture(autouse=True)
def _require_repo_venv() -> None:
    if not _in_repo_venv():
        pytest.skip(f"not running in {VENV} (sys.prefix={sys.prefix}); the check is about .venv")


@pytest.mark.xfail(strict=True, reason="F21: contract pinned before the fix")
def test_every_installed_package_is_pinned() -> None:
    unpinned = sorted(f"{n}=={v}" for n, v in _installed().items() if n not in _pins())
    assert not unpinned, (
        f"❌ Installed in .venv but pinned nowhere (F21): {unpinned}\n"
        "Fix: if it is a new transitive dependency, pin it in constraints-dev.txt; if it is "
        "left over, the operator runs `make venv-clean venv`."
    )


def test_installed_versions_match_pins() -> None:
    pins, installed = _pins(), _installed()
    wrong = sorted(
        f"{name}: installed {installed[name]}, pinned {pins[name]}"
        for name in pins.keys() & installed.keys()
        if installed[name] != pins[name]
    )
    assert not wrong, (
        "❌ .venv differs from the pins (F21):\n"
        + "\n".join(f" - {w}" for w in wrong)
        + "\nFix: run `make venv`; if a pin was bumped, it reinstalls the pinned version."
    )


def test_every_pin_is_installed() -> None:
    missing = sorted(set(_pins()) - set(_installed()))
    assert not missing, (
        f"❌ Pinned but not installed in .venv (F21): {missing}\n"
        "Fix: run `make venv`; if the package is no longer needed, remove its pin."
    )
