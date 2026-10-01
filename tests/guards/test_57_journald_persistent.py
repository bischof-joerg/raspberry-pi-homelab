# tests/guards/test_57_journald_persistent.py
#
# Finding F62 (R1.18): the Pi's journal is volatile, so every reboot erases the host's own record.
# Raspberry Pi OS ships /usr/lib/systemd/journald.conf.d/40-rpi-volatile-storage.conf with
# `Storage=volatile` (measured 2026-10-01, systemd 257). journald reads all drop-ins of all
# directories sorted by file name, and the last value wins, so the repository's drop-in must sort
# after it:
#   stacks/core/journald/60-homelab-persistent.conf -> /etc/systemd/journald.conf.d/
#   scripts/host/ensure-journald-persistent.sh installs it; deploy.sh calls it.
#
# The ensure script runs here only inside a tmp sandbox with stub systemctl/journalctl, so nothing
# touches the host. The runtime proof is tests/postdeploy/test_07_host_journald_persistent.py.

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from tests._lib.journald import effective_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
DROPIN = REPO_ROOT / "stacks/core/journald/60-homelab-persistent.conf"
ENSURE = REPO_ROOT / "scripts/host/ensure-journald-persistent.sh"
DEPLOY = REPO_ROOT / "deploy.sh"

DISTRO_DROPIN = "40-rpi-volatile-storage.conf"
VOLATILE = "[Journal]\nStorage=volatile\n"

STUB = """#!/bin/sh
echo "$(basename "$0") $*" >> "$STUB_LOG"
exit 0
"""


def _settings(text: str) -> dict[str, str]:
    return effective_settings(text)


# --- the drop-in ---------------------------------------------------------------------------------


def test_dropin_sets_persistent_storage_with_limits() -> None:
    settings = _settings(DROPIN.read_text(encoding="utf-8"))
    assert settings.get("Storage") == "persistent", (
        f"❌ {DROPIN.relative_to(REPO_ROOT)} sets Storage={settings.get('Storage')!r} (F62).\n"
        "Fix: `Storage=persistent` in the [Journal] section."
    )
    missing = [key for key in ("SystemMaxUse", "SystemKeepFree") if not settings.get(key)]
    assert not missing, (
        f"❌ {DROPIN.relative_to(REPO_ROOT)} lacks {missing} (F62).\n"
        "Fix: bound the persistent journal, so it cannot fill the disk."
    )


def test_dropin_sorts_after_the_distribution_dropin() -> None:
    assert DROPIN.is_file(), f"❌ {DROPIN.relative_to(REPO_ROOT)} is missing (F62)."
    assert DROPIN.name > DISTRO_DROPIN, (
        f"❌ {DROPIN.name} sorts before {DISTRO_DROPIN} (F62); journald applies drop-ins in file "
        "name order, so `Storage=volatile` would win.\nFix: rename it with a higher prefix."
    )


# --- effective configuration ---------------------------------------------------------------------


def _cat_config(*files: tuple[str, str]) -> str:
    """Text shaped like `systemd-analyze cat-config systemd/journald.conf`."""
    parts = ["# /etc/systemd/journald.conf\n[Journal]\n#Storage=auto\n#SystemMaxUse=\n"]
    parts += [f"\n# {path}\n{body}" for path, body in files]
    return "".join(parts)


def test_last_dropin_wins() -> None:
    ours = DROPIN.read_text(encoding="utf-8")
    text = _cat_config(
        (f"/usr/lib/systemd/journald.conf.d/{DISTRO_DROPIN}", VOLATILE),
        (f"/etc/systemd/journald.conf.d/{DROPIN.name}", ours),
    )
    assert _settings(text)["Storage"] == "persistent"
    reversed_text = _cat_config(
        (f"/etc/systemd/journald.conf.d/{DROPIN.name}", ours),
        (f"/usr/lib/systemd/journald.conf.d/{DISTRO_DROPIN}", VOLATILE),
    )
    assert _settings(reversed_text)["Storage"] == "volatile", (
        "❌ effective_settings does not let the last file win."
    )


def test_commented_defaults_and_other_sections_are_ignored() -> None:
    text = "[Journal]\n#Storage=auto\n; Storage=none\n[Other]\nStorage=none\n"
    assert _settings(text) == {}


