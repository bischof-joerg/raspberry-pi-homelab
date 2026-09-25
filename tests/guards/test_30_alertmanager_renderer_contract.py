# tests/guards/test_30_alertmanager_renderer_contract.py
#
# Static guard for the Alertmanager config renderer (findings F26, F26b, F35, F39).
# The rendered alertmanager.yml may contain the SMTP password, so it must never be
# world-readable, and the renderer must fail loudly instead of swallowing errors.
# Reads the compose file as plain YAML: no Docker needed, no script is executed (C5).

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

COMPOSE_FILE = REPO_ROOT / "stacks/monitoring/compose/docker-compose.yml"
INIT_PERMISSIONS = REPO_ROOT / "stacks/monitoring/compose/init-permissions.sh"

RENDERER = "alertmanager-config-render"
ALERTMANAGER = "alertmanager"
# nobody:nogroup in the prom/alertmanager image and on Raspberry Pi OS.
ALERTMANAGER_USER = "65534:65534"
ALERTMANAGER_GID = "65534"

_XFAIL_R1_1 = pytest.mark.xfail(
    strict=True, reason="R1.1: contract pinned before the fix (F26, F26b, F35, F39)"
)


def _services() -> dict:
    data = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    return data["services"]


def _renderer_script() -> str:
    command = _services()[RENDERER]["command"]
    return "\n".join(command) if isinstance(command, list) else str(command)


@_XFAIL_R1_1
def test_renderer_does_not_swallow_errors() -> None:
    script = _renderer_script()
    bad = [p for p in ("|| true", "2>/dev/null") if p in script]
    assert not bad, (
        f"❌ {RENDERER} swallows errors via {bad} (F35).\n"
        "Fix: remove the suppression; guard the one legitimate case with an explicit [ -e ] test."
    )


@_XFAIL_R1_1
def test_renderer_writes_config_0640_and_nothing_world_readable() -> None:
    script = _renderer_script()
    widening = re.findall(r"chmod\s+(?:-R\s+)?(?:0?644|[ugo]*[ao][ugo]*\+r\w*)", script)
    assert not widening, (
        f"❌ {RENDERER} makes files world-readable: {widening} (F26).\n"
        "Fix: the rendered config holds the SMTP password; use mode 0640 and o= for templates."
    )
    assert re.search(r"chmod\s+0640\s", script), (
        f"❌ {RENDERER} does not set mode 0640 on the rendered alertmanager.yml (F26).\n"
        "Fix: chmod 0640 the rendered file before moving it into place."
    )


@_XFAIL_R1_1
def test_alertmanager_runs_as_nobody_nogroup() -> None:
    user = _services()[ALERTMANAGER].get("user")
    assert user == ALERTMANAGER_USER, (
        f"❌ {ALERTMANAGER} user is {user!r}, expected {ALERTMANAGER_USER!r} (F26).\n"
        "Fix: set it explicitly; the 0640 config is readable only through this group."
    )


@_XFAIL_R1_1
def test_renderer_group_matches_alertmanager_group() -> None:
    user = str(_services()[RENDERER].get("user", ""))
    assert user.split(":")[-1] == ALERTMANAGER_GID and ":" in user, (
        f"❌ {RENDERER} user is {user!r}; its group must be {ALERTMANAGER_GID} (F26).\n"
        f'Fix: user: "0:{ALERTMANAGER_GID}" so the rendered files get the Alertmanager group '
        "without CAP_CHOWN."
    )


@_XFAIL_R1_1
def test_renderer_script_is_english_only() -> None:
    script = _renderer_script()
    german = re.findall(r"\b(?:muss|nicht|und|ansprechen)\b|[äöüÄÖÜß]", script)
    assert not german, (
        f"❌ {RENDERER} script contains German text: {german} (F39, decision E6).\n"
        "Fix: translate the comment to English."
    )


@_XFAIL_R1_1
def test_init_permissions_restricts_alertmanager_config_dir() -> None:
    text = INIT_PERMISSIONS.read_text(encoding="utf-8")
    expected = [
        r'check_one "\$alertmanager_cfg_dir" "0" "\$prom_gid" "750"',
        r'chown -R "0:\$\{prom_gid\}" "\$alertmanager_cfg_dir"',
        r'chmod 0750 "\$alertmanager_cfg_dir"',
        r'chmod -R u\+rwX,g\+rX,o-rwx "\$alertmanager_cfg_dir"',
    ]
    missing = [p for p in expected if not re.search(p, text)]
    assert not missing, (
        "❌ init-permissions.sh does not reconcile alertmanager-config to root:nogroup 0750 "
        "without other-bits (F26, F26b).\n"
        "Missing patterns:\n" + "\n".join(f" - {p}" for p in missing) + "\n"
        "Fix: check and apply 0:$prom_gid mode 750 and strip other-bits recursively."
    )
