# Vector

## Networks

vector joins three external networks (`stacks/monitoring/compose/docker-compose.yml`):

- `monitoring` — to ship logs to `victorialogs:9428`.
- `docker-api` (internal) — to read the Docker API through `socket-proxy` (`docker_host:
  http://socket-proxy:2375` in `stacks/monitoring/vector/vector.yaml`). vector has no Docker
  socket mount and no Docker group since R1.10 (finding F30,
  `docs/architecture/adr/ADR-0012-docker-api-socket-proxy.md`).
- `apps` — on purpose, decided by the operator on 2026-09-29 (finding F34): the apps stack
  (roadmap stage R6) is prepared, and vector is to process data from app services there. No vector
  source uses it yet. Container logs do not need it: the `docker_logs` source reads them through
  the Docker API (via `docker-api`), not over `apps`.

The network set of every service is pinned in `tests/guards/test_10_monitoring_compose_contract.py`
(`EXPECTED_NETWORKS`), so joining another network is a reviewed change.

The vector API listens on `127.0.0.1:8686` only (`stacks/monitoring/vector/vector.yaml`, finding
F58, since R1.13): no container on `monitoring` or `apps` can reach it. Its only caller,
`tests/postdeploy/test_20_health_endpoints.py`, queries `/health` from inside vector's network
namespace. Guarded by `test_vector_api_listens_on_loopback_only`
(`tests/guards/test_10_monitoring_compose_contract.py`) and proven on the Pi by
`test_vector_api_is_not_reachable_from_other_containers` (`tests/postdeploy/test_40_vector_pipeline.py`).

A change to `vector.yaml` recreates vector on deploy through its own config hash
(`VECTOR_CONFIG_HASH`, R1.12, `docs/operations/DevWorkflow.md` §7).

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
