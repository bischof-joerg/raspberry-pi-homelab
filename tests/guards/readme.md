# How to run (GitOps flow)

## Local (WSL) – static guards

Fast checks that do not need the Pi:

```bash
pytest -q tests/guards/test_00_no_prometheus_artifacts.py tests/guards/test_10_monitoring_compose_contract.py
