import json
import os
from pathlib import Path
from urllib.parse import urlparse

import pytest
import requests

POSTDEPLOY_ON_TARGET = os.getenv("POSTDEPLOY_ON_TARGET") == "1"


pytestmark = pytest.mark.postdeploy


def _repo_root() -> Path:
    # tests/postdeploy/<file> -> repo root is 3 levels up
    return Path(__file__).resolve().parents[2]


def _load_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise AssertionError(f"Missing file: {p}") from e
    except json.JSONDecodeError as e:
        raise AssertionError(f"Invalid JSON in {p}: {e}") from e


def _required_keys_assertions(d: dict, *, where: str) -> None:
    # Keep these tight and actionable. Adjust if you intentionally change daemon defaults.
    required_top = {
        "default-cgroupns-mode",
        "metrics-addr",
        "experimental",
        "log-driver",
        "log-opts",
    }
    missing = sorted(k for k in required_top if k not in d)
    assert not missing, f"{where}: missing required top-level keys: {missing}"

    assert isinstance(d["log-opts"], dict), f"{where}: log-opts must be an object/dict"
    for k in ("max-size", "max-file"):
        assert k in d["log-opts"], f"{where}: log-opts missing key: {k}"


def _metrics_url_from_metrics_addr(metrics_addr: str) -> str:
    # metrics-addr is typically "IP:PORT". Convert to "http://HOST:PORT/metrics".
    # Handle "0.0.0.0:PORT" or "[::]:PORT" by probing localhost.
    host_port = metrics_addr.strip()

    # If someone configured a scheme already, keep it, otherwise add http://
    base = host_port if "://" in host_port else f"http://{host_port}"

    u = urlparse(base)
    host = u.hostname or ""
    port = u.port

    if port is None:
        raise AssertionError(f"metrics-addr has no port: {metrics_addr}")

    # Normalize wildcard binds for host-side probe
    if host in {"0.0.0.0", "::"} or host.startswith("[::]"):
        host = "127.0.0.1"

    return f"http://{host}:{port}/metrics"


@pytest.mark.skipif(not POSTDEPLOY_ON_TARGET, reason="POSTDEPLOY_ON_TARGET=1 required")
def test_docker_daemon_json_matches_repo_copy() -> None:
    repo = _repo_root()
    src = repo / "stacks/core/docker/daemon.json"
    dst = Path("/etc/docker/daemon.json")

    src_json = _load_json(src)
    dst_json = _load_json(dst)

    _required_keys_assertions(src_json, where=f"repo:{src}")
    _required_keys_assertions(dst_json, where=f"host:{dst}")

    # Exact semantic equality (ignores key order / whitespace)
    assert dst_json == src_json, (
        "Host docker daemon.json differs from repo copy.\n"
        f"repo: {src}\n"
        f"host: {dst}\n"
        "Fix by re-running deploy (or apply script) to converge."
    )


@pytest.mark.skipif(not POSTDEPLOY_ON_TARGET, reason="POSTDEPLOY_ON_TARGET=1 required")
def test_docker_metrics_endpoint_reachable_from_host() -> None:
    dst = Path("/etc/docker/daemon.json")
    cfg = _load_json(dst)
    _required_keys_assertions(cfg, where=f"host:{dst}")

    url = _metrics_url_from_metrics_addr(str(cfg["metrics-addr"]))

    try:
        r = requests.get(url, timeout=3)
    except requests.RequestException as e:
        raise AssertionError(f"Failed to reach Docker metrics endpoint: {url} ({e})") from e

    assert r.status_code == 200, f"Unexpected status from {url}: {r.status_code}"
    body = r.text

    # Keep it robust across Docker/BuildKit versions: accept any known marker.
    markers = (
        "# HELP ",
        "engine_daemon_engine_info",
        "builder_builds_failed_total",
    )
    assert any(m in body for m in markers), (
        f"Metrics response from {url} does not look like Prometheus text format.\n"
        f"Expected one of markers: {markers}\n"
        f"First 200 chars:\n{body[:200]!r}"
    )
