"""Toolchain parity: tools installed into .venv must match the pre-commit pins.

Why: `make ci` runs pre-commit (pinned hook revs) while local/Claude read-only checks run the
same tools from `.venv` (installed from requirements-dev.txt). Diverging versions produce
diverging lint results. This test fails as soon as one side is bumped without the other.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest
import yaml

from tests._helpers import REPO_ROOT

PRE_COMMIT_CONFIG = REPO_ROOT / ".pre-commit-config.yaml"
REQUIREMENTS_DEV = REPO_ROOT / "requirements-dev.txt"
PYPROJECT = REPO_ROOT / "pyproject.toml"
MAKEFILE = REPO_ROOT / "Makefile"

# pre-commit hook repository URL -> PyPI distribution name installed into .venv
PARITY_MAP: dict[str, str] = {
    "https://github.com/astral-sh/ruff-pre-commit": "ruff",
    "https://github.com/shellcheck-py/shellcheck-py": "shellcheck-py",
    "https://github.com/adrienverge/yamllint": "yamllint",
}

_REQ_LINE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(.*?)\s*(?:#.*)?$")


def _normalize(name: str) -> str:
    """PEP 503 name normalization."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _pre_commit_revs(path: Path) -> dict[str, str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    revs: dict[str, str] = {}
    for repo in data.get("repos", []):
        url = str(repo.get("repo", ""))
        if url in PARITY_MAP:
            revs[url] = str(repo.get("rev", ""))
    return revs


def _requirement_specs(path: Path) -> dict[str, str]:
    specs: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _REQ_LINE.match(line)
        if match:
            specs[_normalize(match.group(1))] = match.group(2).replace(" ", "")
    return specs


@pytest.mark.precommit
def test_parity_map_repos_exist_in_pre_commit_config() -> None:
    revs = _pre_commit_revs(PRE_COMMIT_CONFIG)
    missing = sorted(set(PARITY_MAP) - set(revs))
    assert not missing, (
        "PARITY_MAP references hook repos not found in .pre-commit-config.yaml: "
        f"{missing}. Update PARITY_MAP in {Path(__file__).name} or restore the hook."
    )


@pytest.mark.precommit
@pytest.mark.parametrize(("hook_repo", "package"), sorted(PARITY_MAP.items()))
def test_requirements_dev_pins_match_pre_commit_rev(hook_repo: str, package: str) -> None:
    rev = _pre_commit_revs(PRE_COMMIT_CONFIG).get(hook_repo)
    if rev is None:
        pytest.fail(f"hook repo {hook_repo} missing in .pre-commit-config.yaml")
    expected = rev.removeprefix("v")

    specs = _requirement_specs(REQUIREMENTS_DEV)
    spec = specs.get(_normalize(package))
    assert spec is not None, (
        f"{package} missing in requirements-dev.txt; add '{package}=={expected}' "
        f"(must match {hook_repo} rev {rev})."
    )
    assert spec == f"=={expected}", (
        f"{package} in requirements-dev.txt is '{spec}', expected '=={expected}' "
        f"to match {hook_repo} rev {rev}. Bump both files in the same commit."
    )


# F22: requirements-dev.txt is the only source of dev dependencies.


def _venv_recipe() -> str:
    match = re.search(
        r"^venv:.*?\n(.*?)(?=^[A-Za-z_][\w.-]*:)",
        MAKEFILE.read_text(encoding="utf-8"),
        re.MULTILINE | re.DOTALL,
    )
    assert match, "❌ No 'venv:' target found in the Makefile.\nFix: update this test."
    return match.group(1)


@pytest.mark.precommit
@pytest.mark.xfail(strict=True, reason="F22: contract pinned before the fix")
def test_pyproject_declares_no_dev_dependencies() -> None:
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8")).get("project", {})
    extras = project.get("optional-dependencies", {})
    assert not extras and not project.get("dependencies"), (
        f"❌ pyproject.toml declares dependencies: {extras or project.get('dependencies')} (F22)\n"
        "Fix: declare dev dependencies in requirements-dev.txt only; make venv never reads "
        "pyproject.toml."
    )


@pytest.mark.precommit
@pytest.mark.xfail(strict=True, reason="F22: contract pinned before the fix")
def test_venv_installs_only_requirements_dev() -> None:
    installs = re.findall(r"pip\"?\s+install\s+([^;\\\n]*)", _venv_recipe())
    assert installs, "❌ The venv recipe runs no 'pip install'.\nFix: update this test."
    other = [
        args.strip()
        for args in installs
        if "-r requirements-dev.txt" not in args and not re.fullmatch(r"(-U\s+)?pip\b.*", args)
    ]
    assert not other, (
        f"❌ make venv installs from a source other than requirements-dev.txt (F22): {other}\n"
        "Fix: install only with 'pip install -r requirements-dev.txt'; fail if it is missing."
    )
