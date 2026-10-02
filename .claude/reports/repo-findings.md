# Repository findings – raspberry-pi-homelab

- **Status:** handed over 2026-09-23 (Phase 6 of the transition, now archived in
  `.claude/ClaudeTransition.md`); worked off in roadmap stage **R1** since 2026-09-25.
- **Nature:** each entry is written so that it can become one increment (`increment-plan` skill).
  Fixed entries keep their history in a **Resolution** line and carry status `addressed`.
- **Single source of truth.** This file holds the entries of every open or partly addressed
  finding and the index of **all** findings. An entry moves to
  `.claude/reports/repo-findings-archive.md` unchanged when it becomes `addressed`, in the `docs/`
  commit that logs the increment; its index row stays here. Read an archived entry only when its
  history matters. The grouping into R1 increments, with what is open and done per group, lives in
  `.claude/roadmap.md` §6.
- **Mechanical check (V6.2):** `python3 .claude/tools/check_findings.py`, also run by `make ci`
  through `tests/guards/test_58_findings_check.py` — every entry in either file has Evidence,
  Impact, Proposed fix, Test and Acceptance; every cited repo path exists; a path marked
  *(absent)* really is absent; the entries of both files together are the index; the archive holds
  only `addressed` findings and this file none; the roadmap groups agree with the index's status
  and R1 columns.

## How to read an entry

| Field | Meaning |
|---|---|
| **Evidence** | Repository paths (`file:line`) and the verification state. **[V date]** = read in the file on that date. **[I]** = inference; the entry names the check that would settle it. |
| **Impact** | What goes wrong, and for whom. |
| **Proposed fix** | The smallest change that removes the defect. Ordering hints where one fix depends on another. |
| **Test** | Layer (`tests/precommit`, `tests/guards`, `tests/postdeploy`) and the file to extend or create — test-first per D1. |
| **Acceptance** | An observable pass/fail statement. If you cannot check it, the finding is not closed. |
| **Prevention** | Required from F64 on (IN17): where on the ladder the defect would have been caught earlier and by which mechanism — test or guard, checker, hook, rule, skill or agent, or (with a reason why nothing can check it) a lesson. Part of the fix increment, or its own finding. |
| **Scheduling** | Optional. The operator's dated decision to schedule the finding other than IN15 says, with the reason (IN16), e.g. `2026-10-01, operator: pulled forward before F57, …`. |

Verification dates: F1–F24 were first recorded 2026-09-16 on a Windows copy of the repository
(decision E1) and partly re-verified later; the date given is the latest read. On 2026-09-23 only
the findings whose status could plausibly have changed were re-read (F5, F10, F14, F21, F22, F23).
Re-verifying **every** entry against `main` is the R1 exit criterion (`.claude/roadmap.md` §4);
line numbers drift, so re-read before fixing.

Caution carried over from the transition (§5.2 there): three times a Claude artefact cited a
document as saying something it does not say. A cited file existing is not the file agreeing. Read
the cited lines before acting on any entry.

## Index

Severity: **Critical** = harm happening now or imminent — security updates blocked, a credential
exposed on the network, data loss or a broken backup, a host that may not boot; **High** =
credential exposure, host-root equivalence, or a safety mechanism that does not work; **Med** =
drift, fragility, a missing test for a real contract, or a deviation from a named best practice;
**Low** = hygiene.

**Found** is the date the finding was recorded (`—` only for F1–F63 where none is recorded).
**Due** follows from the severity (`.claude/roadmap.md` §2, IN15): Critical → `next`, the next
increment; High → `R<x>.<y>`, the increment after the next planned one; Med and Low → `R<x>`, the
stage after the current one; `—` once addressed. A **Scheduling** line in the entry records an
operator's override (IN16). Findings up to F63 predate the model and keep a stage Due from their R1
group. The R1 column is the grouping into increments; per-group status and order in
`.claude/roadmap.md` §6. `tools/check_findings.py` enforces Due and reports overdue findings.

| ID | Title | Area | Sev | Found | Due | Status | R1 |
|---|---|---|---|---|---|---|---|
| F1 | Config hash is driven by a single runtime file | Deploy | High | — | R1 | open | d |
| F2 | Hash list names a missing file and two unmounted ones | Deploy | Med | — | R1 | open | d |
| F3 | Images pinned by tag, not by digest | Supply chain | Med | — | R1 | open | g |
| F4 | Renovate manages compose images only | Supply chain | Med | — | R2 | open | R2d |
| F5 | `README.md` describes a stack that no longer exists | Docs | Low | — | R2 | open | R2b |
| F6 | ADR numbering and titles are inconsistent | Docs | Low | — | R2 | open | R2b |
| F7 | Missing restart policy / healthchecks | Hardening | Med | — | R1 | partly | f |
| F8 | Renderer installs `gettext` from the network at every run | Supply chain | Med | — | — | addressed | a |
| F9 | Backup scripts have no tests although ADR-009 requires them | Backup | High | — | R3 | open | R3 |
| F10 | pytest version drift between pre-commit and `.venv` | Toolchain | Low | — | — | addressed | – |
| F11 | `.gitattributes` does not pin LF for all text types | Toolchain | Low | — | R1 | open | h |
| F12 | `.env.example` duplicates keys and holds host-derived values | Secrets | Low | — | R2 | open | R2b |
| F13 | Compose mounts a templates directory that does not exist | Deploy | Med | — | R1 | open | d |
| F14 | DevWorkflow committed before `make ci` | Docs | Low | — | — | addressed | – |
| F15 | UFW is not reconciled on deploy | Exposure | Med | — | R1 | open | c |
| F16 | Network bootstrap on deploy skips subnet/bridge validation | Host | Med | — | R1 | open | e |
| F17 | `daemon.json` applied before the network it references exists | Host | Med | — | R1 | open | e |
| F18 | Any `daemon.json` change restarts Docker during deploy | Host | Med | — | R1 | open | e |
| F19 | Host-specific literals in reconciliation scripts | Host | Low | — | R1 | open | e |
| F20 | `ensure-journald-read.sh` default user does not match its use | Host | Low | — | R1 | open | e |
| F21 | Toolchain drift between `.venv` and pre-commit | Toolchain | Med | — | — | addressed | h |
| F22 | Three diverging sources of dev dependencies | Toolchain | Med | — | — | addressed | h |
| F23 | Tests marked `lint` are never run by any gate | Tests | Med | — | R1 | open | h |
| F24 | Renovate validator hook runs a floating image tag | Supply chain | Med | — | R1 | open | g |
| F25 | JSON test scans git-ignored files | Tests | Low | — | R1 | open | h |
| F26 | Alertmanager SMTP password written world-readable | Secrets | High | — | — | addressed | a |
| F26b | The same password persists in every backup archive | Secrets | High | — | R1 | partly | a |
| F27 | Container uid left to image defaults for 8 of 10 services | Hardening | Med | — | R1 | open | f |
| F28 | cadvisor mounts the Docker socket read-write | Privilege | High | — | — | addressed | b |
| F29 | Config-hash label missing on 5 of 10 services | Deploy | High | — | R1 | open | d |
| F30 | vector is effectively host root via the Docker socket | Privilege | High | — | — | addressed | b |
| F31 | Grafana admin credentials default to empty | Secrets | High | — | R1 | open | c |
| F32 | Grafana runs without `read_only` on a wrong justification | Hardening | Med | — | R1 | open | f |
| F33 | vector has no healthcheck | Hardening | Low | — | R1 | open | f |
| F34 | vector joins the `apps` network without a reason | Privilege | Med | — | — | addressed | b |
| F35 | Renderer swallows errors despite `set -euo pipefail` | Secrets | Med | — | — | addressed | a |
| F36 | Renderer builds YAML without escaping | Secrets | Med | — | — | addressed | a |
| F37 | `alpine:3.24` is a floating minor tag | Supply chain | Med | — | — | addressed | g |
| F38 | `depends_on` ignores existing healthchecks | Hardening | Low | — | R1 | open | f |
| F39 | German comment in the renderer script | Docs | Low | — | — | addressed | a |
| F40 | Volume naming rule contradicted the implementation | Docs | Low | — | — | addressed | – |
| F41 | No static guard for the compose hardening contract | Tests | Med | — | R1 | partly | f |
| F42 | LAN exposure of 3000/9428 is recorded in no document | Exposure | Med | — | R1 | partly | c |
| F43 | ADR-0001 promises subnet validation the deploy path skips | Docs | Med | — | R1 | open | e |
| F44 | Stale image tag in a Markdown example | Supply chain | Low | — | R1 | open | g |
| F45 | UFW very likely does not govern the published ports | Exposure | High | — | R1 | open | c |
| F46 | cadvisor's privileged mode is undocumented; docs say the opposite | Privilege | High | — | — | addressed | b |
| F47 | cadvisor doctor test never runs; its skip hides a compose error | Tests | Med | — | R1 | open | h |
| F48 | Orphaned named alertmanager-config volumes held an old SMTP password | Secrets | High | — | — | addressed | a |
| F49 | Postdeploy as root writes `__pycache__` into the Pi checkout | Tests | Low | — | — | addressed | h |
| F50 | The WSL layer (Python, Docker Desktop, apt) is neither documented nor checked | Toolchain | Med | — | R2 | open | R2d |
| F51 | Host upgrade apply does not execute the reviewed plan | Host | High | — | R3 | open | R3b |
| F52 | Mutating host-runtime scripts have no backup gate | Host | High | — | R3 | open | R3b |
| F53 | host-runtime scripts are untestable off the Pi and untested | Tests | Med | — | R3 | open | R3b |
| F54 | Docker packages upgrade uncontrolled inside the routine APT upgrade | Host | Med | — | R3 | open | R3b |
| F55 | Plan output, audit and runtime-updates doc disagree; audit gaps pass silently | Host | Low | — | R3 | open | R3b |
| F56 | Deploy log records postdeploy as `passed` without counts; the evidence is not kept | Tests | Med | — | R1 | open | h |
| F57 | cadvisor is host-root equivalent via the Docker socket, root and `pid: host` | Privilege | High | — | R1.23 | open | b |
| F58 | vector's API listens on all interfaces of two networks | Privilege | Low | — | — | addressed | b |
| F59 | `make ci` never runs the pre-commit hooks on new, untracked files | Toolchain | Low | — | — | addressed | h |
| F60 | `/boot/firmware` is read-only, so `initramfs-tools` stays half-configured and every APT run fails | Host | High | 2026-09-29 | — | addressed | j |
| F61 | unattended-upgrades runs on the Pi, outside the documented host update flow | Host | Med | 2026-09-29 | R3 | open | R3b |
| F62 | The Pi's journal is volatile; host evidence is lost at every reboot | Host | Med | 2026-10-01 | — | addressed | k |
| F63 | The memory cgroup Docker relies on is enabled by a hand-edited kernel command line outside the repository | Host | Low | 2026-10-01 | R1 | open | e |
| F64 | No proactive host best-practice check; deviations surface only by accident | Host | Med | 2026-10-01 | R2 | open | R2e |
| F65 | cadvisor cannot stat container root filesystems under the containerd image store | Monitoring | Low | 2026-10-01 | R2 | open | R2a |
| F66 | Measurements on the Pi leave files and packages behind | Host | Low | 2026-10-01 | — | addressed | l |
| F67 | Development on the Pi was possible and happened; nothing in the repository prevents it | Host | Low | 2026-10-01 | — | addressed | l |
| F68 | Backup inventory omits the host files deploy installs and the hand-edited `sshd_config` | Backup | Low | 2026-10-01 | R2 | open | R2b |
| F69 | Journald ingestion test skips quiet units at once; the skip count varies between deploys | Tests | Low | 2026-10-02 | R2 | open | R2a |
| F70 | Postdeploy changes udev's log level and re-triggers every device on the host | Host | Med | 2026-10-02 | R2 | open | R2a |
| F71 | Postdeploy pulls and runs the unpinned `hello-world:latest` | Supply chain | Low | 2026-10-02 | R2 | open | R2a |
| F72 | node-exporter shares the host PID namespace without a recorded reason | Privilege | Low | 2026-10-02 | R2 | open | R2a |

