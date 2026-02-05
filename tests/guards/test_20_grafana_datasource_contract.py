# Compose contract: VictoriaMetrics coverage must exist.
# This guard checks the monitoring stack shape (services present) and that banned services are absent.

from __future__ import annotations

import os
from pathlib import Path

from tests._lib.compose import render_compose

REPO_ROOT = Path(__file__).resolve().parents[2]

COMPOSE_FILE = REPO_ROOT / "stacks/monitoring/compose/docker-compose.yml"

# For local WSL runs you can point to a dummy env file, since docker compose config
# will fail on missing vars. Keep it minimal & non-secret.
ENV_EXAMPLE = REPO_ROOT / "stacks/monitoring/compose/.env.example"

REQUIRED_SERVICES = {
    # Metrics storage/query
    "victoriametrics",
    # Scrape/shipper
    "vmagent",
    # Alerting rules evaluation
    "vmalert",
    # Alertmanager for notifications
    "alertmanager",
    # Dashboards
    "grafana",
    # Exporters
    "node-exporter",
    "cadvisor",
}

OPTIONAL_SERVICES = {
    "victorialogs",
}

# Policy: Prometheus runtime must not exist in this stack.
BANNED_SERVICES = {
    "prometheus",
}


def _logging_enabled() -> bool:
    return os.environ.get("LOGGING_ENABLED", "0") == "1"


def test_compose_renders():
    assert COMPOSE_FILE.exists(), f"Missing {COMPOSE_FILE}"
    data = render_compose(COMPOSE_FILE, env_file=ENV_EXAMPLE if ENV_EXAMPLE.exists() else None)
    assert "services" in data and isinstance(data["services"], dict), "compose has no services"


def test_required_services_present_and_banned_absent():
    data = render_compose(COMPOSE_FILE, env_file=ENV_EXAMPLE if ENV_EXAMPLE.exists() else None)
    services = set(data["services"].keys())

    required = set(REQUIRED_SERVICES)
    if _logging_enabled():
        required |= OPTIONAL_SERVICES

    missing = sorted(required - services)
    assert not missing, "Missing required monitoring services:\n" + "\n".join(missing)

    present_banned = sorted(BANNED_SERVICES & services)
    assert not present_banned, "Banned services present:\n" + "\n".join(present_banned)
