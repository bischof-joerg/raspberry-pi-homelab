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

## Enforcement

Checked on every deploy by `tests/postdeploy/test_56_monitoring_no_volume_mounts.py`:

- `test_monitoring_containers_have_no_volume_mounts`: no monitoring container has a mount of type
  `volume`.
- `test_host_has_no_docker_volumes`: no Docker volume of any kind exists on the Pi. The Pi is a
  deploy target only, so a dangling volume is drift. On 2026-09-25 three volumes left by earlier
  compose project names were found, one holding an old SMTP password (finding F48) — the
  project-name risk named under Rationale.

The parsing logic of the host check is proven statically in
`tests/guards/test_40_volume_offenders.py`. An image `VOLUME` that a service leaves uncovered also
creates an anonymous volume; for the Alertmanager renderer that is checked in
`tests/guards/test_32_alertmanager_renderer_container.py`.
