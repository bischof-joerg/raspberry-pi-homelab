# Vector

## Networks

vector joins two external networks (`stacks/monitoring/compose/docker-compose.yml`):

- `monitoring` — to ship logs to `victorialogs:9428`.
- `apps` — on purpose, decided by the operator on 2026-09-29 (finding F34): the apps stack
  (roadmap stage R6) is prepared, and vector is to process data from app services there. No vector
  source uses it yet. Container logs do not need it: the `docker_logs` source reads them through
  the Docker API, not over a network.

The network set of every service is pinned in `tests/guards/test_10_monitoring_compose_contract.py`
(`EXPECTED_NETWORKS`), so joining another network is a reviewed change.

Side effect recorded as finding F58: the vector API listens on `0.0.0.0:8686`
(`stacks/monitoring/vector/vector.yaml`), so every container on `monitoring` and `apps` can reach it.

## Journald access runbook (required for containerized Vector)

Reading journald from inside a container is primarily a permissions problem.

Ensure Docker uses journald logging driver (host-level change).

Ensure Vector can read:

- `/run/log/journal` and `/var/log/journal` (mounted read-only)
- `/etc/machine-id` (mounted read-only; required by sd-journal readers)

If Vector gets “permission denied” on journal files:

- Preferred: grant read to the journal directories via a **dedicated group** (e.g. `systemd-journal`) and align container group id or apply an ACL for a dedicated runtime group.
- Keep this as an **idempotent host script** (similar to your existing init-permissions approach) to prevent drift.

(We can implement the idempotent script next, but the above is the minimum you need documented because it’s environment-specific.)