## Secrets and credentials

### F26b – The same password persists in every backup archive

- **Evidence:** `scripts/backup/backup.sh:383-385` archives `${STACK_DATA_ROOT}/alertmanager-config`; `stacks/monitoring/compose/init-permissions.sh:111,112,146` reconciles the directory to `0:0` mode `0755`. [V 2026-09-23]
- **Impact:** Rotating the SMTP password is not complete until backup retention ages out; a restore re-materialises the file at `0644`; the directory is traversable by everyone. At rest the archive is GPG-encrypted, which is acceptable.
- **Proposed fix:** Directory to `0750` with the Alertmanager-readable group in `init-permissions.sh`; document "rotation completes after retention" in `docs/operations/BackupVerifyRestore.md`; ensure restore re-applies the F26 mode.
- **Test:** `tests/postdeploy` — directory mode `0750`; backup fixture test (R3, F9) — a restored tree yields `0640` on the rendered file.
- **Acceptance:** Directory mode is `750` after deploy; a restore dry-run in the fixture harness produces no world-readable credential file.
- **Resolution (R1.1, 2026-09-25) — partly:** `init-permissions.sh` reconciles the directory to `0:nogroup 750` and strips other-bits recursively (its `--check` detects restore leftovers); rotation note in `docs/operations/BackupVerifyRestore.md` §6.2; postdeploy `test_55`. **Open:** the restore fixture test, which belongs to R3/F9 (stage R2 before the re-plan of 2026-09-26).

