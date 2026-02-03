from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DS_FILE = REPO_ROOT / "stacks/monitoring/grafana/provisioning/datasources/prometheus.yml"


def test_grafana_default_datasource_does_not_point_to_prometheus() -> None:
    assert DS_FILE.exists(), f"Missing datasource provisioning file: {DS_FILE}"

    data = yaml.safe_load(DS_FILE.read_text(encoding="utf-8"))
    datasources = data.get("datasources", [])
    assert isinstance(datasources, list) and datasources, "No datasources defined"

    default = [d for d in datasources if isinstance(d, dict) and d.get("isDefault") is True]
    assert len(default) == 1, f"Expected exactly one default datasource, found {len(default)}"

    url = default[0].get("url")
    assert isinstance(url, str) and url.strip(), "Default datasource has no url"

    assert "prometheus:9090" not in url, f"Datasource still points to Prometheus: url={url!r}"
