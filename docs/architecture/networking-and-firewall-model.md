# Networking & Firewall Model

It's the implementation of Architecture Decision Record [ADR-0001-networking-and-firewall.md](./adr/ADR-0001-networking-and-firewall.md).

This implementation itself is tested by post-deploy test `tests/postdeploy/test_35_network_and_ufw.py`.

This document describes the **networking and firewall operating model** for the Raspberry Pi homelab.
It defines how Docker networks are created, validated, cleaned up, and protected by UFW, and how these steps are integrated into the GitOps deployment flow.

The design prioritizes:

- Determinism
- Idempotency
- Least privilege
- No manual drift on the host

---

## 1. Network Topology Overview

### Networks

| Network     | Type      | Purpose |
|------------|-----------|---------|
| `monitoring` | external | Monitoring plane: VictoriaMetrics, vmagent, vmalert, VictoriaLogs, Grafana, exporters |
| `apps`       | external | Application plane: app stacks (Home Assistant, AdGuard, etc.) |

### Design principles

- Networks are **external** and **shared**.
- Docker Compose **references** networks but does **not create or modify** them.
- Network lifecycle is managed explicitly via scripts.
- Monitoring components communicate **only** via the `monitoring` network.
- Applications never access monitoring components unless explicitly required.

---

## 2. Docker Network Definitions

### Canonical names

| Logical name | Docker network name |
|-------------|---------------------|
| monitoring  | `monitoring` |
| apps        | `apps` |

### Docker Compose (example)

```yaml
networks:
  monitoring:
    external: true
    name: monitoring
  apps:
    external: true
    name: apps
```

> Compose files **must not** define `driver`, `ipam`, or bridge options for external networks.

---

## 3. Network Bootstrap (`bootstrap-networks.sh`)

### Purpose

`bootstrap-networks.sh` ensures that all **external Docker networks required by the stack exist before deployment**.

It is:

- Idempotent
- Safe to run repeatedly
- Explicitly guarded against subnet overlap
- GitOps-compatible

### Responsibilities

- Verify that required networks exist (`monitoring`, `apps`)
- Create missing networks (optional)
- Validate subnet, gateway, and bridge name if configured
- Refuse creation if the requested subnet overlaps existing Docker networks

### Default behavior

```bash
sudo scripts/bootstrap-networks.sh
```

- Creates missing networks
- Does **not** modify existing networks
- Does **not** delete anything

### Optional strict validation

```bash
export MONITORING_SUBNET=172.20.0.0/16
export MONITORING_GATEWAY=172.20.0.1
export MONITORING_BRIDGE_NAME=br-monitoring
sudo scripts/bootstrap-networks.sh
```

If the existing network does not match these values, the script fails.

### Dry run

```bash
DRY_RUN=1 sudo scripts/bootstrap-networks.sh
```

---

## 4. Firewall Model (UFW)

### Goals

- Restrict host-level access to Docker bridge interfaces
- Allow only **explicit, required traffic**
- Automatically remove stale rules caused by removed Docker networks

### Required rule (steady state)

Docker Engine metrics must be reachable **only from the monitoring network**:

```bash
ufw allow in on br-monitoring from 172.20.0.0/16 to any port 9323 proto tcp
```

This enables:

- vmagent → Docker Engine metrics
- No exposure to other networks or the host LAN

---

## 5. Network & UFW Cleanup (`cleanup-network-ufw.sh`)

### Purpose

`cleanup-network-ufw.sh` reconciles the **actual system state** with the expected steady state.

It is intentionally conservative.

### What it does

#### Docker networks

- Removes **unused** Docker networks matching a strict allowlist (e.g. `compose_default`)
- Never removes:
  - Networks with attached containers
  - The `monitoring` network
  - Networks belonging to the current Compose project

#### UFW rules

- Backs up current UFW state
- Removes rules that:
  - Reference non-existent bridge interfaces **and**
  - Match known stale bridge name patterns
- Ensures the required `br-monitoring → 9323/tcp` rule exists
- Optionally removes overly broad `ALLOW Anywhere` rules when a subnet-scoped rule is present

### Execution modes

Dry run (default):

```bash
sudo scripts/cleanup-network-ufw.sh
```

Apply changes:

```bash
sudo scripts/cleanup-network-ufw.sh --apply
```

Verbose:

```bash
sudo scripts/cleanup-network-ufw.sh --apply --verbose
```

---

## 6. Integration into `deploy.sh`

### Order of operations

The deployment pipeline enforces a strict sequence:

1. Sanity & prerequisite checks
2. **Network bootstrap**
3. Permissions initialization
4. Docker Compose pull + up
5. Post-deploy tests

### Integration point

```bash
check_prereqs
validate_secrets_file

bootstrap_networks   # ensures monitoring + apps exist

maybe_init_permissions
```

### Why this matters

- `docker compose up` never creates networks implicitly
- Network failures are caught **before** any containers start
- IPAM overlap errors are prevented deterministically
- Firewall expectations remain stable across deployments

---

## 7. Failure Modes & Guardrails

### Subnet overlap

If a requested subnet overlaps an existing Docker network:

- `bootstrap-networks.sh` **fails fast**
- Deployment stops before any mutation

### Network drift

- Compose does not manage networks → no accidental recreation
- Cleanup script removes only provably stale artifacts

### Firewall safety

- UFW rules are only removed if the interface no longer exists
- Backups are created before any UFW mutation

---

## 8. Verification Checklist

After deployment:

```bash
# Networks exist
docker network inspect monitoring >/dev/null
docker network inspect apps >/dev/null

# Bridge + subnet
docker network inspect monitoring | jq '.[0].Options, .[0].IPAM.Config'

# UFW rule
ufw status | grep 9323

# Monitoring connectivity
docker exec -it homelab-home-prod-mon-vmagent-1 \
  sh -lc 'getent hosts victorialogs && wget -qO- http://victorialogs:9428/metrics | head'

# Scrape health
curl -fsS http://127.0.0.1:8428/api/v1/query \
  -d 'query=up{job="victorialogs"}'
```

---

## 9. Design Rationale

- Docker networking is **stateful and global**
- Compose is **not** a safe place to manage IPAM long-term
- Explicit bootstrap + cleanup provides:
  - Predictability
  - Auditable changes
  - Clear ownership boundaries
- Firewall rules must follow **actual bridge interfaces**, not assumptions

This model prevents:

- Accidental network recreation
- IP range collisions
- Silent firewall exposure
- Heisenbugs caused by implicit Docker behavior

---

## 10. Summary

- Networks are **external, explicit, and validated**
- Firewall rules are **minimal, interface-bound, and reconciled**
- Deployment is **deterministic and GitOps-safe**
- Cleanup is **conservative and reversible**

The networking layer is treated as a **first-class, testable part of the infrastructure**, not an implicit side effect.
