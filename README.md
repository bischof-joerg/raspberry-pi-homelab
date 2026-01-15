# raspberry-pi-homelab

Raspberry PI HomeLab Repro

## Monitoring Stack

The monitoring stack is implemented as an isolated Docker stack and provides:

- Host and container metrics (Prometheus, Node Exporter, cAdvisor)
- Centralized logging (Loki + Promtail)
- Dashboards and visualization (Grafana)
- Alert routing (Alertmanager)

📄 Architecture, container roles, and persistence details are documented here:  
➡️ **[monitoring/MonitoringStack.md](monitoring/monitoring.md)**


## Secrets

- Runtime secrets don't reside in repo, but root-only under: /etc/raspberry-pi-homelab/secrets.env (Mode 600, Owner root)

## Development Workflow

For a basis for reproducible deployments and exentension with additional services, the following principles are applied:
- Infrastructure as Code with:
  - editing sources on WSL
  - establishing tests befor committing to git, after deployed and to have sanity checks in addition. The execution is integrated as make steps - see the Makefile for details.
  - on PI only git pull and automated deployement followed by tests is done.
- Secure defaults and hardening is part of integrating new services
Details on the development workflow are availabe under:
➡️ **[DevWorkflow.md](DevWorkflow.md)**