# tests/guards/test_55_boot_firmware_hook.py
#
# Finding F60 (R1.15): /boot/firmware is mounted read-only (/etc/fstab on the Pi), so raspi-firmware's
# kernel and initramfs hooks fail inside dpkg and every APT run exits 1. An APT hook remounts the
# partition read-write only while dpkg runs:
#   stacks/core/apt/99homelab-boot-firmware    -> /etc/apt/apt.conf.d/99homelab-boot-firmware
#   scripts/host/homelab-boot-firmware.sh      -> /usr/local/sbin/homelab-boot-firmware (root copy)
#   scripts/host/ensure-apt-boot-firmware-hook.sh installs both; deploy.sh calls it.
#
# The helper runs here against stub findmnt/mount/logger that record every call, and the ensure
# script only inside a tmp sandbox, so nothing touches the host. The runtime proof is
# tests/postdeploy/test_06_host_boot_firmware.py.

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SNIPPET = REPO_ROOT / "stacks/core/apt/99homelab-boot-firmware"
HELPER = REPO_ROOT / "scripts/host/homelab-boot-firmware.sh"
ENSURE = REPO_ROOT / "scripts/host/ensure-apt-boot-firmware-hook.sh"
DEPLOY = REPO_ROOT / "deploy.sh"

HELPER_DST = "/usr/local/sbin/homelab-boot-firmware"
MOUNTPOINT = "/boot/firmware"
EXPECTED_DIRECTIVES = [
    f'DPkg::Pre-Invoke {{ "{HELPER_DST} rw"; }};',
    f'DPkg::Post-Invoke {{ "{HELPER_DST} ro"; }};',
]

pytestmark = pytest.mark.xfail(strict=True, reason="R1.15 (F60): APT hook not implemented yet")

STUB = """#!/bin/sh
echo "$(basename "$0") $*" >> "$STUB_LOG"
case "$(basename "$0")" in
  findmnt)
    [ "${STUB_FINDMNT_EXIT:-0}" = 0 ] || exit "$STUB_FINDMNT_EXIT"
    echo "$STUB_OPTIONS"
    ;;
  mount) exit "${STUB_MOUNT_EXIT:-0}" ;;
esac
exit 0
"""


# --- the apt.conf snippet ------------------------------------------------------------------------


def _directives() -> list[str]:
    lines = SNIPPET.read_text(encoding="utf-8").splitlines()
    return [
        " ".join(line.split())
        for line in lines
        if line.strip() and not line.lstrip().startswith("//")
    ]


def test_snippet_calls_only_the_root_owned_helper() -> None:
    directives = _directives()
    assert directives == EXPECTED_DIRECTIVES, (
        f"❌ {SNIPPET.relative_to(REPO_ROOT)} holds {directives} (F60).\n"
        f"Expected exactly: {EXPECTED_DIRECTIVES}\n"
        f"Fix: call the root-owned copy {HELPER_DST}, never a path in the checkout — the checkout "
        "belongs to admin, and APT runs its hooks as root."
    )


def test_snippet_parses_as_apt_configuration() -> None:
    if shutil.which("apt-config") is None:
        pytest.skip("apt-config not available; the parse check runs in WSL and CI (Ubuntu).")
    proc = subprocess.run(
        ["apt-config", "-c", str(SNIPPET), "dump"], text=True, capture_output=True, check=False
    )
    assert proc.returncode == 0, f"❌ apt-config cannot parse the snippet:\n{proc.stderr}"
    for value in (f'"{HELPER_DST} rw"', f'"{HELPER_DST} ro"'):
        assert value in proc.stdout, (
            f"❌ apt-config dump lacks {value} (F60).\nFix: check the snippet's apt.conf syntax."
        )


# --- the helper ----------------------------------------------------------------------------------


@pytest.fixture
def stubs(tmp_path: Path) -> dict[str, str]:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    env = {"PATH": "/usr/bin:/bin", "STUB_LOG": str(tmp_path / "calls.log")}
    for name in ("findmnt", "mount", "logger"):
        stub = bindir / name
        stub.write_text(STUB, encoding="utf-8")
        stub.chmod(0o755)
        env[f"{name.upper()}_BIN"] = str(stub)
    return env


def _helper(env: dict[str, str], arg: str, **extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(HELPER), arg], env={**env, **extra}, text=True, capture_output=True, check=False
    )


def _calls(env: dict[str, str], tool: str) -> list[str]:
    log = Path(env["STUB_LOG"])
    lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return [
        line.split(" ", 1)[1] if " " in line else "" for line in lines if line.split(" ")[0] == tool
    ]


