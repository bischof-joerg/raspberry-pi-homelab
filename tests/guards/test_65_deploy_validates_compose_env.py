# tests/guards/test_65_deploy_validates_compose_env.py
#
# F31: a missing or empty Grafana admin credential must stop the deploy before it changes anything
# the stack depends on. The compose file interpolates both with `${VAR:?…}`
# (tests/precommit/test_30_compose_config.py); deploy.sh renders the stack with the host env file
# in validate_secrets_file(), so the failure comes before networks, permissions and containers.
#
# Static on purpose: deploy.sh is Pi-only and never executed here (C5).

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY = REPO_ROOT / "deploy.sh"


def _deploy() -> str:
    return DEPLOY.read_text(encoding="utf-8")


def _function(name: str) -> str:
    m = re.search(rf"^{name}\(\) \{{\n(.*?)^\}}", _deploy(), flags=re.MULTILINE | re.DOTALL)
    assert m, f"❌ deploy.sh has no function {name}().\nFix: add it."
    return m.group(1)


@pytest.mark.xfail(
    strict=True, reason="F31: validate_secrets_file checks the file, not its content"
)
def test_validate_secrets_file_renders_the_stack() -> None:
    body = _function("validate_secrets_file")
    assert re.search(r"^\s*compose config --quiet\b.*\|\| die ", body, flags=re.MULTILINE), (
        "❌ validate_secrets_file() does not render the stack with the host env file (F31).\n"
        f"Body:\n{body}\n"
        'Fix: end it with `compose config --quiet >/dev/null || die "…"`, so a missing '
        "variable that compose requires (`${VAR:?…}`) stops the deploy here."
    )


def test_secrets_are_validated_before_the_stack_changes() -> None:
    main = _function("main")
    steps = ["validate_secrets_file", "bootstrap_networks", "maybe_init_permissions", "up -d"]
    found = [main.find(step) for step in steps]
    assert -1 not in found and found == sorted(found), (
        f"❌ main() must call {steps[0]} before {', '.join(steps[1:])} (F31); "
        f"positions {dict(zip(steps, found, strict=True))}.\n"
        "Fix: keep validate_secrets_file ahead of every step that changes networks, data "
        "directories or containers."
    )
