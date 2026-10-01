# tests/guards/test_61_sshd_hardening.py
#
# Finding F67 (R1.21): the Pi's sshd allowed every forwarding for `admin` — the package's
# /etc/ssh/sshd_config ends with a hand-added `Match User admin` block setting AllowTcpForwarding
# and AllowAgentForwarding to yes — and root login with a key. Measured on the Pi 2026-10-01 with
# `sshd -T -C user=admin,...` on a copy of its configuration (OpenSSH 10.0p2): global values in a
# drop-in do not beat that Match block; a `Match all` block in the drop-in does, because the
# Include at the top of sshd_config reads it first and the first matching block wins.
#   stacks/core/ssh/10-homelab-hardening.conf -> /etc/ssh/sshd_config.d/
#   scripts/host/ensure-sshd-hardening.sh installs it; deploy.sh calls it.
#
# The ensure script runs here only inside a tmp sandbox with stub sshd/systemctl, so nothing
# touches the host. The runtime proof is tests/postdeploy/test_08_host_sshd_hardening.py.

from __future__ import annotations

import os
import re
import stat
import subprocess
from pathlib import Path

import pytest

from tests._lib.sshd import HARDENING, effective_values, parse_config

REPO_ROOT = Path(__file__).resolve().parents[2]
DROPIN = REPO_ROOT / "stacks/core/ssh/10-homelab-hardening.conf"
ENSURE = REPO_ROOT / "scripts/host/ensure-sshd-hardening.sh"
DEPLOY = REPO_ROOT / "deploy.sh"

CLOUD_INIT_DROPIN = "50-cloud-init.conf"

STUB = """#!/bin/sh
echo "$(basename "$0") $*" >> "$STUB_LOG"
case "$(basename "$0") $1" in
  "sshd -t") exit "${STUB_SSHD_RC:-0}" ;;
  "systemctl is-active") exit "${STUB_ACTIVE_RC:-0}" ;;
esac
exit 0
"""

RELOADED = [
    "sshd -t",
    "systemctl is-active --quiet ssh.service",
    "systemctl reload ssh.service",
]


# --- the drop-in ---------------------------------------------------------------------------------


def test_dropin_sets_the_hardening_globally() -> None:
    global_values, _ = parse_config(DROPIN.read_text(encoding="utf-8"))
    assert global_values == HARDENING, (
        f"❌ {DROPIN.relative_to(REPO_ROOT)} sets {global_values} globally, expected {HARDENING} "
        "(F67).\nFix: restore the values; tests/_lib/sshd.py HARDENING is the contract."
    )


def test_dropin_repeats_the_hardening_in_one_match_all_block() -> None:
    _, blocks = parse_config(DROPIN.read_text(encoding="utf-8"))
    assert blocks == [("all", HARDENING)], (
        f"❌ {DROPIN.relative_to(REPO_ROOT)} has the Match blocks {blocks}, expected exactly one "
        f"`Match all` with {HARDENING} (F67).\nWithout it, sshd_config's `Match User admin` "
        "block turns forwarding back on for admin (measured 2026-10-01)."
    )


def test_dropin_sorts_before_cloud_init() -> None:
    assert DROPIN.name < CLOUD_INIT_DROPIN, (
        f"❌ {DROPIN.name} sorts after {CLOUD_INIT_DROPIN} (F67); sshd takes the first value it "
        "reads, so a later drop-in loses.\nFix: rename it with a lower prefix."
    )


def test_parse_config_matches_sshd_semantics() -> None:
    text = (
        "# comment\nAllowTcpForwarding no\nallowtcpforwarding yes\n"
        "Match User admin\n  AllowTcpForwarding yes  # trailing\nMatch all\n  X11Forwarding no\n"
    )
    global_values, blocks = parse_config(text)
    assert global_values == {"allowtcpforwarding": "no"}
    assert blocks == [
        ("user admin", {"allowtcpforwarding": "yes"}),
        ("all", {"x11forwarding": "no"}),
    ]


def test_effective_values_parses_sshd_t_output() -> None:
    assert effective_values("permitrootlogin no\nallowtcpforwarding yes\n") == {
        "permitrootlogin": "no",
        "allowtcpforwarding": "yes",
    }


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
        "DROPIN_DST": str(root / f"etc/ssh/sshd_config.d/{DROPIN.name}"),
        "STUB_LOG": str(tmp_path / "calls.log"),
    }
    for name, var in (("sshd", "SSHD_BIN"), ("systemctl", "SYSTEMCTL_BIN")):
        stub = bindir / name
        stub.write_text(STUB, encoding="utf-8")
        stub.chmod(0o755)
        env[var] = str(stub)
    return env


def _ensure(env: dict[str, str], mode: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(ENSURE), mode], env=env, cwd=REPO_ROOT, text=True, capture_output=True, check=False
    )


def _calls(env: dict[str, str]) -> list[str]:
    log = Path(env["STUB_LOG"])
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def test_apply_installs_validates_and_reloads(sandbox: dict[str, str]) -> None:
    proc = _ensure(sandbox, "apply")
    assert proc.returncode == 0, f"❌ ensure apply failed:\n{proc.stdout}{proc.stderr}"
    dst = Path(sandbox["DROPIN_DST"])
    assert dst.read_bytes() == DROPIN.read_bytes(), f"❌ {dst} differs from {DROPIN}."
    mode = stat.S_IMODE(dst.stat().st_mode)
    assert mode == 0o644, f"❌ {dst} has mode {mode:o}, expected 644."
    assert _calls(sandbox) == RELOADED, (
        f"❌ After installing the drop-in the calls were {_calls(sandbox)}, expected {RELOADED} "
        "(F67).\nFix: validate with `sshd -t` first, then reload ssh.service."
    )