@pytest.mark.parametrize(
    ("arg", "options", "expected"),
    [
        ("rw", "ro,nosuid,nodev,noexec,relatime", [f"-o remount,rw {MOUNTPOINT}"]),
        ("rw", "rw,nosuid,nodev,noexec,relatime", []),
        ("ro", "rw,nosuid,nodev,noexec,relatime", [f"-o remount,ro {MOUNTPOINT}"]),
        ("ro", "ro,nosuid,nodev,noexec,relatime", []),
    ],
)
def test_helper_remounts_only_on_a_difference(
    stubs: dict[str, str], arg: str, options: str, expected: list[str]
) -> None:
    proc = _helper(stubs, arg, STUB_OPTIONS=options)
    assert proc.returncode == 0, f"❌ helper {arg} failed:\n{proc.stdout}{proc.stderr}"
    calls = _calls(stubs, "mount")
    assert calls == expected, (
        f"❌ helper {arg} with the partition at '{options.split(',')[0]}' called mount {calls}, "
        f"expected {expected} (F60).\nFix: read `findmnt -no OPTIONS {MOUNTPOINT}` and remount "
        "only when the first option differs."
    )


def test_helper_logs_each_remount(stubs: dict[str, str]) -> None:
    assert _helper(stubs, "rw", STUB_OPTIONS="ro,nosuid").returncode == 0
    logged = _calls(stubs, "logger")
    assert any("-t homelab-boot-firmware" in call for call in logged), (
        f"❌ The helper remounted without a journal entry; logger calls: {logged} (F60).\n"
        "Fix: `logger -t homelab-boot-firmware` for every remount."
    )


def test_failed_read_write_remount_stops_apt(stubs: dict[str, str]) -> None:
    proc = _helper(stubs, "rw", STUB_OPTIONS="ro,nosuid", STUB_MOUNT_EXIT="32")
    assert proc.returncode == 1, (
        f"❌ helper rw exited {proc.returncode} although the remount failed (F60).\n"
        "Fix: exit 1, so APT stops before dpkg (DPkg::Pre-Invoke) instead of leaving a package "
        "half-configured again."
    )
    assert any("-p user.err" in call for call in _calls(stubs, "logger")), (
        "❌ The failed rw remount was not logged with priority user.err."
    )


def test_failed_read_only_remount_warns_but_lets_apt_finish(stubs: dict[str, str]) -> None:
    proc = _helper(stubs, "ro", STUB_OPTIONS="rw,nosuid", STUB_MOUNT_EXIT="32")
    assert proc.returncode == 0, (
        f"❌ helper ro exited {proc.returncode} on a busy partition (F60).\n"
        "Fix: warn and exit 0 — a failing DPkg::Post-Invoke fails the whole APT run, which is the "
        "F60 symptom. The postdeploy check reports a partition left read-write."
    )
    assert any("-p user.warning" in call for call in _calls(stubs, "logger")), (
        "❌ The failed ro remount was not logged with priority user.warning."
    )


def test_helper_does_nothing_without_the_mountpoint(stubs: dict[str, str]) -> None:
    proc = _helper(stubs, "rw", STUB_FINDMNT_EXIT="1")
    assert proc.returncode == 0, f"❌ helper failed without a mountpoint:\n{proc.stderr}"
    assert _calls(stubs, "mount") == [], "❌ The helper called mount although nothing is mounted."


def test_helper_rejects_an_invalid_argument(stubs: dict[str, str]) -> None:
    proc = _helper(stubs, "toggle", STUB_OPTIONS="ro")
    assert proc.returncode == 2, f"❌ helper toggle exited {proc.returncode}, expected 2 (usage)."
    assert _calls(stubs, "mount") == [], "❌ The helper called mount for an invalid argument."


# --- the ensure script ---------------------------------------------------------------------------


@pytest.fixture
def sandbox(tmp_path: Path) -> dict[str, str]:
    root = tmp_path / "host"
    root.mkdir()
    return {
        "PATH": "/usr/bin:/bin",
        "HOMELAB_TEST_SANDBOX": str(root),
        "APT_HOOK_DST": str(root / "etc/apt/apt.conf.d/99homelab-boot-firmware"),
        "HELPER_DST": str(root / "usr/local/sbin/homelab-boot-firmware"),
    }


def _ensure(env: dict[str, str], mode: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(ENSURE), mode], env=env, cwd=REPO_ROOT, text=True, capture_output=True, check=False
    )


