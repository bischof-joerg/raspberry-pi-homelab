# ADR-0010: cadvisor privileged exception

- **Status:** Accepted
- **Date:** 2026-09-28
- **Scope:** `privileged: true` in any Compose service; today only `cadvisor` in
  `stacks/monitoring/compose/docker-compose.yml`

## Context

The monitoring stack runs hardened by default: non-root users, `cap_drop`, read-only root
filesystems, `no-new-privileges` (`.claude/rules/compose-stacks.md`). One service breaks every one
of these. `cadvisor` runs with:

- `privileged: true` and `user: root`,
- `pid: host` and the device `/dev/kmsg`,
- host `/` mounted as `/rootfs:ro`, plus `/sys`, `/sys/fs/cgroup`, `/var/lib/docker`,
- the Docker and containerd sockets, both `:ro` since F28.

cadvisor reads per-container CPU, memory and I/O from the host's cgroup v2 hierarchy and needs to
map cgroups to containers across namespaces. The compose file justifies `privileged` with an inline
comment: it is "non-negotiable on the Pi 5" for cgroup v2 visibility. **That claim has not been
measured.** The flag already existed when the stack moved to the `stacks/` layout (`3a50de5`,
2026-02-02); no commit, issue or document records a test without it. Until this ADR, no document
recorded the exception, and `docs/monitoring.md` stated the opposite ("No privileged containers")
— finding F46.

`.claude/rules/docs-adr.md` requires an ADR for an exception to a standing rule. This ADR records
the exception as it exists, bounds it, and names the step that tests whether it is needed.

## Decision

1. `cadvisor` is the **only** service that may run `privileged: true`. The exception is held until
   F46 step (4) tests running without it.
2. Every other service MUST NOT set `privileged: true`. A new exception requires its own ADR; this
   one MUST NOT be cited to justify a second privileged container.
3. The allowed services are listed in `PRIVILEGED_ALLOWLIST` in
   `tests/guards/test_10_monitoring_compose_contract.py`, each entry pointing at the ADR that
   records it.
4. F46 step (4) tries dropping `privileged` using the existing `--docker_only=true` flag and the
   explicit `/sys/fs/cgroup` mount, proven by the postdeploy cadvisor checks. If metrics still
   flow, the flag is removed, the allowlist entry is deleted, and this ADR is marked
   "Superseded by" the ADR that records the result. If they do not, the failure is recorded here as
   a dated amendment, and the claimed necessity becomes a measured one.

## Alternatives considered

- **Drop `privileged` now.** Rejected for this step: it changes runtime behaviour, and the
  project's approach is one concern per increment, with the change and its postdeploy proof in the
  same increment. That is F46 step (4).
- **Keep the inline comment as the only record.** Rejected: the only document that discussed
  cadvisor contradicted it, and Claude's own artefacts repeated the claim (F46). A comment is not
  checked by anything.
- **Replace cadvisor with another container metrics source** (for example the Docker Engine
  metrics endpoint, already scraped on `:9323`). Not evaluated here. The engine endpoint is
  assumed, not verified, to lack per-container CPU and memory usage. This stays an open option
  outside this decision.

## Consequences

### Positive

- The exception is visible, bounded to one service, and checked on every CI run.
- Any new privileged service fails the guard until someone writes its ADR.
- The claimed Pi 5 necessity is marked as an assumption with a named test, not as a fact.

### Negative / Tradeoffs

- **A compromise of cadvisor is a compromise of the host.** `privileged` grants every capability
  and every device; `pid: host` exposes all host processes; the Docker socket gives full Docker
  API access. Mounting the socket `:ro` protects only the socket file, not the API (F30). cadvisor
  has no network port on the host, but vmagent reaches it over the `monitoring` network, and it
  parses host-controlled data.
- Accepting the exception, even for a limited time, makes it easier to keep. The counterweight is
  that F46 step (4) is scheduled as its own increment in `.claude/roadmap.md` (group b), not left
  open-ended.
- Every cadvisor image upgrade runs with host-root rights, so Renovate updates to
  `ghcr.io/google/cadvisor` deserve the same review as a host package.

## Enforcement

- `tests/guards/test_10_monitoring_compose_contract.py`:
  - `test_privileged_services_are_allowlisted` — every privileged service is on the allowlist;
  - `test_allowlist_has_no_stale_entries` — every entry is still privileged;
  - `test_allowlist_entries_cite_existing_adr` — every entry names an existing ADR that mentions
    the service;
  - `test_monitoring_doc_does_not_deny_privileged_containers` — `docs/monitoring.md` does not
    claim the opposite and links this ADR.
- `tests/guards/test_50_docker_socket_mounts.py` — runtime sockets mounted `:ro` only (F28).
- `tests/postdeploy/test_25_cadvisor_metrics.py` — cadvisor exports named container metrics and
  its socket mount is read-only; this is the proof step (4) relies on.