def test_second_apply_changes_nothing_and_does_not_reload(sandbox: dict[str, str]) -> None:
    assert _ensure(sandbox, "apply").returncode == 0
    Path(sandbox["STUB_LOG"]).unlink()
    before = Path(sandbox["DROPIN_DST"]).stat().st_mtime_ns
    proc = _ensure(sandbox, "apply")
    assert proc.returncode == 0, f"❌ Second apply failed:\n{proc.stderr}"
    assert Path(sandbox["DROPIN_DST"]).stat().st_mtime_ns == before, (
        "❌ The second apply rewrote an unchanged file (not idempotent)."
    )
    assert _calls(sandbox) == [], f"❌ The second apply called {_calls(sandbox)}."
    assert "OK (no changes)" in proc.stdout, f"❌ No 'OK (no changes)' message:\n{proc.stdout}"


def test_rejected_config_removes_a_new_dropin_and_does_not_reload(
    sandbox: dict[str, str],
) -> None:
    proc = _ensure({**sandbox, "STUB_SSHD_RC": "255"}, "apply")
    assert proc.returncode == 2 and "sshd -t rejected" in proc.stderr, (
        f"❌ apply did not fail on a rejected config (rc={proc.returncode}):\n{proc.stderr}"
    )
    assert not Path(sandbox["DROPIN_DST"]).exists(), (
        "❌ The rejected drop-in stayed installed (F67); the next sshd start would fail."
    )
    assert _calls(sandbox) == ["sshd -t"], (
        f"❌ A rejected config led to {_calls(sandbox)}; nothing may be reloaded."
    )


def test_rejected_config_restores_the_previous_dropin(sandbox: dict[str, str]) -> None:
    dst = Path(sandbox["DROPIN_DST"])
    dst.parent.mkdir(parents=True)
    dst.write_text("PermitRootLogin no\n", encoding="utf-8")
    dst.chmod(0o644)
    proc = _ensure({**sandbox, "STUB_SSHD_RC": "255"}, "apply")
    assert proc.returncode == 2, f"❌ apply did not fail (rc={proc.returncode}):\n{proc.stderr}"
    assert dst.read_text(encoding="utf-8") == "PermitRootLogin no\n", (
        "❌ A rejected config did not restore the previous drop-in (F67)."
    )


def test_inactive_unit_is_not_reloaded(sandbox: dict[str, str]) -> None:
    proc = _ensure({**sandbox, "STUB_ACTIVE_RC": "3"}, "apply")
    assert proc.returncode == 0, f"❌ apply failed with an inactive ssh.service:\n{proc.stderr}"
    assert _calls(sandbox) == RELOADED[:2], (
        f"❌ apply called {_calls(sandbox)} although ssh.service is not active."
    )


@pytest.mark.parametrize("drift", ["content", "mode"])
def test_check_detects_drift(sandbox: dict[str, str], drift: str) -> None:
    assert _ensure(sandbox, "apply").returncode == 0
    assert _ensure(sandbox, "check").returncode == 0, "❌ check fails right after apply."
    dst = Path(sandbox["DROPIN_DST"])
    if drift == "content":
        dst.write_text(dst.read_text(encoding="utf-8") + "AllowTcpForwarding yes\n", "utf-8")
    else:
        dst.chmod(0o664)
    proc = _ensure(sandbox, "check")
    assert proc.returncode != 0 and "DRIFT" in proc.stderr, (
        f"❌ check did not report {drift} drift of the drop-in (rc={proc.returncode}):\n"
        f"{proc.stdout}{proc.stderr}"
    )


def test_check_never_reloads(sandbox: dict[str, str]) -> None:
    _ensure(sandbox, "check")
    assert _calls(sandbox) == [], f"❌ check called {_calls(sandbox)}; it must only read."


def test_sandbox_override_is_refused_for_host_paths(sandbox: dict[str, str]) -> None:
    proc = _ensure({**sandbox, "DROPIN_DST": f"/etc/ssh/sshd_config.d/{DROPIN.name}"}, "apply")
    assert proc.returncode == 2, (
        f"❌ ensure apply accepted HOMELAB_TEST_SANDBOX with a destination outside it "
        f"(rc={proc.returncode}).\nFix: the test override must never reach a host path."
    )
    assert _calls(sandbox) == [], "❌ A refused run still called sshd or systemctl."


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


def test_deploy_ensures_the_dropin() -> None:
    text = DEPLOY.read_text(encoding="utf-8")
    assert 'ENSURE_SSHD_HARDENING="${ENSURE_SSHD_HARDENING:-1}"' in text, (
        "❌ deploy.sh lacks the toggle ENSURE_SSHD_HARDENING defaulting to 1 (F67)."
    )
    assert '"$SSHD_HARDENING_SCRIPT" apply' in _function(text, "ensure_sshd_hardening")
    assert re.search(r"^\s+ensure_sshd_hardening$", _function(text, "main"), re.MULTILINE), (
        "❌ deploy.sh main() does not call ensure_sshd_hardening (F67)."
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
