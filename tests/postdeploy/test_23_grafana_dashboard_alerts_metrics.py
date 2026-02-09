# tests/postdeploy/test_23_grafana_dashboard_alerts_metrics.py
from __future__ import annotations

import base64
import json
import os
from typing import Any

import pytest


def _basic_auth_header(user: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{password}".encode()).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def _grafana_base_url() -> str:
    return os.environ.get("GRAFANA_BASE_URL", "http://127.0.0.1:3000").strip().rstrip("/")


def _grafana_creds() -> tuple[str, str]:
    # conftest.py auto-loads /etc/raspberry-pi-homelab/monitoring.env if readable
    user = os.environ.get("GRAFANA_ADMIN_USER", "").strip()
    pw = os.environ.get("GRAFANA_ADMIN_PASSWORD", "").strip()
    if not user or not pw:
        pytest.fail(
            "Missing Grafana credentials. Expected GRAFANA_ADMIN_USER and "
            "GRAFANA_ADMIN_PASSWORD (on target these should be loaded by tests/postdeploy/conftest.py "
            "from /etc/raspberry-pi-homelab/monitoring.env if readable)."
        )
    return user, pw


@pytest.mark.postdeploy
def test_grafana_dashboard_alerts_metrics_is_provisioned(http_get, retry) -> None:
    """
    Postdeploy smoke:
    - validates provisioning + mounts by asserting Grafana can load dashboard by UID via API
    - uses shared postdeploy helpers: http_get + retry

    Requirements:
    - Grafana reachable at GRAFANA_BASE_URL (default http://127.0.0.1:3000)
    - Grafana admin creds available in env (loaded on target by conftest.py if possible)
    """
    base = _grafana_base_url()
    uid = os.environ.get("GRAFANA_EXPECT_DASHBOARD_UID", "alerts-metrics").strip()
    expected_title = os.environ.get("GRAFANA_EXPECT_DASHBOARD_TITLE", "Alerts (Metrics)").strip()
    timeout_s = int(float(os.environ.get("GRAFANA_TIMEOUT_SECONDS", "8")))

    user, pw = _grafana_creds()
    headers = _basic_auth_header(user, pw)

    url = f"{base}/api/dashboards/uid/{uid}"

    def _assert_dashboard_present() -> None:
        status, body = http_get(url, headers=headers, timeout=timeout_s)

        if status == 401:
            raise AssertionError(
                "Grafana API returned 401 Unauthorized.\n"
                f"url={url}\n"
                "Check GRAFANA_ADMIN_USER/GRAFANA_ADMIN_PASSWORD (and that monitoring.env is readable)."
            )

        if status == 404:
            raise AssertionError(
                "Grafana API returned 404 Not Found for expected dashboard UID.\n"
                f"url={url}\nuid={uid}\n"
                "This typically means provisioning/mounts did not load the dashboard JSON.\n"
                "Check:\n"
                "- dashboard JSON exists under /var/lib/grafana/dashboards/alerts\n"
                "- dashboards provider points to that path\n"
                "- the dashboard JSON sets uid=alerts-metrics"
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

    # Grafana provisioning is periodic; allow brief eventual consistency after deploy/start
    retry(_assert_dashboard_present, timeout_s=60, interval_s=2.5)
