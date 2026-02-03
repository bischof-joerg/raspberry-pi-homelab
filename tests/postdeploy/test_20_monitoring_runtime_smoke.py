from __future__ import annotations

import os

import pytest
import yaml

from tests._lib.http import get_json, wait_http_ok

# Runtime smoke tests (Pi) for end-to-end “Prometheus replaced”
# Intended to run on the Pi after deploy. Use IPv4 loopback for determinism.

VM_URL = os.getenv("TEST_VM_URL", "http://127.0.0.1:8428")
VMAGENT_URL = os.getenv("TEST_VMAGENT_URL", "http://127.0.0.1:8429")
VMALERT_URL = os.getenv("TEST_VMALERT_URL", "http://127.0.0.1:8880")
ALERTMANAGER_URL = os.getenv("TEST_ALERTMANAGER_URL", "http://127.0.0.1:9093")
GRAFANA_URL = os.getenv("TEST_GRAFANA_URL", "http://127.0.0.1:3000")


def _parse_alertmanager_original_yaml(status_payload: dict) -> dict:
    """
    Alertmanager /api/v2/status in this setup provides:
      payload["config"]["original"] = "<alertmanager.yml as string>"

    We parse that YAML and return the dict.
    """
    cfg = status_payload.get("config")
    assert isinstance(cfg, dict), (
        f"Alertmanager status payload missing 'config' object. Top-level keys={list(status_payload.keys())}"
    )

    original = cfg.get("original")
    assert isinstance(original, str) and original.strip(), (
        f"Alertmanager status payload missing 'config.original' YAML string (got type={type(original).__name__})."
    )

    try:
        parsed = yaml.safe_load(original)
    except Exception as e:
        snippet = original[:400].replace("\n", "\\n")
        raise AssertionError(
            f"Failed to parse Alertmanager config.original as YAML: {e}. config.original snippet={snippet!r}"
        ) from e

    assert isinstance(parsed, dict), f"Parsed config.original is not a YAML mapping (got {type(parsed).__name__})"
    return parsed


@pytest.mark.postdeploy
def test_victoriametrics_health() -> None:
    wait_http_ok(f"{VM_URL}/health")
    wait_http_ok(f"{VM_URL}/api/v1/status/buildinfo")


@pytest.mark.postdeploy
def test_vmagent_health_and_targets() -> None:
    wait_http_ok(f"{VMAGENT_URL}/health")
    # Prometheus-style targets endpoint is commonly available; adjust if your vmagent differs.
    wait_http_ok(f"{VMAGENT_URL}/api/v1/targets")


@pytest.mark.postdeploy
def test_vmalert_health() -> None:
    wait_http_ok(f"{VMALERT_URL}/health")


@pytest.mark.postdeploy
def test_alertmanager_ready() -> None:
    wait_http_ok(f"{ALERTMANAGER_URL}/-/ready")


@pytest.mark.postdeploy
def test_alertmanager_has_configured_receivers() -> None:
    wait_http_ok(f"{ALERTMANAGER_URL}/-/ready")

    status = get_json(f"{ALERTMANAGER_URL}/api/v2/status")
    parsed_cfg = _parse_alertmanager_original_yaml(status)

    receivers = parsed_cfg.get("receivers")
    assert isinstance(receivers, list) and receivers, (
        f"Alertmanager config has no receivers (parsed from config.original). Top-level keys={list(parsed_cfg.keys())}"
    )

    bad_types = [r for r in receivers if not isinstance(r, dict)]
    assert not bad_types, f"Some receivers are not YAML mappings/dicts: {bad_types}"

    names = [r.get("name") for r in receivers if isinstance(r, dict)]
    assert any(isinstance(n, str) and n.strip() for n in names), (
        f"No receiver contains a non-empty 'name' field. Receivers={receivers}"
    )


@pytest.mark.postdeploy
def test_grafana_health() -> None:
    wait_http_ok(f"{GRAFANA_URL}/api/health")
    data = get_json(f"{GRAFANA_URL}/api/health")
    assert data.get("database") in {"ok", "OK"}, f"Grafana db not ok: {data}"
