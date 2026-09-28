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
from tests._lib.requirements import normalize, option_lines, requirement_specs

PRE_COMMIT_CONFIG = REPO_ROOT / ".pre-commit-config.yaml"
REQUIREMENTS_DEV = REPO_ROOT / "requirements-dev.txt"
CONSTRAINTS_DEV = REPO_ROOT / "constraints-dev.txt"
PYPROJECT = REPO_ROOT / "pyproject.toml"
MAKEFILE = REPO_ROOT / "Makefile"
ENSURE_VENV = REPO_ROOT / "scripts/dev/ensure-venv.sh"
PRECOMMIT_HOOK_ID = "pytest-precommit"

# pre-commit hook repository URL -> PyPI distribution name installed into .venv
PARITY_MAP: dict[str, str] = {
    "https://github.com/astral-sh/ruff-pre-commit": "ruff",
    "https://github.com/shellcheck-py/shellcheck-py": "shellcheck-py",
    "https://github.com/adrienverge/yamllint": "yamllint",
}


def _pre_commit_revs(path: Path) -> dict[str, str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    revs: dict[str, str] = {}
    for repo in data.get("repos", []):
        url = str(repo.get("repo", ""))
        if url in PARITY_MAP:
            revs[url] = str(repo.get("rev", ""))
    return revs


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

    specs = requirement_specs(REQUIREMENTS_DEV)
    spec = specs.get(normalize(package))
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
def test_pyproject_declares_no_dev_dependencies() -> None:
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8")).get("project", {})
    extras = project.get("optional-dependencies", {})
    assert not extras and not project.get("dependencies"), (
        f"❌ pyproject.toml declares dependencies: {extras or project.get('dependencies')} (F22)\n"
        "Fix: declare dev dependencies in requirements-dev.txt only; make venv never reads "
        "pyproject.toml."
    )


@pytest.mark.precommit
def test_venv_installs_only_requirements_dev() -> None:
    # The recipe may delegate to the script (F21, R1.6); both are checked.
    sources = _venv_recipe() + (
        ENSURE_VENV.read_text(encoding="utf-8") if ENSURE_VENV.exists() else ""
    )
    installs = re.findall(r"pip\"?\s+install\s+([^;\\\n]*)", sources)
    assert installs, "❌ make venv runs no 'pip install'.\nFix: update this test."
    other = [
        args.strip()
        for args in installs
        if not re.search(r"-r\s+\S*requirements", args, re.IGNORECASE)
        and not re.fullmatch(r"(-U\s+|-c\s+\S+\s+)?pip\b.*", args.strip())
    ]
    assert not other, (
        f"❌ make venv installs from a source other than requirements-dev.txt (F22): {other}\n"
        "Fix: install only with 'pip install -r requirements-dev.txt'; fail if it is missing."
    )


# F21: every dev dependency is pinned exactly - direct ones in requirements-dev.txt, transitive
# ones in constraints-dev.txt - and the pre-commit pytest hook uses the same direct pins.


def _unpinned(specs: dict[str, str]) -> list[str]:
    return [f"{name}{spec}" for name, spec in sorted(specs.items()) if not spec.startswith("==")]


def _hook_dependencies() -> list[str]:
    data = yaml.safe_load(PRE_COMMIT_CONFIG.read_text(encoding="utf-8")) or {}
    for repo in data.get("repos", []):
        for hook in repo.get("hooks", []):
            if hook.get("id") == PRECOMMIT_HOOK_ID:
                return [str(dep) for dep in hook.get("additional_dependencies", [])]
    pytest.fail(f"❌ Hook '{PRECOMMIT_HOOK_ID}' not found in .pre-commit-config.yaml.")


@pytest.mark.precommit
def test_requirements_dev_pins_exactly() -> None:
    unpinned = _unpinned(requirement_specs(REQUIREMENTS_DEV))
    assert not unpinned, (
        f"❌ requirements-dev.txt has non-exact pins (F21): {unpinned}\n"
        "Fix: pin each package with '==<version>' as installed in .venv."
    )


@pytest.mark.precommit
def test_requirements_dev_applies_constraints() -> None:
    assert f"-c {CONSTRAINTS_DEV.name}" in option_lines(REQUIREMENTS_DEV), (
        f"❌ requirements-dev.txt does not apply {CONSTRAINTS_DEV.name} (F21).\n"
        f"Fix: add the line '-c {CONSTRAINTS_DEV.name}' so transitive pins take effect."
    )


@pytest.mark.precommit
def test_constraints_pin_exactly_and_do_not_repeat_direct_pins() -> None:
    assert CONSTRAINTS_DEV.is_file(), (
        f"❌ {CONSTRAINTS_DEV.name} is missing (F21).\n"
        "Fix: pin every transitive dev dependency there with '==<version>'."
    )
    constraints = requirement_specs(CONSTRAINTS_DEV)
    assert constraints, f"❌ {CONSTRAINTS_DEV.name} pins nothing.\nFix: add the transitive pins."
    unpinned = _unpinned(constraints)
    assert not unpinned, (
        f"❌ {CONSTRAINTS_DEV.name} has non-exact pins (F21): {unpinned}\n"
        "Fix: pin with '==<version>'."
    )
    both = sorted(constraints.keys() & requirement_specs(REQUIREMENTS_DEV).keys())
    assert not both, (
        f"❌ Pinned in both requirements-dev.txt and {CONSTRAINTS_DEV.name}: {both} (F22)\n"
        "Fix: keep direct dependencies in requirements-dev.txt only."
    )


@pytest.mark.precommit
def test_hook_dependencies_match_requirements_dev() -> None:
    specs = requirement_specs(REQUIREMENTS_DEV)
    mismatched = []
    for dep in _hook_dependencies():
        name, _, version = dep.partition("==")
        expected = specs.get(normalize(name))
        if not version or expected != f"=={version}":
            mismatched.append(f"{dep} (requirements-dev.txt: {expected})")
    assert not mismatched, (
        f"❌ '{PRECOMMIT_HOOK_ID}' additional_dependencies differ from requirements-dev.txt "
        "(F21/F22):\n"
        + "\n".join(f" - {m}" for m in mismatched)
        + "\nFix: use the exact pins from requirements-dev.txt; bump both in the same commit."
    )


@pytest.mark.precommit
@pytest.mark.xfail(strict=True, reason="F21: contract pinned before the fix")
def test_pip_is_pinned_in_constraints() -> None:
    spec = requirement_specs(CONSTRAINTS_DEV).get("pip", "")
    assert spec.startswith("=="), (
        f"❌ pip is not pinned in {CONSTRAINTS_DEV.name} (F21): '{spec or 'missing'}'\n"
        "Fix: add 'pip==<version>'; make venv installs pip under the constraints file."
    )
