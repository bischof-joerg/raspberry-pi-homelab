# Monitoring Stack – Container Roles & Persistence

This document describes the roles of all containers in the monitoring stack and their associated persistence.
It is based directly on the provided `docker-compose.yml` and is designed to run on a Raspberry Pi (ARM64).

---

## Architecture Overview

### Components

- **Prometheus** scrapes:
  - `node-exporter` (host node metrics)
  - `cAdvisor` (container metrics)
  - `docker engine` metrics via `http://<monitoring-gateway>:9323/metrics`
  - optional Grafana `/metrics`
- **Grafana** reads from Prometheus and provides dashboards.
- **Alertmanager** handles alerts fired by Prometheus.

### Docker networking (sustainable hardened setup)

Implementation goal:

- Shared, isolated network for all monitoring components
- Allows clean separation from other application stacks

A dedicated Docker bridge network is used with desired state:

- Docker network name: `monitoring`
- Linux bridge interface name: `br-monitoring`
- Subnet: `172.20.0.0/16`
- Gateway on host: `172.20.0.1`
- Docker Engine Metrics: reachable from containers in `monitoring` netzwork via `http://172.20.0.1:9323/metrics`
- No unused networks like `compose_default` (if not attached)
- No UFW rules on non-existent docker-bridge-interfaces

Prometheus scrapes Docker Engine metrics on the gateway IP:

- `http://172.20.0.1:9323/metrics`

This avoids relying on `host.docker.internal`, and it allows stable firewall rules referencing the fixed bridge interface.

### Verfication and Cleanup of Docker networks and UFW (hardening)

#### Background

n hardened setup, it can happen that old Docker Compose projects or previous Compose names leave behind an additional network such as `compose_default`.
In addition, outdated UFW rules may point to Docker bridge interfaces that no longer exist (e.g., `br-abe...`).

~~~text
An example that causes unintentional `compose_default` creation: docker compose up/down was run without a compose file in the current directory. To avoid: Always run compose from the correct directory (monitoring/compose) or with absoulte paths to the docker-compose.yml file.
~~~

A script is provided to validate and in case of discrepancies cleans up towards the above described **desired network state**.

#### Dry-run (no changes)

~~~bash
make cleanup-check
~~~

#### Apply changes (HANDLE carefully)

~~~bash
make cleanup-check --apply
~~~

---

## Details on Services

### Prometheus

**Role:**
Prometheus is the central time-series database for metrics. It scrapes metrics from exporters such as Node Exporter and cAdvisor and provides querying (PromQL) and alerting capabilities.

**Persistence:**

- **Time-series database (TSDB)**
  Stores all collected metrics.
  - Mount: `/prometheus`
- **Configuration (IaC, Git-managed)**
  Scrape targets, rules, and global settings.
  - Mount: `/etc/prometheus/prometheus.yml` (read-only)

**Note:**
Without persistence, all historical metrics are lost on restart.

---

### Alertmanager

**Role:**
Alertmanager handles alerts sent by Prometheus. It groups, deduplicates, and routes them to configured notification channels (e.g. email, messenger services).

**Persistence:**

- **Alert state & silences**
  Stores active silences and notification state.
  - Volume: `alertmanager-config`
- **Configuration (IaC, Git-friendly)**
  Routing rules and receivers.
  - Mount: `/etc/alertmanager/alertmanager.yml` (read-only)

**Note:**
Without persistence, silences and alert state are lost after restarts.

---

### Grafana

**Role:**
Grafana is the visualization layer. It provides dashboards, panels, and a web UI for metrics and logs from Prometheus and Loki.

**Persistence:**

- **Grafana database**
  Users, organizations, data sources, dashboards (if not provisioned).
  - Mount: `/var/lib/grafana`
- **Provisioning (IaC, optional)**
  Data sources and dashboards as code.
  - Mount: `/etc/grafana/provisioning` (read-only)

**Note:**
Grafana is the only service intentionally exposed to the outside.

---

### Loki

**Role:**
Loki is the log aggregation system. It stores logs efficiently and makes them searchable in Grafana using labels and LogQL.

**Persistence:**

- **Log chunks & index**
  Persistent log storage.
  - Mount: `/loki`
- **Configuration (IaC)**
  Storage backend, limits, schema.
  - Mount: `/etc/loki/loki.yml` (read-only)

**Note:**
Without persistence, log history is lost after restarts.

---

### Promtail

**Role:**
Promtail collects logs from the host and containers and forwards them to Loki.
It is responsible for parsing, labeling, and filtering logs.

**Persistence:**

- **Positions file**
  Tracks how far logs have already been read.
  - Mount: `/positions`
- **Host log access (required, not persistence)**
  - `/var/log:/var/log:ro`
  - `/var/lib/docker/containers:/var/lib/docker/containers:ro`
- **Configuration (IaC)**
  Pipeline stages and scrape targets.
  - Mount: `/etc/promtail/config.yml` (read-only)

**Note:**
Without persisted positions, log duplication or gaps may occur after restarts.

---

### Node Exporter

**Role:**
Exposes host system metrics such as CPU, memory, disk, and network usage.

**Persistence:**
None – this container is fully stateless.

**Required mounts (read-only):**

- `/proc`
- `/sys`
- Root filesystem (depending on configuration)

---

### cAdvisor

**Role:**
Provides container-level metrics (CPU, memory, I/O per container).
Complements Node Exporter with Docker/container visibility.

**Persistence:**
None – stateless.

**Required mounts (read-only):**

- `/var/lib/docker`
- `/sys`
- Root filesystem

**Note:**
Due to the required host mounts, cAdvisor is intentionally isolated and run with minimal privileges.

---

## Persistence Summary

### Stateful (volumes required)

- Prometheus (metrics)
- Grafana (UI data, users, dashboards)
- Loki (logs)
- Promtail (positions)
- Alertmanager (silences & alert state)

### Stateless

- Node Exporter
- cAdvisor

### Git-friendly / Infrastructure as Code

- Prometheus configuration & rules
- Alertmanager routing
- Loki & Promtail configuration
- Grafana provisioning & dashboard JSONs