def test_empty_assignment_resets_a_setting() -> None:
    assert "Storage" not in _settings("[Journal]\nStorage=volatile\nStorage=\n")


def test_systemd_merges_the_dropins_in_name_order(tmp_path: Path) -> None:
    if shutil.which("systemd-analyze") is None:
        pytest.skip("systemd-analyze not available; the merge check runs in WSL and CI (Ubuntu).")
    distro = tmp_path / "usr/lib/systemd/journald.conf.d"
    local = tmp_path / "etc/systemd/journald.conf.d"
    distro.mkdir(parents=True)
    local.mkdir(parents=True)
    (distro / DISTRO_DROPIN).write_text(VOLATILE, encoding="utf-8")
    shutil.copyfile(DROPIN, local / DROPIN.name)
    proc = subprocess.run(
        ["systemd-analyze", "--no-pager", f"--root={tmp_path}", "cat-config",
         "systemd/journald.conf"],
        text=True, capture_output=True, check=False,
    )  # fmt: skip
    assert proc.returncode == 0, f"❌ systemd-analyze cat-config failed:\n{proc.stderr}"
    assert _settings(proc.stdout).get("Storage") == "persistent", (
        f"❌ With {DISTRO_DROPIN} present, systemd's merge yields "
        f"Storage={_settings(proc.stdout).get('Storage')!r} (F62):\n{proc.stdout}"
    )


# --- the ensure script ---------------------------------------------------------------------------


@pytest.fixture
def sandbox(tmp_path: Path) -> dict[str, str]:
    root = tmp_path / "host"
    root.mkdir()
    bindir = tmp_path / "bin"
    bindir.mkdir()
    env = {
        "PATH": "/usr/bin:/bin",
        "HOMELAB_TEST_SANDBOX": str(root),
        "DROPIN_DST": str(root / f"etc/systemd/journald.conf.d/{DROPIN.name}"),
        "STUB_LOG": str(tmp_path / "calls.log"),
    }
    for name in ("systemctl", "journalctl"):
        stub = bindir / name
        stub.write_text(STUB, encoding="utf-8")
        stub.chmod(0o755)
        env[f"{name.upper()}_BIN"] = str(stub)
    return env


def _ensure(env: dict[str, str], mode: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(ENSURE), mode], env=env, cwd=REPO_ROOT, text=True, capture_output=True, check=False
    )


def _calls(env: dict[str, str]) -> list[str]:
    log = Path(env["STUB_LOG"])
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def test_apply_installs_the_dropin_and_restarts_journald(sandbox: dict[str, str]) -> None:
    proc = _ensure(sandbox, "apply")
    assert proc.returncode == 0, f"❌ ensure apply failed:\n{proc.stdout}{proc.stderr}"
    dst = Path(sandbox["DROPIN_DST"])
    assert dst.read_bytes() == DROPIN.read_bytes(), f"❌ {dst} differs from {DROPIN}."
    mode = stat.S_IMODE(dst.stat().st_mode)
    assert mode == 0o644, f"❌ {dst} has mode {mode:o}, expected 644."
    assert _calls(sandbox) == ["systemctl restart systemd-journald", "journalctl --flush"], (
        f"❌ After installing the drop-in the calls were {_calls(sandbox)} (F62).\n"
        "Fix: journald reads its configuration only at start — restart it, then flush the "
        "runtime journal to /var/log/journal."
    )


def test_second_apply_changes_nothing_and_does_not_restart(sandbox: dict[str, str]) -> None:
    assert _ensure(sandbox, "apply").returncode == 0
    Path(sandbox["STUB_LOG"]).unlink()
    before = Path(sandbox["DROPIN_DST"]).stat().st_mtime_ns
    proc = _ensure(sandbox, "apply")
    assert proc.returncode == 0, f"❌ Second apply failed:\n{proc.stderr}"
    assert Path(sandbox["DROPIN_DST"]).stat().st_mtime_ns == before, (
        "❌ The second apply rewrote an unchanged file (not idempotent)."
    )
    assert _calls(sandbox) == [], (
        f"❌ The second apply called {_calls(sandbox)} although nothing changed.\n"
        "Fix: restart journald only when the drop-in was installed."
    )
    assert "OK (no changes)" in proc.stdout, f"❌ No 'OK (no changes)' message:\n{proc.stdout}"