def test_apply_installs_both_files_with_their_modes(sandbox: dict[str, str]) -> None:
    proc = _ensure(sandbox, "apply")
    assert proc.returncode == 0, f"❌ ensure apply failed:\n{proc.stdout}{proc.stderr}"
    for dst, src, mode in (
        (sandbox["APT_HOOK_DST"], SNIPPET, 0o644),
        (sandbox["HELPER_DST"], HELPER, 0o755),
    ):
        path = Path(dst)
        assert path.read_bytes() == src.read_bytes(), f"❌ {path} differs from {src}."
        actual = stat.S_IMODE(path.stat().st_mode)
        assert actual == mode, f"❌ {path} has mode {actual:o}, expected {mode:o}."


def test_second_apply_changes_nothing(sandbox: dict[str, str]) -> None:
    assert _ensure(sandbox, "apply").returncode == 0
    before = {k: Path(sandbox[k]).stat().st_mtime_ns for k in ("APT_HOOK_DST", "HELPER_DST")}
    proc = _ensure(sandbox, "apply")
    assert proc.returncode == 0, f"❌ Second apply failed:\n{proc.stderr}"
    after = {k: Path(sandbox[k]).stat().st_mtime_ns for k in ("APT_HOOK_DST", "HELPER_DST")}
    assert before == after, "❌ The second apply rewrote an unchanged file (not idempotent)."
    assert "OK (no changes)" in proc.stdout, f"❌ No 'OK (no changes)' message:\n{proc.stdout}"


@pytest.mark.parametrize("drift", ["content", "mode"])
def test_check_detects_drift(sandbox: dict[str, str], drift: str) -> None:
    assert _ensure(sandbox, "apply").returncode == 0
    assert _ensure(sandbox, "check").returncode == 0, "❌ check fails right after apply."
    helper = Path(sandbox["HELPER_DST"])
    if drift == "content":
        helper.write_text(helper.read_text(encoding="utf-8") + "# drift\n", encoding="utf-8")
    else:
        helper.chmod(0o775)
    proc = _ensure(sandbox, "check")
    assert proc.returncode != 0 and "DRIFT" in proc.stderr, (
        f"❌ check did not report {drift} drift of the helper (rc={proc.returncode}):\n"
        f"{proc.stdout}{proc.stderr}"
    )


def test_sandbox_override_is_refused_for_host_paths(sandbox: dict[str, str]) -> None:
    proc = _ensure({**sandbox, "HELPER_DST": HELPER_DST}, "apply")
    assert proc.returncode == 2, (
        f"❌ ensure apply accepted HOMELAB_TEST_SANDBOX with a destination outside it "
        f"(rc={proc.returncode}).\nFix: the test override must never reach a host path."
    )
    assert not Path(sandbox["APT_HOOK_DST"]).exists(), "❌ A refused run still installed a file."


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


def test_deploy_ensures_the_hook_before_compose() -> None:
    text = DEPLOY.read_text(encoding="utf-8")
    assert 'ENSURE_APT_BOOT_FIRMWARE_HOOK="${ENSURE_APT_BOOT_FIRMWARE_HOOK:-1}"' in text, (
        "❌ deploy.sh lacks the toggle ENSURE_APT_BOOT_FIRMWARE_HOOK defaulting to 1 (F60)."
    )
    assert '"$APT_BOOT_FIRMWARE_SCRIPT" apply' in _function(text, "ensure_apt_boot_firmware_hook")
    main = _function(text, "main")
    steps = ("ensure_docker_daemon_json", "ensure_apt_boot_firmware_hook", "up -d")
    order = [main.find(step) for step in steps]
    assert -1 not in order and order == sorted(order), (
        "❌ main() must call ensure_apt_boot_firmware_hook after ensure_docker_daemon_json and "
        f"before `compose up -d` (positions {dict(zip(steps, order, strict=True))}).\nFix: call it right "
        "after ensure_docker_daemon_json."
    )


@pytest.mark.parametrize("script", [HELPER, ENSURE], ids=["helper", "ensure"])
def test_scripts_are_executable(script: Path) -> None:
    rel = str(script.relative_to(REPO_ROOT))
    staged = subprocess.run(
        ["git", "ls-files", "-s", "--", rel], cwd=REPO_ROOT, text=True, capture_output=True
    ).stdout
    if staged:
        assert staged.startswith("100755"), f"❌ {rel} is tracked without mode 100755: {staged}"
    else:
        assert os.access(script, os.X_OK), f"❌ {rel} is not executable.\nFix: chmod +x {rel}"
