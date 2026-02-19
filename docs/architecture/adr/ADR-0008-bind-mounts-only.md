# ADR-000X: Use bind mounts only for persistent monitoring data

## Status

Accepted

## Context

The monitoring stack persists state on disk (e.g., VictoriaMetrics TSDB, VictoriaLogs storage, Grafana data, Alertmanager state, Vector buffers).
Docker supports persistence using either named volumes or bind mounts.

This homelab follows an IaC + GitOps operating model:

- deterministic host layout under /srv/data
- backups and restores are performed at the filesystem layer
- no manual drift on the target node
- idempotent deploys and predictable rollback

A mixed approach (some named volumes, some bind mounts) complicates backup/restore and increases the risk of “hidden” state outside the standard data root.

## Decision

Use bind mounts exclusively for all persistent state in the monitoring stack.
No Docker named volumes are used.

All persistent paths MUST live under:

- /srv/data/stacks/monitoring/<service>

Specifically:

- VictoriaLogs storage is mounted as /srv/data/stacks/monitoring/victorialogs:/vlogs
- Existing persistent services continue using bind mounts under the same root.

## Rationale

Bind mounts provide:

- deterministic, human-auditable storage locations
- simple and consistent backup/restore using standard filesystem tools (rsync/borg/restic/snapshots)
- alignment with IaC requirements: directory creation and permissions can be managed idempotently

Named volumes were avoided because:

- their physical location is Docker-managed and less transparent
- they introduce an additional lifecycle domain (docker volume create/inspect/remove)
- project-name or compose-name changes can result in new empty volumes if not pinned carefully

## Consequences

Positive:

- One uniform persistence model across services
- Easier operational runbooks (backup/restore, inspection, troubleshooting)
- Reduced risk of untracked state outside /srv/data

Negative / Risks:

- Correctness depends on host directory existence and permissions
- Container UID/GID mismatches can cause write failures

Mitigations:

- deploy.sh MUST create required directories before docker compose up
- init-permissions.sh MUST enforce ownership/permissions idempotency
- config mounts remain read-only; only state directories are writable
- post-deploy tests verify storage and service health

## Implementation Notes

1. Replace any named volume mounts with bind mounts under /srv/data/stacks/monitoring/<service>
2. Remove top-level volumes: declarations from docker-compose.yml
3. Extend init-permissions.sh to include any new data directories
4. Validate with:
   - docker compose config
   - docker inspect <container> to confirm mount Type=bind
   - service logs and health checks