@pytest.mark.parametrize("drift", ["content", "mode"])
def test_check_detects_drift(sandbox: dict[str, str], drift: str) -> None:
    assert _ensure(sandbox, "apply").returncode == 0
    assert _ensure(sandbox, "check").returncode == 0, "❌ check fails right after apply."
    dst = Path(sandbox["DROPIN_DST"])
    if drift == "content":
        dst.write_text(dst.read_text(encoding="utf-8") + "Storage=volatile\n", encoding="utf-8")
    else:
        dst.chmod(0o664)
    proc = _ensure(sandbox, "check")
    assert proc.returncode != 0 and "DRIFT" in proc.stderr, (
        f"❌ check did not report {drift} drift of the drop-in (rc={proc.returncode}):\n"
        f"{proc.stdout}{proc.stderr}"
    )


def test_check_never_restarts_journald(sandbox: dict[str, str]) -> None:
    _ensure(sandbox, "check")
    assert _calls(sandbox) == [], f"❌ check called {_calls(sandbox)}; it must only read."


def test_sandbox_override_is_refused_for_host_paths(sandbox: dict[str, str]) -> None:
    host_dst = f"/etc/systemd/journald.conf.d/{DROPIN.name}"
    proc = _ensure({**sandbox, "DROPIN_DST": host_dst}, "apply")
    assert proc.returncode == 2, (
        f"❌ ensure apply accepted HOMELAB_TEST_SANDBOX with a destination outside it "
        f"(rc={proc.returncode}).\nFix: the test override must never reach a host path."
    )
    assert _calls(sandbox) == [], "❌ A refused run still called systemctl or journalctl."


@pytest.mark.skipif(os.geteuid() == 0, reason="needs a non-root user to prove the root check")
def test_apply_without_sandbox_requires_root() -> None:
    proc = _ensure({"PATH": "/usr/bin:/bin"}, "apply")
    assert proc.returncode == 2 and "root" in proc.stderr.lower(), (
        f"❌ ensure apply without root did not refuse (rc={proc.returncode}):\n{proc.stderr}"
    )


# --- wiring --------------------------------------------------------------------------------------


def _function(text: str, name: str) -> str:
    m = re.search(rf"^{name}\(\) \{{\n(.*?)^\}}", text, flags=re.MULTILINE | re.DOTALL)
    assert m, f"❌ deploy.sh has no function {name}().\nFix: add it."
    return m.group(1)


def test_deploy_ensures_the_dropin_before_journald_read_access() -> None:
    text = DEPLOY.read_text(encoding="utf-8")
    assert 'ENSURE_JOURNALD_PERSISTENT="${ENSURE_JOURNALD_PERSISTENT:-1}"' in text, (
        "❌ deploy.sh lacks the toggle ENSURE_JOURNALD_PERSISTENT defaulting to 1 (F62)."
    )
    assert '"$JOURNALD_PERSISTENT_SCRIPT" apply' in _function(text, "ensure_journald_persistent")
    main = _function(text, "main")
    steps = (
        "ensure_apt_boot_firmware_hook",
        "ensure_journald_persistent",
        "ensure_journald_read_access",
    )
    order = [main.find(step) for step in steps]
    assert -1 not in order and order == sorted(order), (
        "❌ main() must call ensure_journald_persistent after ensure_apt_boot_firmware_hook and "
        f"before ensure_journald_read_access (positions {dict(zip(steps, order, strict=True))}).\n"
        "Fix: the read-access step must see /var/log/journal/<machine-id>, which journald creates "
        "only once storage is persistent."
    )


def test_ensure_script_is_executable() -> None:
    rel = str(ENSURE.relative_to(REPO_ROOT))
    staged = subprocess.run(
        ["git", "ls-files", "-s", "--", rel], cwd=REPO_ROOT, text=True, capture_output=True
    ).stdout
    if staged:
        assert staged.startswith("100755"), f"❌ {rel} is tracked without mode 100755: {staged}"
    else:
        assert os.access(ENSURE, os.X_OK), f"❌ {rel} is not executable.\nFix: chmod +x {rel}"
