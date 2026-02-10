from __future__ import annotations

from pathlib import Path

from tests._lib.compose import render_compose

REPO_ROOT = Path(__file__).resolve().parents[2]

COMPOSE_FILE = REPO_ROOT / "stacks/monitoring/compose/docker-compose.yml"
ENV_EXAMPLE = REPO_ROOT / "stacks/monitoring/compose/.env.example"

REQUIRED_SERVICES = {
    "victoriametrics",
    "vmagent",
    "vmalert",
    "alertmanager",
    "grafana",
    "node-exporter",
    "cadvisor",
    "victorialogs",
}

OPTIONAL_SERVICES = {}

# Policy: Prometheus runtime must not exist in the monitoring stack.
BANNED_SERVICES = {"prometheus"}


def test_compose_renders():
    assert COMPOSE_FILE.exists(), f"Missing {COMPOSE_FILE}"
    data = render_compose(COMPOSE_FILE, env_file=ENV_EXAMPLE if ENV_EXAMPLE.exists() else None)
    assert "services" in data and isinstance(data["services"], dict), "compose has no services"


def test_required_services_present_and_banned_absent():
    data = render_compose(COMPOSE_FILE, env_file=ENV_EXAMPLE if ENV_EXAMPLE.exists() else None)
    services = set(data["services"].keys())

    missing = sorted(REQUIRED_SERVICES - services)
    assert not missing, "Missing required monitoring services:\n" + "\n".join(missing)

    present_banned = sorted(BANNED_SERVICES & services)
    assert not present_banned, "Banned services present:\n" + "\n".join(present_banned)


def test_grafana_datasource_does_not_point_to_prometheus_runtime():
    """
    Static guard: Grafana may use datasource type 'prometheus' (PromQL compatibility),
    but its URL must not point at a Prometheus runtime service/host.
    """
    prov_dir = REPO_ROOT / "stacks/monitoring/grafana/provisioning/datasources"
    if not prov_dir.exists():
        return

    ymls = sorted(list(prov_dir.rglob("*.yml")) + list(prov_dir.rglob("*.yaml")))
    assert ymls, f"No datasource provisioning files found in {prov_dir}"

    bad = []
    for f in ymls:
        txt = f.read_text(encoding="utf-8", errors="replace").lower()
        if "http://prometheus" in txt or "https://prometheus" in txt or "prometheus:9090" in txt:
            bad.append(f.relative_to(REPO_ROOT).as_posix())

    assert not bad, "Grafana datasources reference Prometheus runtime:\n" + "\n".join(bad)
