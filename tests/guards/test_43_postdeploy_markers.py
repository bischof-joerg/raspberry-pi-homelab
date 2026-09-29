# tests/guards/test_43_postdeploy_markers.py
#
# R1.10 fix-forward: deploy.sh runs the postdeploy suite with `-m postdeploy`, so a test in
# tests/postdeploy without that marker is deselected on the Pi and never runs. make ci ignores
# tests/postdeploy, so nothing else notices. The seven checks of test_26_docker_socket_proxy.py
# were deselected on the first R1.10 deploy (2026-09-29) for exactly this reason.
#
# Every test function in tests/postdeploy must carry the marker: as a decorator
# `@pytest.mark.postdeploy`, or through a module-level `pytestmark` that includes it.

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
POSTDEPLOY_DIR = REPO_ROOT / "tests/postdeploy"


def _is_postdeploy_mark(node: ast.expr) -> bool:
    # Matches `pytest.mark.postdeploy`, also when called or listed.
    if isinstance(node, ast.Call):
        node = node.func
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "postdeploy"
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "mark"
    )


def _module_is_marked(tree: ast.Module) -> bool:
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "pytestmark" for t in stmt.targets
        ):
            values = (
                stmt.value.elts if isinstance(stmt.value, ast.List | ast.Tuple) else [stmt.value]
            )
            if any(_is_postdeploy_mark(v) for v in values):
                return True
    return False


def _unmarked_tests(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    if _module_is_marked(tree):
        return []
    return [
        f"{path.name}::{node.name}"
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name.startswith("test_")
        and not any(_is_postdeploy_mark(d) for d in node.decorator_list)
    ]


def _postdeploy_files() -> list[Path]:
    return sorted(POSTDEPLOY_DIR.glob("test_*.py"))


def test_postdeploy_files_exist() -> None:
    # Guards the guard: a moved directory would make the check below pass vacuously.
    assert len(_postdeploy_files()) >= 20, (
        f"❌ Found only {len(_postdeploy_files())} test files in {POSTDEPLOY_DIR}.\n"
        "Fix: update this guard if the postdeploy suite moved."
    )


@pytest.mark.xfail(strict=True, reason="R1.10: test_26 lacks the postdeploy marker")
def test_every_postdeploy_test_carries_the_marker() -> None:
    unmarked = [t for path in _postdeploy_files() for t in _unmarked_tests(path)]
    assert not unmarked, (
        "❌ Postdeploy tests without the `postdeploy` marker are deselected on the Pi:\n"
        + "\n".join(f" - {t}" for t in unmarked)
        + "\nFix: add `pytestmark = pytest.mark.postdeploy` to the module, "
        "or `@pytest.mark.postdeploy` to each test."
    )
