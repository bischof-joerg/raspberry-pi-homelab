# tests/postdeploy/test_08_host_sshd_hardening.py
#
# Finding F67 (R1.21): deploy.sh installs an sshd drop-in that turns off every forwarding and root
# login (scripts/host/ensure-sshd-hardening.sh). These checks prove on the Pi that the installed
# file equals the repository and that sshd's effective configuration for `admin` — with the Match
# blocks evaluated, which plain `sshd -T` does not do — carries every value. The static contract
# is tests/guards/test_61_sshd_hardening.py.

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from tests._helpers import REPO_ROOT, run
from tests._lib.sshd import HARDENING, effective_values

pytestmark = pytest.mark.postdeploy

ENSURE = REPO_ROOT / "scripts/host/ensure-sshd-hardening.sh"
INSTALLED = Path("/etc/ssh/sshd_config.d/10-homelab-hardening.conf")
# The connection spec the F67 measurement used; `admin` is the user the Match block names.
CONNECTION = "user=admin,host=rpi-hub,addr=127.0.0.1"


def test_sshd_dropin_matches_the_repository() -> None:
    res = run([str(ENSURE), "check"])
    assert res.returncode == 0, (
        f"❌ The sshd drop-in on the Pi differs from the repository (F67):\n"
        f"{res.stdout}{res.stderr}\nFix: sudo ./deploy.sh (it runs `{ENSURE.name} apply`)."
    )


def test_installed_sshd_dropin_is_root_owned() -> None:
    st = INSTALLED.stat()
    mode = stat.S_IMODE(st.st_mode)
    assert (st.st_uid, st.st_gid, mode) == (0, 0, 0o644), (
        f"❌ {INSTALLED}: owner {st.st_uid}:{st.st_gid} mode {mode:o}, expected 0:0 644 (F67).\n"
        "Fix: sudo ./deploy.sh."
    )


def test_effective_sshd_config_for_admin_is_hardened() -> None:
    res = run(["/usr/sbin/sshd", "-T", "-C", CONNECTION])
    assert res.returncode == 0, f"❌ sshd -T -C {CONNECTION} failed:\n{res.stderr}"
    values = effective_values(res.stdout)
    wrong = {key: values.get(key) for key, want in HARDENING.items() if values.get(key) != want}
    assert not wrong, (
        f"❌ sshd's effective configuration for {CONNECTION} differs (F67): {wrong}, "
        f"expected {HARDENING}.\nA Match block that sorts before the drop-in's `Match all`, or a "
        "drop-in sorting before 10-homelab-hardening.conf, overrides it.\n"
        "Fix: check `sudo sshd -T -C " + CONNECTION + "` and `grep -n Match /etc/ssh/sshd_config "
        "/etc/ssh/sshd_config.d/*.conf`."
    )
