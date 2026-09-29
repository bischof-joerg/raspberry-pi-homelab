# Monitoring Stack – Container Roles & Persistence

This document describes the roles of all containers in the monitoring stack and their associated persistence.
It is based directly on the provided `docker-compose.yml` and is designed to run on a Raspberry Pi (ARM64).

---

## Architecture Overview

### Components

- **vmagent** scrapes:
  - `node-exporter` (host node metrics)
  - `cAdvisor` (container metrics)
  - `docker engine` metrics via `http://<monitoring-gateway>:9323/metrics`
  - optional Grafana `/metrics`
- **Grafana** reads from VictoriaMetrics and provides dashboards.
- **Alertmanager** handles alerts fired by vmalert.

### Docker networking (sustainable hardened setup)

Implementation goal including hardening:

- Shared, isolated network for all monitoring components
- Allows clean separation from other application stacks
- Only Grafana exposes a TCP port
- All other services are internal-only Docker network
- Read-only root filesystems where supported
- No container runs privileged; cAdvisor still runs as root with `pid: host` and the Docker
  socket ([ADR-0011](architecture/adr/ADR-0011-cadvisor-unprivileged.md)); vector reads the Docker
  API only through the filtering socket-proxy
  ([ADR-0012](architecture/adr/ADR-0012-docker-api-socket-proxy.md))
- Secrets never stored in Git
- Fixed Docker bridge + UFW rules

⚠ Security Note: Docker Engine metrics must

- never be bound to 0.0.0.0
- never be reachable from non-monitoring containers
- be protected by UFW rules limiting access to br-monitoring only

A dedicated Docker bridge network is used with desired state:

- Docker network name: `monitoring`
- Linux bridge interface name: `br-monitoring`
- Subnet: `172.20.0.0/16`
- Gateway on host: `172.20.0.1`
- Docker Engine Metrics: reachable from containers in `monitoring` netzwork via `http://172.20.0.1:9323/metrics`
- No unused networks like `compose_default` (if not attached)
- No UFW rules on non-existent docker-bridge-interfaces

vmagent scrapes Docker Engine metrics on the gateway IP:

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

### Alertmanager

**Role:**
Alertmanager handles alerts sent by vmalert. It groups, deduplicates, and routes them to configured notification channels (e.g. email, messenger services).

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
Grafana is the visualization layer. It provides dashboards, panels, and a web UI for metrics and logs from VictoriaMetrics.

**Persistence:**

- **Grafana database**
  Users, organizations, data sources, dashboards (if not provisioned).
  - Mount: `/var/lib/grafana`
- **Provisioning (IaC, optional)**
  Data sources and dashboards as code.
  - Mount: `/etc/grafana/provisioning` (read-only)

**Note:**
Grafana is the only service exposed on the host network.
All other services are only reachable inside the Docker monitoring network.

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
- `/sys` and `/sys/fs/cgroup`
- Root filesystem (`/:/rootfs`)
- `/etc/machine-id`
- Docker socket and containerd socket

**Privileges:**
cAdvisor runs without privileged mode, but as `user: root` with `pid: host` and the device
`/dev/kmsg`. It publishes no host port; vmagent scrapes it over the `monitoring` network. The
`:ro` socket mounts do not restrict the Docker API, so a compromise of cAdvisor is still a
compromise of the host. The decision, the baseline measurement and the metric families the
postdeploy tests require are recorded in
[ADR-0011](architecture/adr/ADR-0011-cadvisor-unprivileged.md), which supersedes
[ADR-0010](architecture/adr/ADR-0010-cadvisor-privileged-exception.md). cAdvisor cannot move to
socket-proxy for now: Docker on the Pi uses the containerd image store, and cAdvisor's Docker
integration then requires the containerd socket, which the proxy cannot filter (tried and
reverted on 2026-09-29, F57).

### socket-proxy

**Role:**
Filtering Docker API proxy (`wollomatic/socket-proxy`). vector's `docker_logs` source reads
container logs through it at `http://socket-proxy:2375` instead of mounting the Docker socket
(F30). It allows GET only, on `events`, `containers/json`, `containers/<id>/json` and
`containers/<id>/logs`, for the client `vector`; every other request is refused and logged as
`blocked request`.

**Persistence:**
None – stateless.

**Privileges:**
The only service with the Docker socket (`:ro`) and the Docker group; uid 65534, read-only root
filesystem, no capabilities, no published port. It joins only the internal network `docker-api`.
It is still host-root equivalent itself; what the proxy does not protect (container environments,
including secrets, are readable through `containers/<id>/json`) is recorded in
[ADR-0012](architecture/adr/ADR-0012-docker-api-socket-proxy.md).

---

## Persistence Summary

### Stateful (volumes required)

The following volumes must be included in host-level backups.

- VictoriaMetrics TSDB
- Grafana data
- Alertmanager state

Backup should be performed at filesystem level (outside Docker).
See the following backup and restore runbook
➡️ **[./BackupRestoreRunbook.md](./BackupRestoreRunbook.md)**

### Stateless

- Node Exporter
- cAdvisor
- socket-proxy

### Git-friendly / Infrastructure as Code

- VictoriaMetrics configuration & rules
- Alertmanager routing
- Loki & Promtail configuration
- Grafana provisioning & dashboard JSONs
