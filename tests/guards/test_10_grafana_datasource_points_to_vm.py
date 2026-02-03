from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASOURCES_DIR = REPO_ROOT / "stacks/monitoring/grafana/provisioning/datasources"


def _load_all_datasources() -> list[dict]:
    assert DATASOURCES_DIR.is_dir(), f"Grafana datasource provisioning dir missing: {DATASOURCES_DIR}"

    all_datasources: list[dict] = []

    for path in sorted(DATASOURCES_DIR.glob("*.yml")) + sorted(DATASOURCES_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        datasources = data.get("datasources", [])
        assert isinstance(datasources, list), f"'datasources' must be a list in {path}"

        for ds in datasources:
            assert isinstance(ds, dict), f"Invalid datasource entry in {path}: {ds!r}"
            ds["_source_file"] = path.relative_to(REPO_ROOT).as_posix()
            all_datasources.append(ds)

    assert all_datasources, "No Grafana datasources found at all"
    return all_datasources


def test_grafana_default_datasource_points_to_victoriametrics() -> None:
    datasources = _load_all_datasources()

    defaults = [d for d in datasources if d.get("isDefault") is True]
    assert len(defaults) == 1, f"Expected exactly one default datasource, found {len(defaults)}:\n" + "\n".join(
        f"- {d.get('name')} ({d.get('_source_file')})" for d in defaults
    )

    default = defaults[0]
    url = default.get("url")

    assert isinstance(url, str) and url.strip(), (
        f"Default datasource has no valid url (source={default.get('_source_file')})"
    )

    # Hard ban: Prometheus container endpoint
    assert "prometheus:9090" not in url, f"Default datasource still points to Prometheus: url={url!r}"

    # Positive assertion: VictoriaMetrics must be the backend
    assert "victoriametrics" in url, f"Default datasource does not point to VictoriaMetrics: url={url!r}"
