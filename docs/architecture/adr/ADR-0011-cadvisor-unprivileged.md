# ADR-0011: cadvisor runs without privileged mode

- **Status:** Proposed — accepted by the operator once postdeploy is green on the Pi
- **Date:** 2026-09-29
- **Scope:** `cadvisor` in `stacks/monitoring/compose/docker-compose.yml`; `privileged: true` in
  any Compose service
- **Supersedes:** [ADR-0010](ADR-0010-cadvisor-privileged-exception.md) once accepted

## Context

ADR-0010 recorded cadvisor's `privileged: true` as an exception and marked the claimed Pi 5
necessity as unmeasured. Its Decision 4 names the test: drop `privileged`, keep the existing
`--docker_only=true` flag and the explicit `/sys/fs/cgroup` mount, and prove with the postdeploy
cadvisor checks that metrics still flow (finding F46, step 4).

Baseline, measured on the Pi on 2026-09-29 while cadvisor was still privileged: cadvisor exported
every metric family that the alert rules (`stacks/monitoring/vmalert/rules/basic-alerts.yml`) and
the Docker overview dashboard use — `container_last_seen`, `container_cpu_usage_seconds_total`,
`container_memory_working_set_bytes`, `container_memory_rss`, `container_memory_cache`,
`container_network_receive_bytes_total`, `container_network_transmit_bytes_total` — with a `name=`
label for `alertmanager`, `grafana` and `victoriametrics`.

The known risk without `privileged` is assumed, not measured: the per-container network counters
come from `/proc/<pid>/net/dev` of processes running under other UIDs, which a root process
without `CAP_SYS_PTRACE` may not be allowed to read.

## Decision

1. `cadvisor` runs **without** `privileged: true`. It keeps `user: root`, `pid: host`, the device
   `/dev/kmsg`, its read-only host mounts and the Docker and containerd sockets (`:ro`).
2. No service in the repository runs `privileged: true`. `PRIVILEGED_ALLOWLIST` in
   `tests/guards/test_10_monitoring_compose_contract.py` is empty; a new entry requires its own
   ADR (unchanged from ADR-0010 Decision 2).
3. If the postdeploy checks show missing metric families, the fix is the smallest `cap_add` set
   that restores them, justified from cadvisor's log and recorded in this ADR by amendment — not a
   return to `privileged`. Only if that fails is the change reverted (IN8) and ADR-0010 amended
   with the measured result.

## Alternatives considered

- **Keep `privileged`.** Rejected: ADR-0010 held it only until this test; `privileged` grants every
  capability and every device for a need nobody measured.
- **Add capabilities up front** (for example `SYS_PTRACE`). Rejected: that would grant a
  capability on an assumption. The measurement decides; Decision 3 covers the failure case.
- **Replace cadvisor.** Out of scope, as in ADR-0010.

## Consequences

### Positive

- The stack has no privileged container; the guard fails for any new one without an ADR.
- The Pi 5 necessity claimed by the old inline comment is tested instead of assumed.

### Negative / Tradeoffs

- **cadvisor stays host-root equivalent.** The Docker socket gives full Docker API access; `:ro`
  protects only the socket file, not the API (F30, F34). `pid: host` still exposes every host
  process. Dropping `privileged` removes all-capabilities and all-devices, not this path.
- cadvisor still runs as root without `cap_drop`, `read_only` or a healthcheck; that hardening is
  group f (F7), not this decision.
- A future cadvisor release that needs more rights would fail at runtime, not in CI. Only the
  postdeploy family check catches it, so Renovate updates to `ghcr.io/google/cadvisor` still need
  a deploy with postdeploy green before they count as done.

## Enforcement

- `tests/guards/test_10_monitoring_compose_contract.py`:
  - `test_cadvisor_is_not_privileged` — the compose service does not set `privileged: true`;
  - `test_privileged_services_are_allowlisted` — with the empty allowlist, no service may;
  - `test_monitoring_doc_matches_cadvisor_privileges` — `docs/monitoring.md` does not call
    cadvisor privileged and its cAdvisor section links this ADR.
- `tests/postdeploy/test_25_cadvisor_metrics.py`:
  - `test_cadvisor_container_is_not_privileged` — `HostConfig.Privileged` is `false` on the Pi;
  - `test_cadvisor_exports_named_container_metrics` — every family above is exported with
    `name=` for each checked service;
  - `test_cadvisor_docker_socket_is_read_only` — the socket mount stays `:ro` (F28).