### F31 – Grafana admin credentials default to empty

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:246-247` uses `${GRAFANA_ADMIN_USER:-}` / `${GRAFANA_ADMIN_PASSWORD:-}`. [V 2026-09-23]; what Grafana does with empty values [I — check with `docker compose config` and Grafana's startup log with the variables unset, in WSL].
- **Impact:** A missing or incomplete host env file starts a LAN-exposed Grafana (port 3000) with whatever Grafana does for empty credentials, instead of failing the deploy.
- **Proposed fix:** Use `${VAR:?message}` so `docker compose config` fails fast; `deploy.sh` secrets validation should list both variables.
- **Test:** `tests/precommit/test_30_compose_config.py` — with a fixture env that omits both variables, `docker compose config` must fail and name them.
- **Acceptance:** `docker compose config` without the two variables exits non-zero with a message naming them; with them it passes.

### F12 – `.env.example` duplicates keys and holds host-derived values

- **Evidence:** `stacks/monitoring/compose/.env.example` lists `DOCKER_GID` / `SYSTEMD_JOURNAL_GID` twice; `docs/architecture/adr/ADR-0007-secrets-and-env-files.md` §4 says host-derived values are computed by `deploy.sh`. [V 2026-09-16]
- **Impact:** Operators copy wrong or duplicate values into the host env file; the later key silently wins.
- **Proposed fix:** Remove the duplicates and the host-derived keys, with a comment pointing to `deploy.sh`.
- **Test:** `tests/precommit` — `.env.example` has unique keys and none of the host-derived names.
- **Acceptance:** The test passes and fails on a duplicated key.

## Privilege and the Docker socket

### F57 – cadvisor is host-root equivalent via the Docker socket, root and `pid: host`

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:251-287` — after F46 step (4) cadvisor is no longer privileged, but still runs `user: root` with `pid: host`, the device `/dev/kmsg`, host `/` as `/rootfs:ro`, and `/var/run/docker.sock` plus the containerd socket (both `:ro`); no `cap_drop`, no `read_only`, no `security_opt`. [V 2026-09-29]; ADR-0011 "Negative / Tradeoffs" records the same. F30 describes this socket class for vector only; F7 covers only cadvisor's missing healthcheck.
- **Impact:** A compromise of cadvisor, which parses host-controlled data and is reachable from every container on the `monitoring` network, still gives full Docker API access (`:ro` does not restrict the API), i.e. host root. Dropping `privileged` removed all-capabilities and all-devices, not this path.
- **Proposed fix:** Decide together with F30, since both need read-only Docker API access: a filtering socket proxy that allows only the read endpoints cadvisor and vector use, shared or per service. Then drop what cadvisor does not need, each step measured by `tests/postdeploy/test_25_cadvisor_metrics.py`: `cap_drop: [ALL]` plus only the capabilities that prove necessary, `no-new-privileges`, `read_only` with a `tmpfs`, and whether `pid: host` and `/dev/kmsg` are needed with `--docker_only=true`.
- **Test:** `tests/guards/test_50_docker_socket_mounts.py` — no service mounts the raw socket once the proxy exists; `tests/guards/test_10_monitoring_compose_contract.py` — cadvisor's expected `cap_add`/`cap_drop`/`security_opt` set; postdeploy `test_25` family check after each step.
- **Acceptance:** cadvisor cannot call a write endpoint of the Docker API; every family in `REQUIRED_FAMILIES` still flows; its remaining rights are listed in ADR-0011 or a successor.
- **Progress (2026-09-29, R1.11 attempted and reverted):** the socket part was tried as R1.11 — merge `768e3fb` (PR #40; `611e704` tests, `cdf15f8` fix): cadvisor with `--docker=tcp://socket-proxy:2375`, no Docker or containerd socket, proxy allowlist extended by GET `_ping`/`version`/`info` and HEAD `/_ping`. Postdeploy failed: `test_cadvisor_exports_named_container_metrics` found no `name=` series, and the live count `grep -c 'name="homelab-home-prod-mon-'` on cadvisor's `/metrics` was `0` [V 2026-09-29, operator]. Cause, measured on the Pi [V 2026-09-29, operator]: cadvisor logged `Registration of the docker container factory failed: unable to create containerd client: containerd: cannot unix dial containerd api service: dial unix /run/containerd/containerd.sock: connect: no such file or directory`; `docker info` reports `overlayfs 29.5.2 [[driver-type io.containerd.snapshotter.v1]]` — Docker uses the containerd image store. In cadvisor v0.60.5 (`container/docker/factory.go`, read 2026-09-29) the Docker factory creates a containerd client whenever the storage driver is the containerd snapshotter, and a failure aborts the whole registration; no flag turns it off. The proxy log held no `blocked request` at all, so the Docker API calls themselves were not the problem. The containerd API is gRPC and cannot be filtered by socket-proxy; the containerd socket alone grants host root (tasks in the `moby` namespace). Reverted per IN8: merge `4d498a1` (PR #41, revert commit `82fe60f`, tree identical to `5ce0854`); postdeploy `71 passed, 4 skipped`, the proxy log holds only the two `127.0.0.1` probes, cadvisor exports `634` `name=` series again [V 2026-09-29, operator]. **Consequence:** the socket part of F57 cannot be solved with socket-proxy while Docker uses the containerd image store. Open options, none decided: (a) switch the Docker daemon to the classic `overlay2` graph driver — a `daemon.json` change that restarts Docker (F18) and rebuilds every image and container, needs its own ADR and a proven backup (R3), and whether cadvisor then no longer needs containerd is [I]; (b) accept the socket risk explicitly in ADR-0011 or a successor; (c) drop cadvisor's Docker integration (`name=` labels, on which vmalert rules and dashboards depend) — not viable today. The other hardening steps (`cap_drop`, `no-new-privileges`, `read_only`, `pid: host`, `/dev/kmsg`) are independent of the sockets and remain open. Status stays `open`.
- **Progress (2026-10-01, R1.19):** `cap_drop: [ALL]` with `cap_add: [DAC_OVERRIDE]`. Measured by the operator on the Pi with a `bpftrace` trace of `cap_capable` over a cadvisor restart and a postdeploy run [V 2026-10-01, operator]: `DAC_OVERRIDE` is the only capability cadvisor used with its own credentials; the other granted checks (`DAC_READ_SEARCH`, `FOWNER`, `SYS_ADMIN`) ran with overlayfs's mounter credentials — `DAC_READ_SEARCH` and `SYS_ADMIN` are not even in its `CapEff 0xa80425fb`. Table and decision in ADR-0011, amendment 2026-10-01. Guards `test_every_service_drops_all_capabilities`, `test_cadvisor_cap_add_is_the_measured_set` (`tests/guards/test_10_monitoring_compose_contract.py`); postdeploy `test_cadvisor_runs_with_measured_capabilities` expects `CapEff 0x2`. Still open: `no-new-privileges`, `read_only`, `pid: host`, `/dev/kmsg`, and the socket decision. Status stays `open`.
- **Progress (2026-10-01, R1.20):** `security_opt: [no-new-privileges=true]`. Measured by the operator on the Pi [V 2026-10-01, operator]: no setuid/setgid and no file-capability files in cadvisor's rootfs; a `bpftrace` trace of `sys_enter_execve`/`execveat` over every fork of the entrypoint's process, across a restart and a postdeploy run, saw only `runc:[2:INIT]` → `/usr/bin/entrypoint.sh` → `/usr/bin/cadvisor`. After the deploy `NoNewPrivs: 1`, `CapEff 0x2`. ADR-0011, amendment "no-new-privileges". Guard `test_every_service_sets_no_new_privileges` (`tests/guards/test_10_monitoring_compose_contract.py`); postdeploy `test_cadvisor_runs_without_new_privileges`. Still open: `read_only`, `pid: host`, `/dev/kmsg`, and the socket decision. Status stays `open`.
- **Progress (2026-10-01, R1.21):** `read_only: true` without `tmpfs`. Measured by the operator on the Pi [V 2026-10-01, operator]: image without `VOLUME`; after a restart and 90 s no write-related log line; `docker diff` over the container's life lists only the five bind-mount targets and their parent directories; a self-test proved that `docker diff` shows a file the container writes. ADR-0011, amendment "read_only". Guards `test_every_service_has_a_read_only_rootfs` (grafana excepted, F41), `test_read_only_exceptions_are_current`; postdeploy `test_cadvisor_root_filesystem_is_read_only`, `test_cadvisor_logs_no_write_errors_since_start`. Still open: `pid: host`, `/dev/kmsg`, and the socket decision. Status stays `open`.
- **Scheduling:** 2026-10-01, operator: Due moved from R1.19 to R1.20 after R1.19 delivered the `cap_drop` step; R1.20 is the next F57 step (`no-new-privileges`), earlier than IN15's increment-after-next because it touches the same service, files and tests. 2026-10-01, operator: Due moved from R1.20 to R1.21 after R1.20 delivered `no-new-privileges`; R1.21 is the next F57 step (`read_only`), for the same reason. 2026-10-01, operator: Due moved from R1.21 to R1.22 after R1.21 delivered `read_only`; R1.22 is the next F57 step (`/dev/kmsg`, before `pid: host`), for the same reason. 2026-10-02, operator: Due moved from R1.22 to R1.23 after R1.22 delivered `/dev/kmsg`; R1.23 is the next F57 step (`pid: host`), for the same reason.
- **Progress (2026-10-01, R1.21 deployed):** merge `1659424` (PR #70; `43165bf`), CI green. Measured on the Pi [V 2026-10-01, operator]: postdeploy `96 passed, 3 skipped`, including `test_cadvisor_root_filesystem_is_read_only` and `test_cadvisor_logs_no_write_errors_since_start`; cadvisor recreated at the deploy (`Created 2026-10-01T13:59:39Z`) with `ReadonlyRootfs=true`; its `docker diff` lists only the ten mount-target entries of the measurement and no `C /tmp`, so the self-test's trace in the old container went with it. Status stays `open`: `/dev/kmsg`, `pid: host` and the socket decision.
- **Progress (2026-10-02, R1.22):** `/dev/kmsg` dropped. Measured by the operator on the Pi with one read-only script [V 2026-10-02, operator]: `kernel.dmesg_restrict 0`, `CapEff 0x2`; cadvisor held one descriptor on `/dev/kmsg` (self-test: the same predicate found `/dev/null`); its log since the start lists `oom_event` as enabled and has no OOM-watcher warning; 11 `container_oom_events_total` series. The device was in use, for the OOM watcher only; the operator decided to drop it anyway, since no rule or dashboard reads that metric. ADR-0011, amendment "/dev/kmsg". Guard `test_no_service_maps_host_devices` (`DEVICES_ALLOWLIST` empty); postdeploy `test_cadvisor_has_no_host_devices`. Still open: `pid: host` and the socket decision. Status stays `open`.
- **Progress (2026-10-02, R1.22 deployed):** merge `77391d1` (PR #72; `49bcd9c` tests, `d48d475` fix and skill), CI green. Measured on the Pi [V 2026-10-02, operator]: deploy 13:38 `tests: passed`, postdeploy `96 passed, 4 skipped`, including `test_cadvisor_has_no_host_devices` and `test_cadvisor_exports_named_container_metrics`; all four skips are `test_21` (two) and `test_45`'s quiet `systemd-udevd.service` and `ufw.service` (F69), none in cadvisor's tests. cadvisor's log since the deploy: `Could not configure a source for OOM detection, disabling OOM events: open /dev/kmsg: no such file or directory`, as ADR-0011 expects. Status stays `open`: `pid: host` and the socket decision.
- **Progress (2026-10-02, R1.23):** `pid: host` dropped. Source read (cadvisor v0.60.5): with `/rootfs/proc` present, every per-process path is read as `/rootfs/proc/<host pid>/…`. Measured by the operator on the Pi with one read-only script [V 2026-10-02, operator]: `/rootfs/proc` is a `proc` mount (the host's procfs via `/:/rootfs`), `1/comm` `systemd` as on the host, 196 PIDs on both sides, no `/proc/<pid>` error in the log, 69 `container_*` families. ADR-0011, amendment "pid: host", which also corrects the "/dev/kmsg" amendment: `container_oom_events_total` is still exported (11 series), only no longer counted. Guard `test_no_service_shares_the_host_pid_namespace` (`PID_HOST_ALLOWLIST`: node-exporter, F72); postdeploy `test_cadvisor_has_its_own_pid_namespace`, `test_cadvisor_logs_no_proc_read_errors_since_start`. Still open: the socket decision. Status stays `open`.

## Exposure and firewall

### F45 – UFW very likely does not govern the published ports

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:243,347` publish `3000` and `9428` on all interfaces; `scripts/network/cleanup-ufw.sh:446,474` add INPUT-chain rules only; no `ufw route` / `DOCKER-USER` rule in `scripts/`, `docs/` or `stacks/`; `stacks/core/docker/daemon.json` does not set `"iptables": false`; `tests/postdeploy/test_35_network_and_ufw.py:210-244,327-342`. [V 2026-09-23]; effective reachability [I — from a host outside `LAN_CIDR`, `curl` both ports; operator only, C5].
- **Impact:** Docker's published-port traffic is DNAT'd through `FORWARD`, not `INPUT`, so the allowlist is very likely inert and both UIs are reachable from anything that can route to the Pi. The postdeploy test asserts rule **presence**; its one real negative test targets `9323`, a host port on the INPUT path, so it passes for a reason that does not generalise.
- **Proposed fix:** Bind both ports to the LAN address in compose, or add `ufw route` / `DOCKER-USER` rules — plus a negative postdeploy check.
- **Test:** `tests/postdeploy/test_35_network_and_ufw.py` — a negative reachability check from a non-`LAN_CIDR` source (or, if that is impractical on the Pi, assert the published bind address).
- **Acceptance:** A connection from outside `LAN_CIDR` to 3000/9428 is refused, measured by a test, not inferred from rule presence.

### F42 – LAN exposure of 3000/9428 is recorded in no document

- **Evidence:** `docs/architecture/adr/ADR-0001-networking-and-firewall.md` mentions neither port; a grep over `docs/` finds only timestamps and in-container examples. The exposure is intentional per `scripts/network/cleanup-ufw.sh`, `stacks/monitoring/compose/.env.example` and `tests/postdeploy/test_35_network_and_ufw.py`. [V 2026-09-23]
- **Impact:** A deliberate exposure without a record gets copied as precedent. The Claude rule that called it "documented" was corrected on 2026-09-23 (hence *partly*); the documentation gap remains.
- **Proposed fix:** Amend ADR-0001 (or a new ADR) with the two ports, their purpose and the intended source restriction — after F45 is decided, so the ADR records the working mechanism.
- **Test:** `tests/guards` — every published non-loopback port in compose appears in the network ADR.
- **Acceptance:** The guard test passes and fails when a new LAN port is published without an ADR entry.

### F15 – UFW is not reconciled on deploy

- **Evidence:** `deploy.sh` does not call `scripts/network/cleanup-ufw.sh`; `Makefile` has no target for it; `Todo.txt` notes the gap. [V 2026-09-16]
- **Impact:** UFW drift is detected by postdeploy (`tests/postdeploy/test_35_network_and_ufw.py`) but never corrected; a fresh host has no firewall policy from the repository.
- **Proposed fix:** R1 decision (ADR) on which host state `deploy.sh` reconciles; if UFW is in, call the script in `--apply` mode from `deploy.sh` behind a flag, idempotently. Depends on F45.
- **Test:** `tests/postdeploy/test_35_network_and_ufw.py` stays the detector; add a `tests/guards` check that `deploy.sh` invokes the reconciler when the ADR says so.
- **Acceptance:** After deploying onto a host with a manually deleted rule, postdeploy is green without manual action.

## Deploy path and config hash

### F1 – Config hash is driven by a single runtime file

- **Evidence:** `deploy.sh:177` `compute_monitoring_config_hash` lists four files; of these `stacks/monitoring/alertmanager/alertmanager.yml` (absent) is skipped, while `stacks/monitoring/vmalert/vmalert.yml` and `stacks/monitoring/victoriametrics/victoriametrics.yml` are mounted by no container. Only `stacks/monitoring/vmagent/vmagent.yml` counts. [V 2026-09-23]
- **Impact:** Changes to `vmalert/rules/*`, `stacks/monitoring/vector/vector.yaml`, the Alertmanager template or Grafana provisioning do not change the hash, so containers are not recreated and the deploy silently keeps old configuration. Together with F29 the mechanism is close to inert.
- **Proposed fix:** Derive the hash input from the compose file's bind-mounted config paths (one list, one source), or hash each service's mounted config into its own label.
- **Test:** `tests/guards` — every read-only config bind mount in compose is covered by the hash input; a missing file in the hash list fails the test.
- **Acceptance:** Changing any mounted config file changes the affected service's label value (checked in the guard test by computing the hash over a fixture change).
- **Progress (2026-09-29, R1.12):** the operator chose the per-service variant, started with vector because F58 changes `stacks/monitoring/vector/vector.yaml`, which no hash covered. `deploy.sh` gained `compute_file_hash` (content only, no paths; dies on a missing file) and exports `VECTOR_CONFIG_HASH`; vector carries `homelab.config-hash=${VECTOR_CONFIG_HASH:-unset}`. Tests commit `f2e01b2`: `tests/guards/test_54_vector_config_hash.py` (4 strict xfails, static), postdeploy `test_vector_label_matches_config_hash` in `tests/postdeploy/test_40_vector_pipeline.py`. The global `MONITORING_CONFIG_HASH` and the other services are unchanged; status stays `open`.

### F2 – Hash list names a missing file and two unmounted ones

- **Evidence:** `deploy.sh:177`; `stacks/monitoring/alertmanager/alertmanager.yml` (absent), only `stacks/monitoring/alertmanager/alertmanager.yml.tmpl` exists; `stacks/monitoring/vmalert/vmalert.yml`, `stacks/monitoring/victoriametrics/victoriametrics.yml` unmounted. [V 2026-09-23]
- **Impact:** The list looks complete and is not; the `[[ -f ]]` filter hides the missing file.
- **Proposed fix:** Fixed by F1's derived list; until then, fail on a missing listed file instead of skipping it.
- **Test:** Same guard test as F1.
- **Acceptance:** No listed hash input is absent or unmounted.

### F29 – Config-hash label missing on 5 of 10 services

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml` — `homelab.config-hash` on five services; missing on `victoriametrics`, `node-exporter`, `cadvisor`, `victorialogs`, `vector`. [V 2026-09-23]
- **Impact:** Even a correct hash cannot recreate these services; `vector.yaml` changes trigger nothing at all.
- **Proposed fix:** Add the label to every service that mounts configuration (together with F1).
- **Test:** `tests/guards/test_10_monitoring_compose_contract.py` — every service with a config bind mount carries the label.
- **Acceptance:** The test enumerates the services and fails when one lacks the label.
- **Progress (2026-09-29, R1.12):** vector now carries the label, with its own per-service value `VECTOR_CONFIG_HASH` (see F1). The generic "every config-mounting service carries a label" test is still missing; status stays `open`.

### F13 – Compose mounts a templates directory that does not exist

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:67` mounts `../alertmanager/templates`; `stacks/monitoring/alertmanager/templates` (absent). [V 2026-09-23]; Pi-side effect [I — on the Pi, `stat` the path: Docker creates it root-owned and empty].
- **Impact:** A root-owned empty directory appears in the working tree on the Pi, which can later block `git pull --ff-only` if templates are added.
- **Proposed fix:** Add the directory with a `.gitkeep`, or remove the mount.
- **Test:** `tests/guards` — every relative bind-mount source in compose exists in the repository.
- **Acceptance:** The guard test passes and fails on a mount to a non-existent path.

### F43 – ADR-0001 promises subnet validation the deploy path skips

- **Evidence:** `docs/architecture/adr/ADR-0001-networking-and-firewall.md:37-41`; `scripts/network/bootstrap-networks.sh` validates only when `MONITORING_SUBNET` etc. are set; `deploy.sh` does not export them. [V 2026-09-23]
- **Impact:** The ADR states a guarantee ("guarded against subnet overlap") that the deploy path does not deliver. `.claude/rules/host-runtime.md` describes reality correctly; the ADR is the defect.
- **Proposed fix:** Correct the ADR, or fix F16 so the promise becomes true — decide in the R1 host-reconciliation ADR.
- **Test:** Follows F16.
- **Acceptance:** ADR text and `deploy.sh` behaviour agree, checked by reading both after the change.

### F16 – Network bootstrap on deploy skips subnet/bridge validation

- **Evidence:** `deploy.sh` calls `scripts/network/bootstrap-networks.sh` without subnet/bridge variables; `scripts/network/cleanup-ufw.sh`, `stacks/core/docker/daemon.json` (`metrics-addr 172.20.0.1:9323`) and `tests/postdeploy/test_35_network_and_ufw.py` depend on `br-monitoring` / `172.20.0.0/16`. [V 2026-09-16]; fresh-host effect [I].
- **Impact:** On a fresh host `monitoring` would be created with a random subnet and bridge name, breaking the firewall rules and the Docker metrics address.
- **Proposed fix:** Export the network parameters from one versioned source in `deploy.sh`.
- **Test:** `tests/guards` — `deploy.sh` passes the subnet and bridge variables; `tests/postdeploy/test_35_network_and_ufw.py` already checks the attributes.
- **Acceptance:** Deploying onto a host without the `monitoring` network yields `br-monitoring` / `172.20.0.0/16`.

### F17 – `daemon.json` applied before the network it references exists

- **Evidence:** `deploy.sh` main order — `scripts/host/ensure-docker-daemon-json.sh` runs before `scripts/network/bootstrap-networks.sh`; `stacks/core/docker/daemon.json` binds `metrics-addr` to the monitoring gateway. [V 2026-09-16]; Docker behaviour on a missing address [I].
- **Impact:** On a fresh host Docker may fail to start or silently not expose metrics.
- **Proposed fix:** Bootstrap networks first, or make the metrics address independent of the bridge. Decide in the R1 ADR.
- **Test:** `tests/guards` — order assertion on `deploy.sh`; `tests/postdeploy/test_05_docker_daemon_json_and_metrics.py`.
- **Acceptance:** The order test encodes the chosen sequence; metrics test green after a fresh-host deploy.

### F18 – Any `daemon.json` change restarts Docker during deploy

- **Evidence:** `scripts/host/ensure-docker-daemon-json.sh` with `RESTART_DOCKER_ON_CHANGE=1` as called by `deploy.sh`. [V 2026-09-16]
- **Impact:** A one-line daemon change restarts every container during an ordinary deploy, without a maintenance window or a backup step.
- **Proposed fix:** Split into plan/apply like `scripts/host-runtime/`: deploy reports the pending change, an explicit operator target applies and restarts.
- **Test:** `tests/guards` — `deploy.sh` does not enable the restart flag by default.
- **Acceptance:** A deploy with a changed `daemon.json` does not restart Docker and prints the pending action.

### F19 – Host-specific literals in reconciliation scripts

- **Evidence:** `scripts/network/cleanup-ufw.sh` (usage path `/home/admin/iac/…`, bridge names `br-abe`, `br-bd2` in a regex); `scripts/network/bootstrap-networks.sh` (fixed temp file `/tmp/bootstrap-networks.overlap`). [V 2026-09-16]
- **Impact:** Stale literals mislead and may match or miss the wrong bridges; a fixed temp file races.
- **Proposed fix:** Remove the stale names, use `mktemp`, derive paths from the repo root.
- **Test:** `tests/guards` — no `/home/` literals and no fixed `/tmp/` paths in `scripts/`.
- **Acceptance:** Guard test passes; ShellCheck clean.

### F20 – `ensure-journald-read.sh` default user does not match its use

- **Evidence:** `scripts/host/ensure-journald-read.sh` defaults `TARGET_USER=vector`; `deploy.sh` passes `admin`; vector runs as uid 65532 with the GID via `group_add`. [V 2026-09-16]; relevance of `admin` membership [I].
- **Impact:** Confusing default; the step may be unnecessary for vector.
- **Proposed fix:** Decide whether the user membership is needed; remove the step or fix the default and document it.
- **Test:** `tests/postdeploy/test_45_host_journald_units_to_victorialogs.py` proves journald ingestion either way.
- **Acceptance:** Journald logs arrive in VictoriaLogs with the step removed or corrected.

## Compose hardening

### F41 – No static guard for the compose hardening contract

- **Evidence:** `tests/guards/test_10_monitoring_compose_contract.py:12-22` — checks presence only. `vector` was missing from `REQUIRED_SERVICES` and was **added 2026-09-24** (Phase 8, V8.2); the hardening contract itself is still open. [V 2026-09-24]
- **Impact:** Every hardening property in this report can regress silently; F7, F27, F28, F29, F32, F33 and F38 all need this test as their home.
- **Proposed fix:** Extend the guard test into a per-service contract: pinned image, `read_only`, `cap_drop`, `no-new-privileges`, healthcheck, `user`, restart policy, allowed exceptions listed explicitly.
- **Test:** `tests/guards/test_10_monitoring_compose_contract.py` itself.
- **Acceptance:** Removing any contract property from any service makes the test fail with the service and property named.
- **Progress (2026-10-01, R1.19):** `cap_drop` is part of the contract: `test_every_service_drops_all_capabilities` requires `cap_drop: [ALL]` for every service, `test_cadvisor_cap_add_is_the_measured_set` allows `cap_add` only for cadvisor's measured set (F57). `read_only`, `no-new-privileges`, healthcheck and `user` remain open.
- **Progress (2026-10-01, R1.20):** `no-new-privileges` is part of the contract: `test_every_service_sets_no_new_privileges` requires it for every service and refuses `false` (F57). `read_only`, healthcheck and `user` remain open.
- **Progress (2026-10-01, R1.21):** `read_only` is part of the contract: `test_every_service_has_a_read_only_rootfs` requires it for every service except those in `READ_ONLY_EXCEPTIONS` — today only grafana, tracked here — and `test_read_only_exceptions_are_current` refuses a stale entry (F57). Healthcheck, `user` and grafana's `read_only` remain open.

### F7 – Missing restart policy and healthchecks

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml` — `victorialogs` has no `restart` and no healthcheck; `node-exporter` and `cadvisor` have no healthcheck. [V 2026-09-16]
- **Impact:** A crashed VictoriaLogs stays down; unhealthy exporters are not visible to `depends_on`.
- **Proposed fix:** Add `restart: unless-stopped` and healthchecks.
- **Test:** F41 contract test; `tests/postdeploy/test_10_containers.py` asserts `healthy`.
- **Acceptance:** All services report `healthy` after deploy.
- **Measured (2026-09-29, reboot during R1.15):** after a controlled reboot of the Pi, `homelab-home-prod-mon-victorialogs-1` stayed `Exited (0)` with `restart=no`, while every other long-running service (`restart=unless-stopped`) was up again [V 2026-09-29, operator]. Postdeploy failed on `test_ready_health_endpoints_strict_200[victorialogs-insert-ready]` (`1 failed, 16 passed`); `sudo ./deploy.sh` started it again (`79 passed, 3 skipped`). `tests/postdeploy/test_10_containers.py:45-55` expects `running` for only seven services — `victorialogs`, `vector` and `socket-proxy` are missing — so it passed with VictoriaLogs stopped. [V 2026-09-29]. Severity raised from Med to High: every reboot, including the automatic one at 03:30 (F61), silently stops the log pipeline until the next deploy. Proposed as its own increment (the `restart` part) before F60's remaining checks; the healthchecks stay in group f.
- **Progress (2026-09-29, R1.16 on `fix/r1-victorialogs-restart`):** tests commit `c79fcb3`: service classes come from the compose file (`tests/_lib/compose_services.py`, `ONE_SHOT_SERVICES`); guard `test_long_running_services_restart_unless_stopped` in `tests/guards/test_10_monitoring_compose_contract.py` (strict xfail, failing with `{'victorialogs': None}` under `--runxfail`) and `test_one_shot_services_exist_and_do_not_restart` (green from the start); `tests/postdeploy/test_10_containers.py` expects `running` for every long-running service, checks restarting/unhealthy for real and the containers' `RestartPolicy`. Fix: `restart: unless-stopped` for `victorialogs`. Status `partly` — the `restart` part is done once a reboot without a deploy leaves every long-running container up; the healthchecks for `victorialogs`, `node-exporter` and `cadvisor` remain (group f).
- **Progress (2026-09-29, R1.16 deployed):** merge `e652be8` (PR #53; `c79fcb3` tests, `bd4648c` fix), CI green. Measured on the Pi [V 2026-09-29, operator]: the deploy recreated `victorialogs`, postdeploy `80 passed, 3 skipped`; after a controlled reboot **without** a deploy all 10 long-running containers were `Up`, the renderer `Exited (0)`, and postdeploy was `80 passed, 3 skipped`. The `restart` part is done; severity back to Med (operator, 2026-09-29). Open: healthchecks for `victorialogs`, `node-exporter`, `cadvisor` (group f).

### F33 – vector has no healthcheck

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:362-393`. [V 2026-09-23]
- **Impact:** A stuck log pipeline shows as running.
- **Proposed fix:** Enable vector's API health endpoint and check it.
- **Test:** F41 contract test; `tests/postdeploy/test_40_vector_pipeline.py`.
- **Acceptance:** `docker inspect` shows a health status for vector.

### F27 – Container uid left to image defaults for 8 of 10 services

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml` — `user:` only on `node-exporter` (65534) and `vector` (65532). [V 2026-09-23]; actual uid per image [I — `docker image inspect -f '{{.Config.User}}'` per pinned image].
- **Impact:** An image bump can silently change the runtime uid — exactly the drift pinning prevents elsewhere.
- **Proposed fix:** Pin `user:` explicitly per service, with the documented exceptions.
- **Test:** F41 contract test.
- **Acceptance:** Every service has `user:` or an explicit exception entry.

### F32 – Grafana runs without `read_only` on a wrong justification

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:271-276` — the comment claims `read_only` would break the data volume; it covers the root filesystem only. [V 2026-09-23]; feasibility with a tmpfs `/tmp` [I].
- **Impact:** A writable root filesystem in the only LAN-exposed UI.
- **Proposed fix:** `read_only: true` plus `tmpfs: /tmp`; fix the comment.
- **Test:** F41 contract test; `tests/postdeploy/test_20_health_endpoints.py`.
- **Acceptance:** Grafana healthy with `read_only: true`.

### F38 – `depends_on` ignores existing healthchecks

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml:175-177,206-210,372-374` use `service_started`. [V 2026-09-23]
- **Impact:** Dependants start before their upstream is ready; startup is order-dependent.
- **Proposed fix:** `condition: service_healthy` where the upstream has a healthcheck.
- **Test:** F41 contract test.
- **Acceptance:** No `service_started` against a service that has a healthcheck.

### F72 – node-exporter shares the host PID namespace without a recorded reason

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml`, service `node-exporter`: `pid: host` together with `--path.rootfs=/host` and the mount `/:/host:ro,rslave` [V 2026-10-02, read]. No ADR or comment says why it needs the host PID namespace. `.claude/rules/compose-stacks.md` names only cadvisor as a documented exception. Found while planning R1.23 for cadvisor's `pid: host`. For cadvisor, R1.23's M1 showed that the host `/` bind mount brings the host's `/proc` along (`/rootfs/proc` of type `proc`, `1/comm` = `systemd`, 196 PIDs on both sides) [V 2026-10-02, operator]. Whether node-exporter's collectors read process data through `/host/proc` or through its own `/proc` is [I]: check its `--path.procfs` default under `--path.rootfs` and compare the `node_*` families before and after on the Pi.
- **Impact:** node-exporter sees every host process and can signal none, since it runs as `65534` with `cap_drop: [ALL]`. The risk is information exposure, and the namespace share is a host-level exception the rules do not record.
- **Proposed fix:** Measure as in R1.23: list the `node_*` families, drop `pid: host`, compare after the deploy. If something is lost, record the reason in an ADR; otherwise remove the entry from `PID_HOST_ALLOWLIST`.
- **Test:** `tests/guards/test_10_monitoring_compose_contract.py` — `test_no_service_shares_the_host_pid_namespace` with `PID_HOST_ALLOWLIST` empty; postdeploy — a family check for node-exporter like `test_25`'s for cadvisor.
- **Acceptance:** node-exporter runs without `pid: host` and with the same `node_*` families, or an ADR records why it needs the namespace and the allowlist cites it.
- **Prevention:** Rung: static guard in CI. `test_no_service_shares_the_host_pid_namespace` (R1.23) refuses a new `pid: host` without an allowlist entry that names an open finding or ADR; this finding is that entry for the existing case.

## Supply chain and pinning

### F3 – Images pinned by tag, not by digest

- **Evidence:** `stacks/monitoring/compose/docker-compose.yml`, all ten images. [V 2026-09-23 via `image-pin-audit`]
- **Impact:** A re-pushed tag changes what deploys without a repository change.
- **Proposed fix:** `image: name:tag@sha256:…`, with Renovate `pinDigests` so updates stay controlled.
- **Test:** `tests/guards` — every compose image reference carries a digest.
- **Acceptance:** The test passes for all images and fails for a tag-only reference.

### F4 – Renovate manages compose images only

- **Evidence:** `renovate.json5` `enabledManagers: ["docker-compose"]`; `.github/workflows/ci.yml` uses `actions/checkout@v4`, `actions/setup-python@v5`, `actions/cache@v4`; `.pre-commit-config.yaml` hook revs; pip ranges; the Grafana plugin pin. [V 2026-09-23]
- **Impact:** Everything outside compose drifts without a proposal; Actions tags are mutable.
- **Proposed fix:** Enable `github-actions`, `pre-commit`, `pip_requirements` managers; pin Actions by SHA; a regex manager for the Grafana plugin.
- **Test:** `tests/precommit` — every manager in a required list is enabled; `scripts/renovate/validate-config.sh` validates syntax.
- **Acceptance:** A Renovate dry run (`make renovate-check`, operator) lists proposals for each manager.
- **Re-planned (2026-09-26):** moved from group g to stage R2d (dev-environment lifecycle, `.claude/roadmap.md` §9.2). The pins in `requirements-dev.txt` and `.pre-commit-config.yaml` must move in one PR, because `tests/precommit/test_50_toolchain_version_parity.py` requires them to match; Actions digest pinning may stay with F3.
- **Progress (2026-09-29):** a second unmanaged class found while planning R1.11: helper images hardcoded in the postdeploy tests — `curlimages/curl:8.11.1` (`tests/postdeploy/test_20_health_endpoints.py:26`, `tests/postdeploy/test_25_cadvisor_metrics.py:13`, `tests/postdeploy/test_26_docker_socket_proxy.py:28`), `alpine:3.20` (`tests/postdeploy/test_22_victorialogs_stats_query.py:125`, `tests/postdeploy/test_25_cadvisor_metrics.py:41`, `tests/postdeploy/test_31_vmagent_targets.py:21`, `tests/postdeploy/test_35_docker_engine_metrics.py:74`, `tests/postdeploy/test_35_network_and_ufw.py:139`), `busybox:1.36` (`tests/postdeploy/test_40_vector_pipeline.py:95`). Renovate cannot see them: `renovate.json5:14` enables only `docker-compose`, and `renovate.json5:30` limits it to the monitoring compose file [V 2026-09-29]. Proposed addition to the fix: one constants module for these images plus a `regex` manager for it (or a `customManagers` entry matching `*_IMAGE = "…"` under `tests/`); test: every image literal under `tests/` comes from that module.

### F24 – Renovate validator hook runs a floating image tag

- **Evidence:** `scripts/renovate/validate-config.sh` runs `renovate/renovate:43`; `Makefile:85` pins the same image by digest; `.pre-commit-config.yaml` calls the script. [V 2026-09-23]
- **Impact:** Two versions of the validator; the hook needs Docker and a registry pull.
- **Proposed fix:** Share the digest pin from one place (e.g. a variable file read by both).
- **Test:** `tests/precommit` — both references resolve to the same digest.
- **Acceptance:** The test fails when one of the two drifts.

### F44 – Stale image tag in a Markdown example

- **Evidence:** `stacks/core/docker/docker-daemon-json-handling.md:93` shows `grafana/grafana:11.0.0`; deployed is `11.6.16` (`stacks/monitoring/compose/docker-compose.yml:239`); `renovate.json5` reads compose files only. [V 2026-09-23]
- **Impact:** Documentation examples drift permanently; readers copy old versions.
- **Proposed fix:** Replace with a placeholder (`grafana/grafana:<pinned>`) or reference the compose file.
- **Test:** `tests/guards` — no concrete `image:` tags in Markdown outside ADRs.
- **Acceptance:** The guard test passes.

## Toolchain and tests

### F9 – Backup scripts have no tests although ADR-009 requires them

- **Evidence:** `docs/architecture/adr/ADR-009-backup-verify-restore.md` DD-012 and §14.2; no backup test under `tests/`; the scripts in `scripts/backup/` already implement exit codes (`scripts/backup/common.sh:12-17`), locking and restore guards. [V 2026-09-23 via `backup-progress`]
- **Impact:** Five of seven ADR-009 requirements are implemented but unproven; the ADR's own acceptance rule is unmet.
- **Proposed fix:** R3 — fixture tests from ADR-009 §14.2 using the existing fixture overrides.
- **Test:** New `tests/backup/` (or `tests/guards`) fixture suite running in CI.
- **Acceptance:** Fixture tests for exit codes, lock contention and restore guards green in CI; `make backup`/`backup_verify` green on the Pi.

### F23 – Tests marked `lint` are never run by any gate

- **Evidence:** `tests/precommit/test_15_json_valid.py:22`, `tests/precommit/test_20_yamllint.py:11`, `tests/precommit/test_25_no_merge_conflict_markers.py:31`, `tests/precommit/test_35_large_files.py:54` carry `@pytest.mark.lint`; `Makefile:286` selects `-m precommit`, `Makefile:292` ignores `tests/precommit`; nothing in `Makefile`, `pyproject.toml` or `.github/workflows/ci.yml` selects `lint`. Three files say the check moved to pre-commit hooks. [V 2026-09-23]
- **Impact:** Four test files are dead code that looks like coverage. (Sharpened 2026-09-23: originally recorded for `test_15` only.)
- **Proposed fix:** Delete the four files (pre-commit hooks `check-json`, `check-yaml`, `check-merge-conflict`, `check-added-large-files` cover them), or run `-m lint` in a gate.
- **Test:** `tests/precommit` — every marker registered in `pyproject.toml` is selected by at least one `Makefile` target.
- **Acceptance:** No test exists that no gate runs.

### F47 – The cadvisor doctor test never runs; its skip hides a compose error

- **Evidence:** `tests/doctor/test_35_cadvisor_flags.py:36-55` renders the compose file with a test env that sets neither `DOCKER_GID` nor `SYSTEMD_JOURNAL_GID`, and calls `pytest.skip` on **any** non-zero exit of `docker compose config`. `stacks/monitoring/compose/docker-compose.yml:377` `group_add` then receives two empty values. Measured in `make ci` on 2026-09-24: `SKIPPED [1] tests/doctor/test_35_cadvisor_flags.py:52: … services.vector.group_add items at 0 and 1 are equal`. [V 2026-09-24]
- **Impact:** The cadvisor flag checks have never run in CI or locally, but the result reads "1 skipped", which looks like a platform limitation. It is the same false-green class as F23: a test that exists but cannot fail.
- **Proposed fix:** Set both GIDs to distinct dummy values in the test env. Skip only when the compose plugin is missing; any other `config` failure must `pytest.fail` with stderr.
- **Test:** The test itself. A negative check: an env without the GIDs must make it **fail**, not skip.
- **Acceptance:** `make ci` shows `test_35_cadvisor_flags` as PASSED. Removing a GID from its env produces FAILED with the compose stderr.
- **Progress (2026-09-29):** the compose error disappeared as a side effect of R1.10 (F30): vector's `group_add` now holds only `${SYSTEMD_JOURNAL_GID}`, so there are no longer two equal empty items. Measured in `make ci` on `feat/r1-socket-proxy` [V 2026-09-29]: the skip moved to `tests/doctor/test_35_cadvisor_flags.py:147: cadvisor image not present locally: ghcr.io/google/cadvisor:v0.60.5`. The test still does not run, and its any-failure skip is unchanged, so the defect stands; status stays `open`.
- **Progress (2026-09-29, R1.11):** after the operator pulled `ghcr.io/google/cadvisor:v0.60.5` in WSL, `make ci` showed `test_cadvisor_flags_are_supported_by_pinned_image` PASSED for the first time [V 2026-09-29] — it proved `--docker` before the R1.11 deploy, and still passes after the revert. It runs only because of that manual pull: `tests/doctor/test_35_cadvisor_flags.py:146-147` skips when the image is missing instead of pulling it, so after a Renovate bump of the cadvisor tag it silently skips again until someone pulls the new tag, and in GitHub CI it never runs. `tests/guards/test_32_alertmanager_renderer_container.py:91` already pulls its pinned image itself. Proposed addition to the fix: pull the image named in compose (as test_32 does) and fail, not skip, when the pull fails; skip only when Docker itself is missing outside CI. Status stays `open`.

### F25 – JSON test scans git-ignored files

- **Evidence:** `tests/precommit/test_15_json_valid.py:13-19` rglobs every `*.json`, including git-ignored files; it fails on the operator's JSONC editor settings. [V 2026-09-18, run result `1 failed, 3 passed`]
- **Impact:** Invisible today only because of F23; would fail as soon as the test is re-enabled.
- **Proposed fix:** Resolved by deleting the test (F23), or iterate `git ls-files '*.json'` instead of `rglob`.
- **Test:** The test itself on a fixture tree with an ignored invalid file.
- **Acceptance:** An ignored invalid JSON file does not fail the test; a tracked one does.

### F11 – `.gitattributes` does not pin LF for all text types

- **Evidence:** `.gitattributes` covers sh/yml/yaml/json/toml but not `*.md`, `*.py`, `Makefile`, `*.json5`. [V 2026-09-16]
- **Impact:** On the Windows side of the operator's machine a checkout can introduce CRLF (K9 in `ClaudeTransition.md`).
- **Proposed fix:** `* text=auto eol=lf` plus explicit binary types.
- **Test:** `tests/precommit` — no tracked text file contains `\r`.
- **Acceptance:** `git ls-files --eol` shows `lf` for all text files.

### F50 – The WSL layer (Python, Docker Desktop, apt) is neither documented nor checked

- **Evidence:** `docs/operations/DevWorkflow.md` covers `make venv` but not the WSL host (Python version, Docker Desktop and its WSL integration, apt/Ubuntu release); `docs/operations/runtime-updates.md` covers the Pi only; `Makefile` target `doctor` reports `FAIL: docker missing` without diagnosis or pointer. Measured 2026-09-26: `make ci` stopped in `doctor` because Docker Desktop's WSL integration was off. `.github/workflows/ci.yml` pins Python `3.12` without a patch level; WSL uses the system `python3` (3.12.3). [V 2026-09-26]
- **Impact:** A change in the WSL environment blocks or silently alters the gate that every increment relies on, and nothing tells the operator how to recover or what is expected.
- **Proposed fix:** R2d — `docs/operations/dev-environment-updates.md` (checklist and recovery), `make doctor` version checks (Python minor as in CI, Docker and Compose plugin present) with a pointer to the doc.
- **Test:** `tests/doctor` — the version checks, with a clear message per missing or mismatched tool.
- **Acceptance:** With Docker's WSL integration off, `make doctor` fails with a message naming the fix; the doc describes the update and recovery flow.

### F56 – Deploy log records postdeploy as `passed` without counts; the evidence is not kept

- **Evidence:** `deploy.sh:290-294` (`run_postdeploy_tests`) runs `make postdeploy` and then logs only `tests: passed`; `log()` at `deploy.sh:66` writes to stdout, and `deploy.sh` redirects nothing to a file (no `tee`/`exec >`). The `Makefile` can tee output to `logs/<target>-<ts>.log` only with opt-in `LOG=1` (`Makefile:101`), which `deploy.sh:293` does not set. Measured by the operator on 2026-09-28 (deploy of merge `ed8e008`): the deploy summary shows `tests: passed` and `deploy: done` with no pass/skip counts; the "62 passed, 4 skipped" in the log rows of `.claude/roadmap.md` §7 comes from the operator reading it off the pytest output, not from any kept record. [V 2026-09-28]; whether pytest's own summary line reliably reaches the operator's terminal view [I — the operator confirms on the next deploy].
- **Impact:** IN7 makes "postdeploy green" part of *done*, but the only kept evidence is a word. A test that starts skipping (the false-green class of F47 and F23) or a test that vanishes leaves `tests: passed` unchanged, so a regression in coverage cannot be seen from the deploy log, and every increment log row has the same gap.
- **Proposed fix:** `run_postdeploy_tests` records the pytest result: write a JUnit XML (`--junitxml`) or capture the summary line to a host log path outside the checkout, and log `tests: passed (<n> passed, <m> skipped, …)` — or `tests: FAILED (…)` before `die`. Decide the host path together with the log location of the backup scripts (`docs/operations/BackupVerifyRestore.md` names `logs/`). IN9 check at fix time: a new host file.
- **Test:** `tests/guards` — run `run_postdeploy_tests` (or an extracted helper) with a stub `make` that prints a pytest summary; assert the logged line carries the counts, and that a failing stub is logged as failed with its counts.
- **Acceptance:** The next deploy log shows `tests: passed (<n> passed, <m> skipped …)`; the increment log rows cite that line instead of an operator reading.
- **Progress (2026-09-29):** the [I] part is answered. On the deploy of merge `68a3118` (R1.7) pytest's own summary line `63 passed, 4 skipped in 15.86s` reached the operator's terminal [V 2026-09-29, operator]. It was read from the terminal, not from a kept file, so the defect stands: `deploy.sh` still keeps no record of the counts. Status stays `open`.

### F69 – Journald ingestion test skips quiet units at once; the skip count varies between deploys

- **Evidence:** `tests/postdeploy/test_45_host_journald_units_to_victorialogs.py:181` calls `pytest.skip` inside the `_check` passed to `retry`. The checks for `systemd-udevd.service` and `ufw.service` set `allow_skip_if_no_events=True`. `retry` in `tests/postdeploy/conftest.py:59-74` catches only `AssertionError`, and pytest's skip exception is not one, so the first empty query skips the test without retrying [V 2026-10-02, read]. R1.22's deploy reported `96 passed, 4 skipped` where 97/3 was predicted: both units were skipped, while R1.21 had three skips in total [V 2026-10-02, operator: `SKIPPED … test_45 …:181: No entries for systemd-udevd.service found` and the same for `ufw.service`]. R1.17 had `82 passed, 4 skipped` (`.claude/increment-log.md`).
- **Impact:** For these two units the ingestion path into VictoriaLogs is never proven when they are quiet. That is the normal case, so a broken path stays green. The skip count changes from deploy to deploy, which makes the postdeploy summary unfit as exact evidence and turned R1.22's exact prediction into a miss.
- **Proposed fix:** The test writes a known entry itself, for example `systemd-cat -t <unit-identifier>` or `logger` with a unique marker, and queries for that marker with `retry`. If an identifier cannot be written that way, the unit's check is dropped with a stated reason instead of being skipped. The provoke steps change no host state (F70).
- **Test:** `tests/postdeploy/test_45_host_journald_units_to_victorialogs.py` itself, with no `allow_skip_if_no_events` left; `tests/guards` — a static check that no postdeploy test calls `pytest.skip` inside a `retry` callback.
- **Acceptance:** Two consecutive deploys report the same skip count, and `test_45` skips no unit.
- **Prevention:** Rung: static guard in CI. A guard that refuses `pytest.skip` inside a function passed to `retry`, and conditional skips without a finding ID in `tests/postdeploy`, would have caught this when the test was written. Until then the `increment-plan` skill tells a postdeploy prediction to name each variable skip (R1.22).

### F70 – Postdeploy changes udev's log level and re-triggers every device on the host

- **Evidence:** `tests/postdeploy/test_45_host_journald_units_to_victorialogs.py`, `_provoke_udevd`, runs `sudo udevadm control --log-level=info && sudo udevadm trigger && sudo udevadm settle` whenever the 24 h precheck finds no udev entry [V 2026-10-02, read]. `udevadm control --log-level` changes the running daemon's log level until the next restart or reboot. `udevadm trigger` with no filter replays a `change` event for every device on the host. Whether it ran on recent deploys is [I]: `journalctl -u systemd-udevd` around a deploy time would show it.
- **Impact:** Every deploy can change host runtime state that the repository does not record (IN18, "leave no trace"; CLAUDE.md §1, no manual changes on the Pi) and replays device events on a running system. A test that changes what it observes is no longer a postdeploy check of the deployed state.
- **Proposed fix:** Remove the host intervention. Prove ingestion with a marker written by `systemd-cat`/`logger` (F69), or drop the udev check with a reason.
- **Test:** `tests/guards` — no file under `tests/postdeploy` calls `udevadm control`, `udevadm trigger`, `systemctl restart|stop` or `sysctl -w` (a denylist with a self-tested example, like `test_59`).
- **Acceptance:** The guard passes and fails on a reintroduced `udevadm trigger`; a deploy leaves `udevadm control` state untouched.
- **Prevention:** Rung: static guard in CI — the denylist above. IN18 was written for Claude's measurements; the same rule for the test suite has no check yet.

### F71 – Postdeploy pulls and runs the unpinned `hello-world:latest`

- **Evidence:** `tests/postdeploy/test_45_host_journald_units_to_victorialogs.py`, `_provoke_docker` (`docker pull -q hello-world:latest`) and `_provoke_containerd` (`docker run --rm hello-world:latest`) [V 2026-10-02, read]. CLAUDE.md §4 (Determinism: pinned image versions, never `latest`) and IN10. Other postdeploy tests pin their helper images (`curlimages/curl:8.11.1` in `tests/postdeploy/test_25_cadvisor_metrics.py`). Whether `alpine:3.20` in the same tests counts as pinned enough is a separate question for group g (F3).
- **Impact:** Each deploy may fetch a different image from the network into the Pi's image store, unreviewed and outside Renovate. The step is small but outside the pinning contract.
- **Proposed fix:** Use an already pinned helper image (for example `curlimages/curl:8.11.1`) for the provoke steps, or the marker approach of F69, which needs no image at all.
- **Test:** `tests/guards` — every image reference in `tests/postdeploy/**/*.py` carries an explicit tag other than `latest`.
- **Acceptance:** The guard passes, and `grep -rn ':latest' tests/postdeploy` finds nothing.
- **Prevention:** Rung: static guard in CI — the image-reference check above, which `image-pin-audit` can share. The existing pinning checks cover compose files only.

## Host runtime updates

Reviewed 2026-09-26 (`scripts/host-runtime/`). The structure is sound — plan/apply split, no
automatic reboot, EEPROM separate, clean Git tree required, no `rpi-update`; the findings are about
what the scripts do not enforce. Scheduled in R3b, after backup (`.claude/roadmap.md` §9.6).

### F51 – Host upgrade apply does not execute the reviewed plan

- **Evidence:** `scripts/host-runtime/upgrade-apply.sh:26-28` runs `apt-get update`, `apt-get -y full-upgrade` and `apt-get -y autoremove --purge` afresh; `scripts/host-runtime/upgrade-plan.sh:27` only simulates and stores nothing. `DEBIAN_FRONTEND=noninteractive` (`scripts/host-runtime/upgrade-apply.sh:25`) without a `Dpkg::Options` conffile policy. [V 2026-09-26]; conffile behaviour under noninteractive [I — confirm with a stubbed `dpkg` in the R3b.1 harness or the Debian docs].
- **Impact:** What gets installed is whatever is current at apply time, not what the operator reviewed in the plan; `autoremove --purge` removes packages and their configuration that the plan never listed; a changed conffile can stall or silently replace configuration.
- **Proposed fix:** The plan writes `package=version` plus a timestamp to a host file; apply refuses if it is missing, stale, or differs from a fresh simulation; explicit `--force-confdef --force-confold`; the plan lists the `autoremove` set.
- **Test:** `tests/guards` with `PATH` stubs (F53) — apply refuses a missing/stale/different plan and passes the conffile options.
- **Acceptance:** A stubbed apply with a plan that differs from the simulation exits non-zero without calling `full-upgrade`.

### F52 – Mutating host-runtime scripts have no backup gate

- **Evidence:** `docs/operations/runtime-updates.md:34-39` and its acceptance list require backup and backup verification first; `scripts/host-runtime/upgrade-apply.sh` and `scripts/host-runtime/eeprom-apply.sh` check only `require_pi` and `require_clean_git_tree` (`scripts/host-runtime/common.sh:29,96`). [V 2026-09-26]
- **Impact:** The one safeguard that makes a host update reversible exists only on paper; an operator in a hurry can upgrade packages or the bootloader without a restorable backup.
- **Proposed fix:** After R3 provides a verified-backup record: both scripts refuse unless the last verified backup is younger than a set age; an explicit override flag with a logged reason.
- **Test:** `tests/guards` with stubs — apply refuses without, or with a stale, verification record; the override is logged.
- **Acceptance:** Without a fresh verified backup both scripts exit non-zero before any `apt-get` or `rpi-eeprom-update -a` call.

### F53 – host-runtime scripts are untestable off the Pi and untested

- **Evidence:** `scripts/host-runtime/common.sh:29` `require_pi` has no test override (the backup scripts use `HOMELAB_ALLOW_NON_PI`, `.claude/rules/backup-restore.md`); no file under `tests/` or `.github/` references the scripts (search 2026-09-26). Only ShellCheck covers them via `.pre-commit-config.yaml`. [V 2026-09-26]
- **Impact:** Every change to the scripts that mutate the host is first exercised on the Pi — the pattern that cost two fix-forward rounds in R1.
- **Proposed fix:** A `HOMELAB_ALLOW_NON_PI` test mode and `PATH` stubs for `apt-get`, `dpkg-query`, `rpi-eeprom-update`, `docker`, `sudo`.
- **Test:** `tests/guards/test_7x_host_runtime_*.py` — plan mutates nothing, apply refuses a dirty tree, EEPROM never runs in the routine path.
- **Acceptance:** The guard tests run in CI and fail when, for example, `upgrade-apply.sh` calls `rpi-eeprom-update -a`.

### F54 – Docker packages upgrade uncontrolled inside the routine APT upgrade

- **Evidence:** `scripts/host-runtime/upgrade-apply.sh:27` `full-upgrade` includes `docker-ce`, `containerd.io` and the Compose plugin, which `scripts/host-runtime/common.sh:153-176` only reports on; no `apt-mark hold`, no separate step, no postdeploy right after. [V 2026-09-26]; that a `docker-ce`/`containerd.io` upgrade restarts the daemon and all containers [I — standard package behaviour; observe in R3b.6].
- **Impact:** A routine security update can restart every service and change the container runtime without the deploy-time checks; related to F18.
- **Proposed fix:** ADR in R3b: hold the Docker packages and upgrade them in a separate controlled step (stop, upgrade, start, postdeploy), or accept the restart explicitly. Postdeploy minimum versions for Docker Engine and the Compose plugin.
- **Test:** `tests/guards` (stubs) for the chosen flow; `tests/postdeploy` minimum-version check.
- **Acceptance:** The ADR exists; the routine path cannot change the Docker packages unnoticed; the version check is green on the Pi.

### F55 – Plan output, audit and runtime-updates doc disagree; audit gaps pass silently

- **Evidence:** `docs/operations/runtime-updates.md:47-54` says the plan shows disk space and failed systemd units — `scripts/host-runtime/upgrade-plan.sh` prints neither (only `scripts/host-runtime/audit-runtime.sh:49,53` does); the doc uses `~/raspberry-pi-homelab` while the Pi checkout is `~/iac/raspberry-pi-homelab` (operator deploy output, 2026-09-25); "Last verified: 2026-05-21". `scripts/host-runtime/common.sh:61` skips a section with only a warning when sudo is not available non-interactively, and many calls end in `|| true`, so an incomplete audit exits 0; no machine-readable output or version history; the EEPROM release channel is never shown (`scripts/host-runtime/eeprom-apply.sh:22`). [V 2026-09-26]
- **Impact:** The operator reviews less than the doc promises, may follow a wrong path, and cannot tell a complete audit from a partial one or see version drift over time.
- **Proposed fix:** R2b corrects the doc; R3b adds the missing plan output, a machine-readable audit summary (versions, EEPROM channel, reboot state) and a distinct exit code for an incomplete audit.
- **Test:** `tests/guards` (stubs) — audit without sudo reports "incomplete" with its exit code; the plan prints disk and failed units.
- **Acceptance:** Doc and scripts agree; an incomplete audit is distinguishable by exit code.

### F61 – unattended-upgrades runs on the Pi, outside the documented host update flow

- **Evidence:** measured by the operator on the Pi on 2026-09-29 [V 2026-09-29, operator]: `unattended-upgrades 2.12` installed (`ii`); `/etc/apt/apt.conf.d/20auto-upgrades` sets `APT::Periodic::Update-Package-Lists "1"` and `APT::Periodic::Unattended-Upgrade "1"`; `apt-daily.timer` and `apt-daily-upgrade.timer` are active (last runs 2026-09-29 07:32 and 06:30). Allowed origins: `origin=Debian,codename=trixie-updates`, `origin=Debian,codename=trixie,label=Debian`, `origin=Debian,codename=trixie,label=Debian-Security`, `origin=Debian,codename=trixie-security,label=Debian-Security` — neither the Raspberry Pi archive nor the Docker repository, so kernel and Docker packages are not upgraded automatically. `mkvtoolnix` is among the installed packages it upgrades, which is unexpected on a deploy-only host. `/etc/apt/apt.conf.d/99-auto-reboot` (dated 2026-01-01, like `50unattended-upgrades` and `/etc/fstab`) sets `Unattended-Upgrade::Automatic-Reboot "true"` and `Unattended-Upgrade::Automatic-Reboot-Time "03:30"`; `50unattended-upgrades` holds only the four `Origins-Pattern` entries above and an empty `Package-Blacklist`; `/var/run/reboot-required` did not exist on 2026-09-29. In the repository: `docs/operations/runtime-updates.md` describes only the manual plan/apply flow (`make host-upgrade-plan`, `make host-upgrade-apply`, backup first) and mentions unattended updates only at line 97 for EEPROM; no file under `scripts/`, `docs/` or `stacks/` names `unattended-upgrades`, `apt-daily` or `20auto-upgrades` (search 2026-09-29). [V 2026-09-29]. With the F60 hook (R1.15) the run of 2026-09-30 06:04 installed `libaudit-common libaudit1 libssh2-1t64 libtiff6 mkvtoolnix rsync zip` (`All upgrades installed`), no `/var/run/reboot-required` afterwards [V 2026-09-30, operator]. The only trail of such a run is the unattended-upgrades log under `/var/log` and the journal; the journal is volatile and vector does not forward `apt-daily-upgrade.service` (F60, answered question) [V 2026-09-30].
- **Impact:** The Pi reboots itself at 03:30 whenever an unattended upgrade requires it, although `docs/operations/runtime-updates.md:240` ("No automatic reboot") and `.claude/rules/host-runtime.md:31` promise none; nothing runs postdeploy after such a reboot. Packages change on the Pi every morning without the plan, the backup gate (F52) or a postdeploy run, and without any record in the repository; the documented flow suggests an operator-controlled host that does not exist. A failure stays invisible — it went unnoticed until F60. Whether automatic security updates are wanted is a legitimate choice, but it is undocumented and unconfigured from the repository.
- **Proposed fix:** Decide in an ADR (R3b, with F51/F52/F54): keep automatic security updates, with `20auto-upgrades` and the origins pattern managed from the repository, a failed run alerting, and `runtime-updates.md` describing both paths — or disable them and rely on the controlled flow with a fixed cadence. Record the host package inventory, so a package like `mkvtoolnix` is either justified or removed. The alert on a failed run needs a trail that survives a reboot — a persistent journal, or vector forwarding `apt-daily-upgrade.service` and the `homelab-boot-firmware` identifier to VictoriaLogs.
- **Test:** `tests/postdeploy` — the unattended-upgrades configuration on the Pi equals the one in the repository (or the service is disabled, per the ADR); a check that the last unattended-upgrades run did not fail.
- **Acceptance:** The ADR exists; the Pi's configuration matches the repository and is checked by postdeploy; `runtime-updates.md` describes every path that changes host packages.

### F63 – The memory cgroup Docker relies on is enabled by a hand-edited kernel command line outside the repository

- **Evidence:** measured by the operator on the Pi in the journal of the boot of 2026-10-01 09:25:13 (`journalctl -b`) [V 2026-10-01, operator]: `Kernel command line: reboot=w coherent_pool=1M 8250.nr_uarts=1 pci=pcie_bus_safe cgroup_disable=memory numa_pol…` (truncated by the pager), then `cgroup: Disabling memory control group subsystem`, `cgroup: Enabling memory control group subsystem` and `Unknown kernel command line parameters "cgroup_memory=1", will be passed to user space.` The firmware's `cgroup_disable=memory` is therefore overridden by a parameter later on the line — very likely `cgroup_enable=memory` from `/boot/firmware/cmdline.txt` [I — `cat /boot/firmware/cmdline.txt`; the full line via `journalctl -b -k --no-pager -g 'Kernel command line'`]; `cgroup_memory=1` is unknown to kernel `6.18.29+rpt-rpi-2712` and has no effect. The repository holds no `cmdline.txt` (absent), and no file mentions it, `cgroup_memory` or `cgroup_enable` (`git grep`, 2026-10-01), and no test checks that the memory controller is available [V 2026-10-01]. `/boot/firmware` is mounted read-only (F60, ADR-0013), so the file was edited by hand while the partition was writable.
- **Impact:** Docker's memory limits and accounting, and the container memory metrics cAdvisor reports, depend on a boot setting that exists only on this host. A re-imaged Pi, a restore onto fresh Raspberry Pi OS or a firmware package that rewrites `cmdline.txt` would boot without the memory controller, and nothing would say so: containers start, limits are silently ignored, memory panels go empty. The unknown `cgroup_memory=1` is noise in every boot log.
- **Proposed fix:** Group e (which host state `deploy.sh` reconciles and which stays manual, by ADR). First, independent of that decision: a postdeploy check that makes the dependency explicit. Then either record `cmdline.txt` in the repository with a `check`-only reconciliation (no write to the read-only partition from `deploy.sh`) and a documented manual procedure through the ADR-0013 remount, or name it in the ADR as manual host state with the procedure in `docs/operations/runtime-updates.md`. Drop `cgroup_memory=1` in the same change.
- **Test:** `tests/postdeploy` — `/sys/fs/cgroup/cgroup.controllers` contains `memory`; once recorded, the kernel command line (`/proc/cmdline`) contains `cgroup_enable=memory` and not `cgroup_memory=1`.
- **Acceptance:** The postdeploy check is green on the Pi and fails with an actionable message when the memory controller is missing; the kernel command line, or the decision to keep it manual, is recorded in the repository.

### F64 – No proactive host best-practice check; deviations surface only by accident

- **Evidence:** F62 (volatile journal) was noticed while tracing F60 and F63 (kernel command line) in the first persistent boot journal (`.claude/increment-log.md`, R1.18) — neither by a check that looks for them. `scripts/host-runtime/audit-runtime.sh:16-66` prints host identity, APT, EEPROM, Docker, failed units, mounts and UFW, but compares none of it against an expected state, and covers neither journald storage, time sync, SSH, swap nor the cgroup controllers. `.claude/rules/host-runtime.md` lists what `deploy.sh` reconciles, not what the host should look like. The postdeploy checks test the deployed stack and the host state each increment touched (`tests/postdeploy/test_06_host_boot_firmware.py`, `tests/postdeploy/test_07_host_journald_persistent.py`). [V 2026-10-01]
- **Impact:** A host setting that contradicts a well-known practice for a Raspberry Pi server stays until it costs something — F62 cost the evidence of two reboots. Nothing tells a deliberate deviation from an unnoticed one, so the triage rules (roadmap §2, IN14) only see what work happens to touch.
- **Proposed fix:** A host baseline in the repository: each item names its expected state, the source of the practice, and how to measure it read-only (for example persistent journal, NTP synchronised, SSH key-only, swap policy, memory cgroup, unattended-upgrades as decided in F61). A baseline audit compares the Pi against it and lists deviations; each deviation becomes a finding candidate (IN14), a postdeploy check, or a recorded exception. Measured once at every stage close. Each item has a stable ID and names the service classes that depend on it (for example the memory cgroup for every service with compose memory limits), so the R4 service DoD can refer to it under "Runtime prerequisites" (roadmap §9.7) and a changed item triggers a review of those services (roadmap §4).
- **Test:** `tests/guards` — every baseline item has expected state, source and a read-only measurement; `tests/postdeploy` — the items that are reconciled hold on the Pi.
- **Acceptance:** The baseline exists with sources, item IDs and dependent service classes; the first audit on the Pi is recorded and every deviation is a finding, a check or an exception; the stage-close step in roadmap §4 runs it.
- **Prevention:** F64 is itself the prevention for F62 and F63 (rung: stage-close audit instead of "noticed at a reboot"). Its own gap — a practice the baseline does not list yet — shows when a later finding matches no baseline item: the IN17 proposal for that finding then adds the item, and the guard above requires its source and measurement.
- **Evidence (added 2026-10-01, with F66):** `ls -la ~` of the operator account on the Pi [V 2026-10-01, operator] shows development leftovers on a deploy-only host (`.claude/CLAUDE.md` §1): `.vscode-server` (2026-02-05, VS Code remote server), `.dotnet` (2026-01-02, origin unknown [I], possibly a VS Code extension), `.pytest_cache` in the home directory (2026-01-12, pytest once ran outside the checkout). Baseline item to add: no development tools or caches on the Pi, or a recorded exception. The operator removed them later the same day, together with the compiler chain and the kernel headers (F67); also baseline items: the `sshd` settings, set by hand and not in the repository, and `PermitRootLogin` (F67 Evidence). Further baseline item, found the same day: `admin` has `NOPASSWD: ALL` from two distribution files (`010_pi-nopasswd`, `90-cloud-init-users`), so its SSH key is root-equivalent; restore over `ssh … 'sudo …'` relies on it, so a change needs a decision, not a cleanup (F67 SSH evidence).

### F68 – Backup inventory omits the host files deploy installs and the hand-edited `sshd_config`

- **Evidence:** `docs/architecture/adr/ADR-009-backup-verify-restore.md:388-400` (§5.4 "Host configuration exports") lists `/etc/docker/daemon.json` ("Also enforced by GitOps script") and `/etc/ssh/ssh_host_*`, but none of the other files `deploy.sh` installs on the host: the APT hook `/etc/apt/apt.conf.d/99homelab-boot-firmware` and `/usr/local/sbin/homelab-boot-firmware` (R1.15), the journald drop-in `/etc/systemd/journald.conf.d/60-homelab-persistent.conf` (R1.18), and since R1.21 the sshd drop-in `/etc/ssh/sshd_config.d/10-homelab-hardening.conf` (`.claude/rules/host-runtime.md`). Nor does it name `/etc/ssh/sshd_config`, whose `Match User admin` block (lines 131–134, F67 SSH evidence) was added by hand and exists nowhere in the repository. Found in R1.21 while answering IN9 for the sshd drop-in. [V 2026-10-01]
- **Impact:** IN9 asks every host-configuration increment to update the backup inventory, yet the inventory never recorded the GitOps-installed files, so each increment had to decide again — R1.15 and R1.18 left it unchanged, silently. For a restore onto a fresh host the reader cannot tell which host files come back with `deploy.sh` and which hand-made state is lost (the `Match User admin` block, F63's `cmdline.txt`).
- **Proposed fix:** Amend ADR-009 §5.4 (dated amendment, operator decision, roadmap §5): one row per file `deploy.sh` installs with "Backup: no — recreated by deploy from Git", and the known hand-made host state (`/etc/ssh/sshd_config`, `/boot/firmware/cmdline.txt` from F63) with its own decision. In R2b.6 (consistency of the backup docs).
- **Test:** `tests/guards` — every destination of a `scripts/host/ensure-*.sh` script (its `*_DST` default) appears in ADR-009 §5.4.
- **Acceptance:** The guard passes and fails when a new `ensure-*.sh` installs a file the inventory does not name; the hand-made host files are listed with a decision.
- **Prevention:** Rung: static guard in CI — the test above turns IN9's "update the backup inventory" from a question each plan has to remember into a failing check whenever an increment adds an installed host file. Nothing earlier sees it: the plan answered IN9 by reading the ADR, and the ADR had no row to update.

## Monitoring coverage

### F65 – cadvisor cannot stat container root filesystems under the containerd image store

- **Evidence:** cadvisor's log on the Pi during the R1.19 capability trace, before its capabilities changed: `E1001 10:47:10 fsHandler.go:121] failed to collect filesystem stats - rootDiskErr: could not stat "/var/lib/docker/rootfs/overlayfs/<id>" to get inode usage: ... no such file or directory` for two container IDs [V 2026-10-01, operator]. The error is `ENOENT`, not `EACCES`, so it predates and is independent of R1.19. Docker on the Pi uses the containerd image store (F57, `docker info` 2026-09-29). Cause [I]: cadvisor v0.60.5 resolves a container's root filesystem to a path that exists only for the classic graph drivers — check with `docker logs` counting `fsHandler` lines over a day and with a query for `container_fs_usage_bytes` per container. `tests/postdeploy/test_25_cadvisor_metrics.py` checks only the families in `REQUIRED_FAMILIES`, none of them `container_fs_*`.
- **Impact:** Per-container filesystem metrics (`container_fs_*`) are missing or partial; a container filling its writable layer goes unseen. The log fills with errors that hide new ones. No alert or dashboard that the postdeploy tests protect depends on them today.
- **Proposed fix:** Measure first which `container_fs_*` series exist; then check cadvisor's containerd-snapshotter support (a flag or a newer release) or accept the gap in ADR-0011 and filter the error. Decided together with F57's socket question, since both follow from the containerd image store.
- **Test:** `tests/postdeploy/test_25_cadvisor_metrics.py` — `container_fs_usage_bytes` exported with `name=` for `NAMED_SERVICES`, or, if the gap is accepted, a test that pins the accepted state.
- **Acceptance:** Either the filesystem families flow for every named service and cadvisor logs no `fsHandler` error after a restart, or ADR-0011 records the gap and the test pins it.
- **Prevention:** Rung: postdeploy. A family check that lists every family the stack's dashboards query, not only the alerting ones, would have shown the gap at the first deploy on the containerd image store; the R4 service DoD (observability: key metrics with interpretation) makes that list part of each service's documentation.

## Documentation and ADRs

F46, F42 and F43 are documentation defects too; they are listed under privilege, exposure and
deploy because their fix starts in code and ends in the document.

### F5 – `README.md` describes a stack that no longer exists

- **Evidence:** `README.md:20,24` (Prometheus, Loki, Promtail), `README.md:56,71,85-86` (env file paths that differ from ADR-0007's `/etc/raspberry-pi-homelab/monitoring.env`). [V 2026-09-23]
- **Impact:** The entry point of the repository contradicts the implementation and the secrets model.
- **Proposed fix:** Rewrite from `.claude/CLAUDE.md` §3–§6 and `docs/monitoring.md`; link, do not duplicate.
- **Test:** `tests/guards/test_00_no_prometheus_artifacts.py` — extend to `README.md`; a link checker for relative links.
- **Acceptance:** No mention of Prometheus/Loki/Promtail; every relative link resolves.

### F6 – ADR numbering and titles are inconsistent

- **Evidence:** `docs/architecture/adr/ADR-0001-networking-and-firewall.md` (titled ADR-0004), `docs/architecture/adr/ADR-0008-bind-mounts-only.md` (titled ADR-000X), `docs/architecture/adr/ADR-009-backup-verify-restore.md` (three digits). [V 2026-09-16]
- **Impact:** References are ambiguous; `.claude/rules/docs-adr.md` expects `ADR-NNNN`.
- **Proposed fix:** Align titles with filenames; rename ADR-009 to ADR-0009 and update references.
- **Test:** `tests/guards` — ADR filename number equals the title number and has four digits.
- **Acceptance:** The guard test passes for all ADRs.

## R1 increments

The grouping into increments, their order and what is open or done per group moved to
`.claude/roadmap.md` §6 on 2026-09-26. `tools/check_findings.py` keeps it consistent with the
index above.
