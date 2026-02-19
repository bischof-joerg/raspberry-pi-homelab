# tests/postdeploy/test_55_monitoring_data_dir_permissions.py
#
# Postdeploy guardrail: verify monitoring persistent data directories on the host
# have the expected ownership (uid/gid) and permissions (mode), so bind-mount
# security posture and idempotent init-permissions do not regress.

from __future__ import annotations

import grp
import os
import pwd
import stat
from dataclasses import dataclass
from pathlib import Path

import pytest


def _on_target() -> bool:
    return os.environ.get("POSTDEPLOY_ON_TARGET", "") == "1"


def _mode_octal(path: Path) -> int:
    st = path.stat()
    return stat.S_IMODE(st.st_mode)


def _uid_gid(path: Path) -> tuple[int, int]:
    st = path.stat()
    return st.st_uid, st.st_gid


def _resolve_nobody_nogroup() -> tuple[int, int]:
    """
    Mirror init-permissions behavior:
    - user: nobody
    - group: prefer 'nogroup' if present, else nobody's primary gid
    """
    try:
        nobody = pwd.getpwnam("nobody")
    except KeyError as e:
        raise RuntimeError("Cannot resolve user 'nobody' on this host") from e

    try:
        nogroup = grp.getgrnam("nogroup")
        return nobody.pw_uid, nogroup.gr_gid
    except KeyError:
        # Fallback to nobody's primary group id
        return nobody.pw_uid, nobody.pw_gid


@dataclass(frozen=True)
class DirSpec:
    service: str
    path: Path
    mode: int
    uid: int
    gid: int


def _specs() -> list[DirSpec]:
    base = Path(os.environ.get("MONITORING_DATA_ROOT", "/srv/data/stacks/monitoring"))

    # Defaults follow init-permissions.sh semantics:
    # - Grafana: 472:472
    # - Vector: 65532:65532
    # - Alertmanager: nobody:<nogroup or nobody primary gid>
    # - Victoria*: default root:root, overridable via envs
    alert_uid, alert_gid = _resolve_nobody_nogroup()

    vm_uid = int(os.environ.get("VICTORIAMETRICS_UID", "0"))
    vm_gid = int(os.environ.get("VICTORIAMETRICS_GID", "0"))
    vl_uid = int(os.environ.get("VICTORIALOGS_UID", "0"))
    vl_gid = int(os.environ.get("VICTORIALOGS_GID", "0"))

    return [
        DirSpec("grafana", base / "grafana", 0o750, 472, 472),
        DirSpec("alertmanager", base / "alertmanager", 0o750, alert_uid, alert_gid),
        # Config artifact dir rendered by config-render job; intentionally 0755 root:root
        DirSpec("alertmanager-config", base / "alertmanager-config", 0o755, 0, 0),
        DirSpec("vector", base / "vector", 0o750, 65532, 65532),
        DirSpec("victoriametrics", base / "victoriametrics", 0o750, vm_uid, vm_gid),
        DirSpec("victorialogs", base / "victorialogs", 0o750, vl_uid, vl_gid),
    ]


@pytest.mark.postdeploy
@pytest.mark.parametrize("spec", _specs(), ids=lambda s: f"{s.service}:{s.path}")
def test_monitoring_data_dir_permissions(spec: DirSpec) -> None:
    if not _on_target():
        pytest.skip(
            "POSTDEPLOY_ON_TARGET is not set; this test is intended to run on the Pi target."
        )

    if not spec.path.exists():
        raise AssertionError(
            f"{spec.service}: expected directory does not exist: {spec.path}\n"
            f"Hint: run init-permissions.sh or deploy.sh to create it."
        )

    if not spec.path.is_dir():
        raise AssertionError(f"{spec.service}: expected a directory but got: {spec.path}")

    have_mode = _mode_octal(spec.path)
    have_uid, have_gid = _uid_gid(spec.path)

    errors: list[str] = []

    if have_mode != spec.mode:
        errors.append(f"mode: expected {spec.mode:04o}, got {have_mode:04o}")

    if (have_uid, have_gid) != (spec.uid, spec.gid):
        errors.append(f"owner: expected {spec.uid}:{spec.gid}, got {have_uid}:{have_gid}")

    if errors:
        raise AssertionError(
            f"{spec.service}: permissions/ownership mismatch for {spec.path}\n"
            + "\n".join(f"- {e}" for e in errors)
            + "\nHint: run: sudo bash stacks/monitoring/compose/init-permissions.sh"
        )


@pytest.mark.postdeploy
def test_monitoring_expected_data_directories_exist() -> None:
    """
    Guardrail: ensure the expected persistent monitoring directories exist on the host.
    This catches regressions where bind-mount targets are missing (layout drift).
    """
    if os.environ.get("POSTDEPLOY_ON_TARGET", "") != "1":
        pytest.skip(
            "POSTDEPLOY_ON_TARGET is not set; this test is intended to run on the Pi target."
        )

    # Reuse the same directory specs you already use for permission checks.
    missing: list[Path] = []
    not_dirs: list[Path] = []

    for spec in _specs():  # assumes your existing helper returns DirSpec entries
        if not spec.path.exists():
            missing.append(spec.path)
        elif not spec.path.is_dir():
            not_dirs.append(spec.path)

    if missing or not_dirs:
        msg = ["Expected monitoring data directories are missing or invalid:"]
        if missing:
            msg.append("Missing:")
            msg.extend([f"  - {p}" for p in missing])
        if not_dirs:
            msg.append("Not a directory:")
            msg.extend([f"  - {p}" for p in not_dirs])
        msg.append(
            "Hint: run: sudo bash stacks/monitoring/compose/init-permissions.sh (or sudo ./deploy.sh)"
        )
        raise AssertionError("\n".join(msg))
