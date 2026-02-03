# How to run (GitOps flow)

## Local (WSL) – static guards

- Fast checks that do not need the Pi:

```bash
pytest -q tests/guards/test_00_no_prometheus_artifacts.py tests/guards/test_10_monitoring_compose_contract.py
```

## On Pi – post-deploy runtime smoke

Run after `sudo ./deploy.sh`:

```bash
export TEST_VM_URL="http://127.0.0.1:8428"
export TEST_VMAGENT_URL="http://127.0.0.1:8429"
export TEST_VMALERT_URL="http://127.0.0.1:8880"
export TEST_ALERTMANAGER_URL="http://127.0.0.1:9093"
export TEST_GRAFANA_URL="http://127.0.0.1:3000"

pytest -q tests/guards/test_20_monitoring_runtime_smoke.py
```

## Notes / decisions you should lock in

- **Ports/URLs**: pick one canonical access path for tests (localhost ports vs Traefik hostnames). Tests should be stable and not depend on DNS.
- **Datasource type**: It’s OK if Grafana datasource is type: prometheus while pointing to VictoriaMetrics. The guard should ban Prometheus host/service, not the label.
- **Dashboards “covered”**: the most reliable automated check is:
  - Grafana health is OK
  - provisioning directory exists
  - dashboards directory is non-empty
  - (optional) Grafana API lists dashboards by folder/uid (requires credentials; doable if you want)
