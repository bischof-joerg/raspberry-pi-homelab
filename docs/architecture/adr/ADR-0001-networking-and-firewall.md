# ADR-0004: External Docker Networks with Explicit Bootstrap and Firewall Reconciliation

## Status
Accepted

## Date
2026-02-06

## Context

The homelab uses Docker Compose and GitOps for deploying a monitoring stack on a Raspberry Pi.
During operation, several issues were observed:

- Docker Compose implicitly created and managed networks, leading to:
  - Non-deterministic network names
  - IPAM subnet overlap errors during redeployments
- Docker bridge interfaces changed over time, causing:
  - Stale UFW rules referencing non-existent interfaces
  - Overly broad firewall rules remaining active
- Network-related failures (e.g. vmagent → VictoriaLogs scraping) were hard to diagnose due to
  implicit Docker behavior and missing guardrails

These problems violated core project principles:
- Determinism
- Idempotency
- No manual drift on the host
- Least privilege at the firewall level

## Decision

The project adopts the following networking and firewall model:

1. **All Docker networks used by stacks are external**
   - Docker Compose files reference networks but never create or modify them.
   - IPAM, bridge names, and lifecycle are managed outside of Compose.

2. **Explicit network bootstrap**
   - A dedicated script (`scripts/bootstrap-networks.sh`) ensures required networks exist.
   - The script is idempotent and guarded against subnet overlap.
   - Network creation and validation happen before any container deployment.

3. **Explicit network and firewall reconciliation**
   - A cleanup script (`scripts/cleanup-network-ufw.sh`) reconciles:
     - Unused Docker networks
     - Stale UFW rules referencing removed bridge interfaces
   - Required firewall rules are enforced explicitly and minimally.

4. **Deployment integration**
   - Network bootstrap is executed as part of `deploy.sh` before `docker compose up`.
   - Deployment fails early if network prerequisites are not met.

5. **Firewall constraints**
   - UFW rules are interface- and subnet-bound.
   - Docker Engine metrics (port 9323) are accessible only from the monitoring network.

## Alternatives Considered

### 1. Let Docker Compose manage networks implicitly
**Rejected** because:
- Network creation is non-deterministic
- IPAM overlaps can occur silently
- Hard to reason about firewall interfaces

### 2. Define IPAM and bridge options in Docker Compose
**Rejected** because:
- External networks cannot be safely managed by Compose
- Network lifecycle becomes coupled to stack deployment
- Rollbacks and partial deploys become risky

### 3. Disable UFW or rely on Docker-managed iptables rules
**Rejected** because:
- Violates least privilege
- Hard to audit
- Docker-generated rules change implicitly over time

### 4. Manual network and firewall management
**Rejected** because:
- Introduces manual drift
- Not GitOps-compatible
- Error-prone during incidents or recovery

## Consequences

### Positive

- Deterministic and reproducible deployments
- Early failure on misconfigured or overlapping networks
- Clear separation of responsibilities:
  - Compose: service topology
  - Bootstrap: infrastructure prerequisites
  - Cleanup: reconciliation and drift control
- Firewall rules are minimal, auditable, and tied to actual interfaces
- Network-related incidents are easier to diagnose

### Negative

- Additional scripts to maintain
- Slightly more complexity during initial setup
- Requires explicit bootstrap before first deployment

These trade-offs are accepted to achieve long-term stability and operational clarity.

## Follow-ups

- Document the networking model in [../networking-and-firewall-model.md](../networking-and-firewall-model.md)
- Consider adding post-deploy tests for:
  - DNS resolution across monitoring network
  - Presence of required UFW rules
- Revisit this ADR if multi-host or multi-node networking is introduced
