# ADR-0011: cadvisor runs without privileged mode

- **Status:** Accepted (operator, 2026-09-29, after postdeploy was green on the Pi)
- **Date:** 2026-09-29
- **Scope:** `cadvisor` in `stacks/monitoring/compose/docker-compose.yml`; `privileged: true` in
  any Compose service
- **Supersedes:** [ADR-0010](ADR-0010-cadvisor-privileged-exception.md)

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

## Result (measured 2026-09-29)

Deployed with merge `68a3118` (PR #31). On the Pi, `HostConfig.Privileged` of the recreated
cadvisor container is `false`. The metric families exported with `name=` for alertmanager, grafana
and victoriametrics match the baseline line for line, including both network families. The
operator reports postdeploy green: 63 passed, 4 skipped. The `cap_add` fallback of Decision 3 was
not needed; the old claim that `privileged` is "non-negotiable on the Pi 5" is disproved for this
image (`ghcr.io/google/cadvisor:v0.60.5`) and kernel.

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
  protects only the socket file, not the API (F30). `pid: host` still exposes every host
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

## Amendment 2026-10-01 — capabilities (F57, R1.19)

cadvisor drops every capability and adds back only `DAC_OVERRIDE`. This narrows the
"Negative / Tradeoffs" point that it runs without `cap_drop`; the socket, `pid: host`, `/dev/kmsg`
and `read_only` points stay as written.

**Measurement** (operator, on the Pi, 2026-10-01). Before: one cadvisor process with Docker's
default set, `CapEff 0xa80425fb`. A `bpftrace` kprobe/kretprobe pair on `cap_capable`, filtered to
`comm == "cadvisor"`, ran for 240 s across a cadvisor restart (`StartedAt` ten seconds after the
trace began) and a full postdeploy run (87 passed, 3 skipped). The kernel has no BTF, so `fexit`
was not available. Result per capability (granted / denied), with the kernel stacks of 1–3:

| Capability | Granted | Denied | Credentials of the check |
|---|---|---|---|
| `DAC_OVERRIDE` (1) | 8 | 0 | cadvisor's own: `generic_permission` called directly from `ovl_permission` |
| `DAC_READ_SEARCH` (2) | 16 | 8 | denied on the same direct path; granted only below `ovl_permission`'s `inode_permission` call and `ovl_path_open` |
| `FOWNER` (3) | 120 | 0 | only below `ovl_path_open` |
| `NET_ADMIN` (12) | 0 | 4 | `CAP_OPT_NOAUDIT` |
| `SYS_ADMIN` (21) | 3732 | 57 | no stack recorded; the denials with `CAP_OPT_NOAUDIT` |

overlayfs checks the overlay inode with the task's credentials and the underlying inode with
the credentials of the mounter. `DAC_READ_SEARCH` and `SYS_ADMIN` are not in cadvisor's
`CapEff`, so their granted checks cannot have used its own credentials; `FOWNER` appears only on
the mounter's paths. `DAC_OVERRIDE` is the only capability cadvisor used itself. Denied checks
fail today already and grant nothing.

**Decision.** `cap_drop: [ALL]` and `cap_add: [DAC_OVERRIDE]`; the expected `CapEff` is
`0x0000000000000002`. Which overlay directories need `DAC_OVERRIDE` was not measured; without it
those opens would fail with `EACCES`, and whether a metric family depends on them is not known,
so it is granted rather than assumed away. A further capability needs a new measurement and
another amendment.

**Enforcement.** `tests/guards/test_10_monitoring_compose_contract.py`:
`test_every_service_drops_all_capabilities`, `test_cadvisor_cap_add_is_the_measured_set`.
`tests/postdeploy/test_25_cadvisor_metrics.py`: `test_cadvisor_runs_with_measured_capabilities`
(`CapDrop`, `CapAdd` and the process's `CapEff` on the Pi).

## Amendment 2026-10-01 — no-new-privileges (F57, R1.20)

cadvisor runs with `security_opt: [no-new-privileges=true]`, like every other service. This
narrows the "Negative / Tradeoffs" point further; the socket, `pid: host`, `/dev/kmsg` and
`read_only` points stay as written.

**Measurement** (operator, on the Pi, 2026-10-01, before the change: `NoNewPrivs: 0`,
`CapEff 0x2`). `no-new-privileges` takes nothing away that a process holds; it only stops
`execve` from adding privileges through setuid/setgid bits or file capabilities. So the question
was what cadvisor executes, and what such files exist:

- The entrypoint `/usr/bin/entrypoint.sh` only runs `exec /usr/bin/cadvisor -logtostderr "$@"`.
- `find` as root over the container's root filesystem (`/proc/<pid>/root`, `-xdev`, so without
  the bind mounts) found no setuid or setgid file, and the host's `getcap` found no file
  capability there.
- A `bpftrace` trace of `sys_enter_execve` and `sys_enter_execveat`, following every fork of the
  process that executed the entrypoint, ran across a cadvisor restart and a full postdeploy run
  (88 passed, 3 skipped) plus 60 s. Before the restart the script checked that the probes were
  attached and that they caught a known `/bin/true` exec with the same predicate; `StartedAt`
  was after that check. The trace saw exactly the expected chain, `runc:[2:INIT]` →
  `/usr/bin/entrypoint.sh` → `/usr/bin/cadvisor`, all in one process, and no other exec.

Two earlier traces did not count: one ran without root, and one filtered on
`sched:sched_process_exec`, whose `filename` field `bpftrace` v0.23.2 on kernel 6.18.29 returned
empty, so it missed even the known start.

**Decision.** `no-new-privileges=true`. Its effect is defence in depth: cadvisor execs nothing
but itself, so it changes no behaviour. The bounding set already caps capabilities at
`DAC_OVERRIDE` across any `execve`; `no-new-privileges` adds that an exec can no longer change the
user or group through a setuid/setgid file — for example one under the host `/` mounted at
`/rootfs` — and that the kernel refuses any privilege-gaining transition on exec.

**Enforcement.** `tests/guards/test_10_monitoring_compose_contract.py`:
`test_every_service_sets_no_new_privileges` (every service, F41).
`tests/postdeploy/test_25_cadvisor_metrics.py`: `test_cadvisor_runs_without_new_privileges`
(`HostConfig.SecurityOpt` and the process's `NoNewPrivs: 1` on the Pi).

## Amendment 2026-10-01 — read_only (F57, R1.21)

cadvisor runs with `read_only: true` and no `tmpfs`. This settles the `read_only` point of
"Negative / Tradeoffs"; the socket, `pid: host` and `/dev/kmsg` points stay as written.

**Measurement** (operator, on the Pi, 2026-10-01, one script, `ReadonlyRootfs false`). The image
`ghcr.io/google/cadvisor:v0.60.5` declares no `VOLUME`. cadvisor was restarted and ran for 90 s,
longer than `--max_housekeeping_interval=60s`; its log since the restart had no `read-only`,
`permission denied` or `no space` line. `docker diff` over the container's whole life (created at
the R1.20 deploy) listed ten entries, all of them bind-mount targets from the compose file and
their parent directories: `A /etc/machine-id`, `A /rootfs`, `A /run/containerd/containerd.sock`,
`A /run/docker.sock` (`/var/run` is a symlink to `/run`), `A /var/lib/docker`, and `C /etc`,
`C /run`, `C /var`, `C /var/lib`. Docker creates these mount points when it creates the container,
a read-only root filesystem included. A self-test after the measurement checked that `docker diff`
shows a file the container writes (`A /tmp/.r121probe`); the file was removed again.

The decision rule fixed in advance ("an empty diff means no `tmpfs`") did not foresee the mount
targets; the rule that held is "the diff minus the mount targets in `.Mounts`".

**Decision.** `read_only: true`. A write cadvisor did not show in this window would fail with
`EROFS`; the postdeploy check below reads its log for that. A `tmpfs` is added only for a path
measured that way, with another amendment.

**Enforcement.** `tests/guards/test_10_monitoring_compose_contract.py`:
`test_every_service_has_a_read_only_rootfs` (every service; grafana is the one exception, tracked
by F41) and `test_read_only_exceptions_are_current`.
`tests/postdeploy/test_25_cadvisor_metrics.py`: `test_cadvisor_root_filesystem_is_read_only`
(`HostConfig.ReadonlyRootfs` on the Pi) and `test_cadvisor_logs_no_write_errors_since_start`.
