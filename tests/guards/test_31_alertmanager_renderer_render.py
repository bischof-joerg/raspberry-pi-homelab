# tests/guards/test_31_alertmanager_renderer_render.py
#
# Runs stacks/monitoring/alertmanager/render-config.sh with the host's POSIX sh/awk in tmp_path
# (finding F36). Values containing YAML-significant characters must round-trip unchanged, a
# control character must abort the render without leaking the value, and the output must be
# 0640 with no temp file left behind. The real image (BusyBox) is covered by test_32.

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RENDER_SCRIPT = REPO_ROOT / "stacks/monitoring/alertmanager/render-config.sh"
TEMPLATE = REPO_ROOT / "stacks/monitoring/alertmanager/alertmanager.yml.tmpl"

pytestmark = pytest.mark.xfail(strict=True, reason="R1.2: contract pinned before the fix (F36, F8)")

# Deliberately hostile but printable values: quotes, backslashes, YAML indicators, shell and
# template metacharacters. None of them is a real credential.
FIXTURE = {
    "ALERT_EMAIL_TO": "ops+alerts@example.org",
    "ALERT_SMTP_FROM": 'Homelab "Pi" <pi@example.org>',
    "ALERT_SMTP_SMARTHOST": "smtp.example.org:587",
    "ALERT_SMTP_AUTH_USERNAME": "domain\\user: #1",
    "ALERT_SMTP_AUTH_PASSWORD": "p\"a\\s:s #w'o$rd {{ x }} & *y ! %z",
    "ALERT_SMTP_REQUIRE_TLS": "true",
}

YAML_KEYS = {
    "ALERT_EMAIL_TO": "to",
    "ALERT_SMTP_FROM": "from",
    "ALERT_SMTP_SMARTHOST": "smarthost",
    "ALERT_SMTP_AUTH_USERNAME": "auth_username",
    "ALERT_SMTP_AUTH_PASSWORD": "auth_password",
}


def _prepare(tmp_path: Path) -> tuple[Path, Path]:
    # Explicit: do not rely on how the host sh reports a missing script file.
    assert RENDER_SCRIPT.is_file(), f"❌ Missing {RENDER_SCRIPT} (F36).\nFix: extract the renderer."
    in_dir, out_dir = tmp_path / "in", tmp_path / "out"
    in_dir.mkdir()
    out_dir.mkdir()
    shutil.copy(TEMPLATE, in_dir / TEMPLATE.name)
    return in_dir, out_dir


def _render(
    tmp_path: Path, values: dict[str, str], enabled: str = "1"
) -> tuple[subprocess.CompletedProcess, Path]:
    in_dir, out_dir = _prepare(tmp_path)
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "ALERT_EMAIL_ENABLED": enabled,
        "RENDER_IN_DIR": str(in_dir),
        "RENDER_OUT_DIR": str(out_dir),
        "RENDER_GROUP": str(os.getgid()),
        **values,
    }
    proc = subprocess.run(
        ["sh", str(RENDER_SCRIPT)], env=env, text=True, capture_output=True, check=False
    )
    return proc, out_dir


def _receiver(config: dict, name: str) -> dict:
    return next(r for r in config["receivers"] if r["name"] == name)


def test_values_round_trip_through_yaml(tmp_path: Path) -> None:
    proc, out_dir = _render(tmp_path, FIXTURE)
    assert proc.returncode == 0, f"❌ render failed:\n{proc.stderr}\nFix: see render-config.sh."

    config = yaml.safe_load((out_dir / "alertmanager.yml").read_text(encoding="utf-8"))
    for receiver in ("email-critical", "email-warning"):
        email = _receiver(config, receiver)["email_configs"][0]
        wrong = {
            key: (email.get(key), FIXTURE[var])
            for var, key in YAML_KEYS.items()
            if email.get(key) != FIXTURE[var]
        }
        assert not wrong, (
            f"❌ {receiver}: values changed by rendering (got, want): {wrong} (F36).\n"
            'Fix: escape \\ and " before embedding values in double-quoted YAML scalars.'
        )
        assert email["require_tls"] is True and email["send_resolved"] is True


def test_disabled_email_renders_empty_receivers(tmp_path: Path) -> None:
    proc, out_dir = _render(tmp_path, {}, enabled="0")
    assert proc.returncode == 0, f"❌ render failed:\n{proc.stderr}"
    config = yaml.safe_load((out_dir / "alertmanager.yml").read_text(encoding="utf-8"))
    for receiver in ("email-critical", "email-warning"):
        got = _receiver(config, receiver)
        assert got.get("webhook_configs") == [] and "email_configs" not in got, (
            f"❌ {receiver} with ALERT_EMAIL_ENABLED=0: {got!r}\n"
            "Fix: render an empty webhook_configs list when email is disabled."
        )


@pytest.mark.parametrize(
    "bad", ["SENTINELA\nSENTINELB", "SENTINELC\tSENTINELD", "SENTINELE\rSENTINELF"], ids=repr
)
def test_control_characters_abort_without_leaking(tmp_path: Path, bad: str) -> None:
    values = {**FIXTURE, "ALERT_SMTP_AUTH_PASSWORD": bad}
    proc, out_dir = _render(tmp_path, values)
    assert proc.returncode != 0, (
        "❌ A control character in ALERT_SMTP_AUTH_PASSWORD was accepted (F36).\n"
        "Fix: reject values containing control characters before rendering."
    )
    assert "ALERT_SMTP_AUTH_PASSWORD" in proc.stderr, (
        f"❌ Error does not name the variable:\n{proc.stderr}"
    )
    leaked = [s for s in bad.split() if s in proc.stdout + proc.stderr]
    assert not leaked, f"❌ The rejected value leaked into the output: {leaked}"
    assert list(out_dir.iterdir()) == [], (
        f"❌ Files left in the output dir after a rejected render: {list(out_dir.iterdir())}"
    )


def test_output_mode_and_no_temp_file(tmp_path: Path) -> None:
    proc, out_dir = _render(tmp_path, FIXTURE)
    assert proc.returncode == 0, f"❌ render failed:\n{proc.stderr}"
    rendered = out_dir / "alertmanager.yml"
    mode = stat.S_IMODE(rendered.stat().st_mode)
    assert mode == 0o640, f"❌ {rendered.name} mode {mode:04o}, expected 0640 (F26)."
    leftovers = sorted(p.name for p in out_dir.iterdir() if p.name.endswith(".tmp"))
    assert not leftovers, f"❌ Temp files left behind: {leftovers}"
    exposed = sorted(
        str(p.relative_to(out_dir))
        for p in out_dir.rglob("*")
        if stat.S_IMODE(p.lstat().st_mode) & stat.S_IRWXO
    )
    assert not exposed, f"❌ Entries with other-bits: {exposed} (F26)."
