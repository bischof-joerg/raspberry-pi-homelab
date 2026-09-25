# tests/guards/test_30_alertmanager_renderer_contract.py
#
# Static guard for the Alertmanager config renderer (findings F26, F26b, F35, F39).
# The rendered alertmanager.yml may contain the SMTP password, so it must never be
# world-readable, and the renderer must fail loudly instead of swallowing errors.
# Reads the compose file as plain YAML: no Docker needed, no script is executed (C5).

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

COMPOSE_FILE = REPO_ROOT / "stacks/monitoring/compose/docker-compose.yml"
INIT_PERMISSIONS = REPO_ROOT / "stacks/monitoring/compose/init-permissions.sh"
RENDER_SCRIPT = REPO_ROOT / "stacks/monitoring/alertmanager/render-config.sh"
RENDER_SCRIPT_IN_CONTAINER = "/in/render-config.sh"

RENDERER = "alertmanager-config-render"
ALERTMANAGER = "alertmanager"
# nobody:nogroup in the prom/alertmanager image and on Raspberry Pi OS.
ALERTMANAGER_USER = "65534:65534"
ALERTMANAGER_GID = "65534"


def _services() -> dict:
    data = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    return data["services"]


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return "\n".join(map(str, value)) if isinstance(value, list) else str(value)


def _renderer_script() -> str:
    """Inline command/entrypoint plus the extracted script, so no location escapes the checks."""
    service = _services()[RENDERER]
    parts = [_as_text(service.get("command")), _as_text(service.get("entrypoint"))]
    if RENDER_SCRIPT.is_file():
        parts.append(RENDER_SCRIPT.read_text(encoding="utf-8"))
    return "\n".join(parts)


PACKAGE_INSTALL = re.compile(
    r"\b(?:apk\s+add|apt-get\s+install|apt\s+install|yum\s+install|dnf\s+install|pip3?\s+install)\b"
)


def test_no_service_installs_packages_at_runtime() -> None:
    offenders = [
        name
        for name, service in _services().items()
        if PACKAGE_INSTALL.search(
            _as_text(service.get("command")) + "\n" + _as_text(service.get("entrypoint"))
        )
    ]
    if RENDER_SCRIPT.is_file() and PACKAGE_INSTALL.search(RENDER_SCRIPT.read_text("utf-8")):
        offenders.append(RENDER_SCRIPT.name)
    assert not offenders, (
        f"❌ Runtime package installation in: {offenders} (F8).\n"
        "Fix: use a pinned image that already contains the tools; deploys must not need a mirror."
    )


def test_renderer_runs_offline() -> None:
    service = _services()[RENDERER]
    assert service.get("network_mode") == "none" and "networks" not in service, (
        f"❌ {RENDERER}: network_mode is {service.get('network_mode')!r}, "
        f"networks is {service.get('networks')!r} (F8).\n"
        'Fix: network_mode: "none" and no networks: - the renderer needs no network.'
    )


def test_renderer_uses_the_alertmanager_image() -> None:
    services = _services()
    have, want = services[RENDERER].get("image"), services[ALERTMANAGER].get("image")
    assert have == want, (
        f"❌ {RENDERER} image is {have!r}, expected {want!r} (F8, F36).\n"
        "Fix: reuse the alertmanager image - it ships sh/awk and amtool, pinned and "
        "Renovate-covered together."
    )


def test_renderer_runs_extracted_script_read_only() -> None:
    service = _services()[RENDERER]
    assert RENDER_SCRIPT.is_file(), f"❌ Missing {RENDER_SCRIPT} (F36).\nFix: extract the renderer."
    assert service.get("entrypoint") == ["/bin/sh", RENDER_SCRIPT_IN_CONTAINER], (
        f"❌ {RENDER_SCRIPT_IN_CONTAINER} not run as entrypoint: "
        f"entrypoint={service.get('entrypoint')!r}, command={service.get('command')!r} (F36).\n"
        f'Fix: entrypoint: ["/bin/sh", "{RENDER_SCRIPT_IN_CONTAINER}"] and no inline command.'
    )
    assert "command" not in service, f"❌ {RENDERER}: drop the inline command (F36)."
    mount = f"../alertmanager/{RENDER_SCRIPT.name}:{RENDER_SCRIPT_IN_CONTAINER}:ro"
    assert mount in service.get("volumes", []), (
        f"❌ {RENDER_SCRIPT.name} is not mounted read-only (F36).\nFix: add volume {mount!r}."
    )
    assert service.get("read_only") is True, (
        f"❌ {RENDERER} has a writable root filesystem; without apk it needs none (F8).\n"
        "Fix: read_only: true (only the /out bind mount is written)."
    )


def test_renderer_does_not_swallow_errors() -> None:
    script = _renderer_script()
    bad = [p for p in ("|| true", "2>/dev/null") if p in script]
    assert not bad, (
        f"❌ {RENDERER} swallows errors via {bad} (F35).\n"
        "Fix: remove the suppression; guard the one legitimate case with an explicit [ -e ] test."
    )


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


def test_alertmanager_runs_as_nobody_nogroup() -> None:
    user = _services()[ALERTMANAGER].get("user")
    assert user == ALERTMANAGER_USER, (
        f"❌ {ALERTMANAGER} user is {user!r}, expected {ALERTMANAGER_USER!r} (F26).\n"
        "Fix: set it explicitly; the 0640 config is readable only through this group."
    )


def test_renderer_keeps_primary_group_root() -> None:
    # uid 0 owns /out (root:nogroup 0750). The Alertmanager group comes from group_add, not
    # from the primary group: "0:65534" made `apk add` exit 10 on the first R1.1 deploy.
    user = str(_services()[RENDERER].get("user", ""))
    assert user == "0:0", (
        f"❌ {RENDERER} user is {user!r}, expected '0:0' (F26).\n"
        "Fix: user 0:0 and get the Alertmanager group via group_add."
    )


def test_renderer_can_hand_files_to_alertmanager_group() -> None:
    service = _services()[RENDERER]
    groups = [str(g) for g in service.get("group_add", [])]
    assert ALERTMANAGER_GID in groups, (
        f"❌ {RENDERER} group_add is {groups!r}; it must contain {ALERTMANAGER_GID} (F26).\n"
        f'Fix: group_add: ["{ALERTMANAGER_GID}"] - an owner may chgrp to a supplementary group '
        "without CAP_CHOWN."
    )
    script = _renderer_script()
    default_group = f'group="${{RENDER_GROUP:-{ALERTMANAGER_GID}}}"'
    assert default_group in script and re.search(r'chgrp\s+"\$group"\s', script), (
        f"❌ {RENDER_SCRIPT.name} does not chgrp the output to RENDER_GROUP "
        f"(default {ALERTMANAGER_GID}) (F26).\n"
        f'Fix: {default_group} and chgrp "$group" before the rename; id -g is the primary '
        "group 0."
    )


def test_renderer_sets_restrictive_umask_before_writing() -> None:
    script = _renderer_script()
    umask, first_write = script.find("umask 027"), script.find('>"$tmp"')
    assert umask != -1 and first_write != -1 and umask < first_write, (
        f"❌ {RENDER_SCRIPT.name}: umask 027 missing or set after the first write (F26).\n"
        "Fix: set umask 027 before rendering to the temp file."
    )


def test_renderer_script_is_english_only() -> None:
    script = _renderer_script()
    german = re.findall(r"\b(?:muss|nicht|und|ansprechen)\b|[äöüÄÖÜß]", script)
    assert not german, (
        f"❌ {RENDERER} script contains German text: {german} (F39, decision E6).\n"
        "Fix: translate the comment to English."
    )


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
