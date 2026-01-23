# Raspberry Pi Homelab (Monitoring Stack)

The setup provides:

- services implemented as an isolated Docker stack
- hardened monitoring stack
- reproducible deployments (Infrastructure as Code)
- clean separation between code and data
- a stable, security-conscious network + firewall setup
- secure defaults (no unnecessary exposed UIs)
- a test suite (pre-commit + postdeploy)
- scalability for adding more household services

---

## Monitoring Stack

The monitoring stack is implemented as an isolated, hardened Docker stack and provides:

- Host and container metrics (Prometheus, Node Exporter, cAdvisor)
- Docker Engine metrics (dockerd `/metrics` on port 9323)
- Dashboards and visualization (Grafana)
- Alert routing (Alertmanager)
- Centralized logging (Loki + Promtail)

📄 Architecture, container roles, and persistence details are documented here:
➡️ **[monitoring/MonitoringStack.md](docs/monitoring.md)**

---

## Repository Layout (excerpt)

- `monitoring/compose/`
  - `docker-compose.yml`
- `monitoring/prometheus/`
  - `prometheus.yml`
  - `rules/`
- `monitoring/grafana/`
  - provisioning (datasources, dashboards)
- `tests/`
  - `precommit/` (static checks: yaml/json, gitleaks, promtool, compose config, etc.)
  - `postdeploy/` (runtime checks against the running stack)
- `scripts/`
  - `deploy.sh`
  - `cleanup-network-ufw.sh`

---

## Secrets and Configuration

Runtime secrets don't reside in repo, but root-only on Pi.

### On the Raspberry Pi

A root-owned env file at a fixed path not tracked in git:

- `/etc/raspberry-pi-homelab/.env` (Mode 600, Owner root)

**Example keys** (illustrative):

- `GRAFANA_ADMIN_USER=...`
- `GRAFANA_ADMIN_PASSWORD=...`
- `GHCR_USER=...`
- `GHCR_PAT=...`

### Permissions

Permissions are automatically checked by the deploy.sh script.

```bash
sudo chown root:root /etc/raspberry-pi-homelab/.env
sudo chmod 600 /etc/raspberry-pi-homelab/.env

---

## Development Workflow

For reproducible deployments and exentensibility with additional services, the following principles are applied:

- Infrastructure as Code with:
  - editing sources on WSL
    - For local development a repro local Python Virtual Environment '(.venv)' is used for tooling like '(pre-commit, pytest)' and automatically used by the make phases. The following commancds manually activate and deactive it:
    - to activate '(.venv)': ```source .venv/bin/activate```
    - to deactive in '(.venv)': ```deactivate```
  - tests
    - before committing to git - as GitHub pre-commit hook and additionally with dedicated repo specific tests
    - with deploy.sh checking afterwards with sanity checks.
    - The execution is integrated as make steps - see the Makefile for details.
  - on Pi only git pull and automated deployement followed by tests is done.
- Secure defaults and hardening is part of integrating new services

Details on the development workflow are availabe under:
➡️ **[DevWorkflow.md](DevWorkflow.md)**

## Update of Grafana Dashboards

Via dedicated scripts Grafana dashboards are downloaded, normalized and validated.

➡️ **[monitoring/grafana/grafana_dashboards.md](monitoring/grafana/grafana_dashboards.md)**
