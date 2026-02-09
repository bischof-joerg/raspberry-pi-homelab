# tests/postdeploy/test_23_grafana_dashboard_alerts_metrics.py
from __future__ import annotations

import os
from typing import Any

import pytest
import requests


def _env_bool(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _grafana_base_url() -> str:
    # Default for on-target postdeploy tests (Grafana port is bound locally in your stack)
    return os.environ.get("GRAFANA_BASE_URL", "http://127.0.0.1:3000").strip().rstrip("/")


def _grafana_auth() -> tuple[str, str]:
    user = os.environ.get("GRAFANA_ADMIN_USER", "").strip()
    pw = os.environ.get("GRAFANA_ADMIN_PASSWORD", "").strip()
    if not user or not pw:
        pytest.fail(
            "Missing Grafana credentials in env. Expected GRAFANA_ADMIN_USER and "
            "GRAFANA_ADMIN_PASSWORD (typically sourced from /etc/raspberry-pi-homelab/monitoring.env)."
        )
    return (user, pw)


@pytest.mark.postdeploy
def test_grafana_dashboard_alerts_metrics_is_provisioned() -> None:
    """
    Validates Grafana provisioning + mounts by asserting the expected dashboard UID exists.

    Checks:
      - GET /api/dashboards/uid/<UID> returns 200
      - dashboard.uid matches
      - (optional) title sanity check

    Default:
      - runs only on target (POSTDEPLOY_ON_TARGET=1)

    Optional local:
      - set GRAFANA_BASE_URL + creds to point to a reachable Grafana.
    """
    on_target = _env_bool("POSTDEPLOY_ON_TARGET")
    has_url_override = bool(os.environ.get("GRAFANA_BASE_URL", "").strip())
    if not on_target and not has_url_override:
        pytest.skip("POSTDEPLOY_ON_TARGET!=1 and GRAFANA_BASE_URL not set")

    base = _grafana_base_url()
    auth = _grafana_auth()

    uid = os.environ.get("GRAFANA_EXPECT_DASHBOARD_UID", "alerts-metrics").strip()
    timeout_s = float(os.environ.get("GRAFANA_TIMEOUT_SECONDS", "5"))

    r = requests.get(
        f"{base}/api/dashboards/uid/{uid}",
        auth=auth,
        timeout=timeout_s,
    )

    if r.status_code == 401:
        pytest.fail(
            "Grafana API returned 401 Unauthorized. Verify credentials and that you sourced "
            "monitoring.env into the environment for this test.\n"
            f"base={base}\nuid={uid}"
        )

    if r.status_code == 404:
        pytest.fail(
            "Expected dashboard not found in Grafana (404). This usually means provisioning/mounts "
            "did not load the dashboard JSON.\n"
            f"base={base}\nuid={uid}\n"
            "Hint: check Grafana mounts for /etc/grafana/provisioning and /var/lib/grafana/dashboards, "
            "and the dashboards provider path for the Alerts folder."
        )

    r.raise_for_status()

    try:
        payload: Any = r.json()
    except Exception as e:  # pragma: no cover
        pytest.fail(f"Grafana returned non-JSON body: {e}\nBody: {r.text[:500]}")

    dash = payload.get("dashboard") if isinstance(payload, dict) else None
    if not isinstance(dash, dict):
        pytest.fail(f"Unexpected Grafana response shape: {type(payload)} -> {str(payload)[:800]}")

    got_uid = str(dash.get("uid", "")).strip()
    assert got_uid == uid, f"Dashboard UID mismatch: expected={uid} got={got_uid}"

    # Optional sanity: ensure it's the expected title (can be relaxed via env if you rename later)
    expected_title = os.environ.get("GRAFANA_EXPECT_DASHBOARD_TITLE", "Alerts (Metrics)").strip()
    got_title = str(dash.get("title", "")).strip()
    assert got_title == expected_title, (
        f"Dashboard title mismatch: expected={expected_title!r} got={got_title!r}"
    )
