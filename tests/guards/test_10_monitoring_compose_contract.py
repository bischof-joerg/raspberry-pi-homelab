# Compose contract: VictoriaMetrics coverage must exist
# Key point: it’s valid for Grafana to use datasource type prometheus
# while talking to VictoriaMetrics (Prometheus API compatible).
# The ban should target Prometheus runtime (service/host/port), not the datasource type label.

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
    # Logs (if you use it) : add later
    # "victorialogs",
    # Dashboards
    "grafana",
    # Exporters
    "node-exporter",
    "cadvisor",
}

OPTIONAL_SERVICES = {
    "victorialogs",
}

BANNED_SERVICES = {
    "prometheus",
}


def _logging_enabled() -> bool:
    return os.environ.get("LOGGING_ENABLED", "0") == "1"


def test_compose_renders():
    assert COMPOSE_FILE.exists(), f"Missing {COMPOSE_FILE}"
    data = render_compose(COMPOSE_FILE, env_file=ENV_EXAMPLE if ENV_EXAMPLE.exists() else None)
    assert "services" in data and isinstance(data["services"], dict), "compose has no services"


def test_required_services_present_and_prometheus_absent():
    data = render_compose(COMPOSE_FILE, env_file=ENV_EXAMPLE if ENV_EXAMPLE.exists() else None)
    services = set(data["services"].keys())

    required = set(REQUIRED_SERVICES)
    if _logging_enabled():
        required |= OPTIONAL_SERVICES

    missing = sorted(required - services)
    assert not missing, "Missing required monitoring services:\n" + "\n".join(missing)

    present_banned = sorted(BANNED_SERVICES & services)
    assert not present_banned, "Banned services present:\n" + "\n".join(present_banned)


def test_grafana_datasource_is_not_prometheus():
    """
    Static guard: your provisioning should point Grafana at VictoriaMetrics
    (typically via a Prometheus-compatible endpoint, but not a 'prometheus' service).
    """
    # Adjust paths to your actual provisioning layout
    prov_dir = REPO_ROOT / "stacks/monitoring/grafana/provisioning/datasources"
    if not prov_dir.exists():
        return  # don’t fail if you manage Grafana differently

    ymls = sorted(list(prov_dir.rglob("*.yml")) + list(prov_dir.rglob("*.yaml")))
    assert ymls, f"No datasource provisioning files found in {prov_dir}"

    bad = []
    for f in ymls:
        txt = f.read_text(encoding="utf-8", errors="replace").lower()
        # We allow 'type: prometheus' because VictoriaMetrics speaks PromQL over Prometheus API.
        # But we reject URL pointing at a prometheus service/host.
        if "http://prometheus" in txt or "prometheus:9090" in txt:
            bad.append(f.relative_to(REPO_ROOT).as_posix())

    assert not bad, "Grafana datasources reference Prometheus:\n" + "\n".join(bad)
