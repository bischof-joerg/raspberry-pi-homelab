# tests/postdeploy/test_23_grafana_dashboard_alerts_metrics.py
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

import pytest


def _grafana_base_url() -> str:
    return os.environ.get("GRAFANA_BASE_URL", "http://127.0.0.1:3000").strip().rstrip("/")


def _read_env_file(path: Path) -> dict[str, str]:
    """
    Minimal .env parser:
      - ignores empty lines and comments
      - parses KEY=VALUE (no shell expansion)
    """
    out: dict[str, str] = {}
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _load_monitoring_env_if_needed() -> None:
    """
    Ensure Grafana creds exist in os.environ.
    On target, we try to read /etc/raspberry-pi-homelab/monitoring.env directly.
    This avoids relying on import-time side effects in conftest.py.
    """
    if os.environ.get("GRAFANA_ADMIN_USER") and os.environ.get("GRAFANA_ADMIN_PASSWORD"):
        return

    env_path = Path("/etc/raspberry-pi-homelab/monitoring.env")
    if not env_path.exists():
        return

    try:
        vals = _read_env_file(env_path)
    except PermissionError:
        # If you want to run as non-root, you must grant read access (ACL) OR run pytest via sudo.
        return

    # Only set missing keys; do not override explicit environment.
    for k, v in vals.items():
        os.environ.setdefault(k, v)


def _grafana_headers() -> dict[str, str]:
    """
    Prefer token if present, else Basic Auth from admin creds.
    """
    token = os.environ.get("GRAFANA_API_TOKEN", "").strip()
    if token:
        return {"Authorization": f"Bearer {token}"}

    _load_monitoring_env_if_needed()
    user = os.environ.get("GRAFANA_ADMIN_USER", "").strip()
    pw = os.environ.get("GRAFANA_ADMIN_PASSWORD", "").strip()
    if not user or not pw:
        pytest.fail(
            "Missing Grafana credentials.\n"
            "Provide either:\n"
            "- GRAFANA_API_TOKEN, or\n"
            "- GRAFANA_ADMIN_USER + GRAFANA_ADMIN_PASSWORD\n"
            "On target these usually live in /etc/raspberry-pi-homelab/monitoring.env.\n"
            "If you run pytest as non-root, ensure that file is readable (ACL) or run via sudo."
        )

    basic = base64.b64encode(f"{user}:{pw}".encode()).decode("ascii")
    return {"Authorization": f"Basic {basic}"}


@pytest.mark.postdeploy
def test_grafana_dashboard_alerts_metrics_is_provisioned(http_get, retry) -> None:
    """
    Postdeploy smoke:
      - validates provisioning + mounts by asserting Grafana can load dashboard by UID via API

    Checks:
      - GET /api/dashboards/uid/<uid> returns 200
      - dashboard.uid matches expected
      - optional title sanity check (if configured)

    Env:
      - GRAFANA_BASE_URL (default http://127.0.0.1:3000)
      - GRAFANA_EXPECT_DASHBOARD_UID (default alerts-metrics)
      - GRAFANA_EXPECT_DASHBOARD_TITLE (default "Alerts (Metrics)")
      - GRAFANA_TIMEOUT_SECONDS (default 8)
      - Auth:
        - GRAFANA_API_TOKEN (preferred), OR
        - GRAFANA_ADMIN_USER/GRAFANA_ADMIN_PASSWORD (loaded from monitoring.env on target if readable)
    """
    base = _grafana_base_url()
    uid = os.environ.get("GRAFANA_EXPECT_DASHBOARD_UID", "alerts-metrics").strip()
    expected_title = os.environ.get("GRAFANA_EXPECT_DASHBOARD_TITLE", "Alerts (Metrics)").strip()
    timeout_s = int(float(os.environ.get("GRAFANA_TIMEOUT_SECONDS", "8")))

    url = f"{base}/api/dashboards/uid/{uid}"
    headers = _grafana_headers()

    def _assert_dashboard_present() -> None:
        status, body = http_get(url, headers=headers, timeout=timeout_s)

        # Grafana might be up (health=OK) but not fully ready/auth backends not stable yet.
        # We still fail hard after retry timeout if this persists.
        if status == 401:
            raise AssertionError(
                "Grafana API returned 401 Unauthorized.\n"
                f"url={url}\n"
                "This usually means wrong/missing creds.\n"
                "If running as non-root, ensure /etc/raspberry-pi-homelab/monitoring.env is readable "
                "(ACL) or run pytest via sudo; or set GRAFANA_API_TOKEN."
            )

        if status == 404:
            raise AssertionError(
                "Grafana API returned 404 Not Found for expected dashboard UID.\n"
                f"url={url}\nuid={uid}\n"
                "This usually means provisioning/mounts did not load the dashboard JSON.\n"
                "Check inside grafana container:\n"
                "- dashboard JSON exists under /var/lib/grafana/dashboards/alerts\n"
                "- dashboards provider points to that path\n"
                f"- the dashboard JSON sets uid={uid}"
            )

        if status != 200:
            raise AssertionError(
                f"Unexpected Grafana API status.\nurl={url}\nstatus={status}\nbody={body[:600]}"
            )

        try:
            payload: Any = json.loads(body)
        except Exception as e:
            raise AssertionError(
                f"Grafana returned non-JSON body: {e}\nurl={url}\nbody={body[:600]}"
            ) from e

        dash = payload.get("dashboard") if isinstance(payload, dict) else None
        if not isinstance(dash, dict):
            raise AssertionError(
                f"Unexpected Grafana response shape: {type(payload)} -> {str(payload)[:800]}"
            )

        got_uid = str(dash.get("uid", "")).strip()
        if got_uid != uid:
            raise AssertionError(f"Dashboard UID mismatch: expected={uid} got={got_uid}")

        got_title = str(dash.get("title", "")).strip()
        if expected_title and got_title != expected_title:
            raise AssertionError(
                f"Dashboard title mismatch: expected={expected_title!r} got={got_title!r}"
            )

    # provisioning is periodic; allow eventual consistency
    retry(_assert_dashboard_present, timeout_s=60, interval_s=2.5)
