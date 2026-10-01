# tests/postdeploy/test_07_host_journald_persistent.py
#
# Finding F62 (R1.18): deploy.sh installs a journald drop-in with `Storage=persistent`
# (scripts/host/ensure-journald-persistent.sh), overriding Raspberry Pi OS's
# /usr/lib/systemd/journald.conf.d/40-rpi-volatile-storage.conf. These checks prove on the Pi that
# the installed file equals the repository, that systemd's merged configuration is persistent,
# and that journald writes to /var/log/journal. The static contract is
# tests/guards/test_57_journald_persistent.py. That a previous boot survives is proven only by an
# attended reboot (`journalctl --list-boots`), not here.

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from tests._helpers import REPO_ROOT, run

pytestmark = pytest.mark.postdeploy

ENSURE = REPO_ROOT / "scripts/host/ensure-journald-persistent.sh"
INSTALLED = Path("/etc/systemd/journald.conf.d/60-homelab-persistent.conf")


def test_journald_dropin_matches_the_repository() -> None:
    res = run([str(ENSURE), "check"])
    assert res.returncode == 0, (
        f"❌ The journald drop-in on the Pi differs from the repository (F62):\n"
        f"{res.stdout}{res.stderr}\nFix: sudo ./deploy.sh (it runs `{ENSURE.name} apply`)."
    )


def test_installed_dropin_is_root_owned() -> None:
    st = INSTALLED.stat()
    mode = stat.S_IMODE(st.st_mode)
    assert (st.st_uid, st.st_gid, mode) == (0, 0, 0o644), (
        f"❌ {INSTALLED}: owner {st.st_uid}:{st.st_gid} mode {mode:o}, expected 0:0 644 (F62).\n"
        "Fix: sudo ./deploy.sh."
    )


def test_effective_journald_storage_is_persistent() -> None:
    from tests._lib.journald import effective_settings

    res = run(["systemd-analyze", "--no-pager", "cat-config", "systemd/journald.conf"])
    assert res.returncode == 0, f"❌ systemd-analyze cat-config failed:\n{res.stderr}"
    storage = effective_settings(res.stdout).get("Storage")
    assert storage == "persistent", (
        f"❌ journald's merged configuration says Storage={storage!r}, expected 'persistent' "
        f"(F62). A drop-in sorting after {INSTALLED.name} overrides it:\n{res.stdout}\n"
        "Fix: rename the repository's drop-in so it sorts last."
    )


def test_journald_writes_to_var_log_journal() -> None:
    machine_id = Path("/etc/machine-id").read_text(encoding="utf-8").strip()
    journal = Path("/var/log/journal") / machine_id / "system.journal"
    assert journal.is_file(), (
        f"❌ {journal} does not exist (F62): journald still writes to /run/log/journal only, and "
        "the next reboot erases it.\nFix: sudo systemctl restart systemd-journald && "
        "sudo journalctl --flush; if it stays missing, check `journalctl -u systemd-journald`."
    )
