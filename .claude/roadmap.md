# Roadmap – raspberry-pi-homelab

The living plan for roadmap stages R1–R6: where the work stands, the rules every increment follows,
the open findings by group, and the increment log. `.claude/CLAUDE.md` is always loaded; this file
is read at the start of any work session. The Claude transition (R0) is complete and archived in
`.claude/ClaudeTransition.md` — historical record only, no longer maintained.

**To work on the roadmap - start a new claude session and enter command:** \
`Antworte auf Deutsch. Lese .claude/roadmap.md und plane das nächste Inkrement mit /increment-plan`

## 1. Status

- **Stage:** R1 — review of the implementation and the findings in `.claude/reports/repo-findings.md`.
- **Done in R1:** group a except F26b (its restore test belongs to R3/F9); F48 and F49; F28, the
  first step of group b; F46 steps (2) and (3) as R1.3 (ADR-0010 Accepted, allowlist guard);
  F21 and F22 as R1.4–R1.6 (one dev dependency source, exact pins incl. `constraints-dev.txt`,
  pinned pip, idempotent `make venv`); F46 step (4) as R1.7 (cadvisor unprivileged, ADR-0011
  supersedes ADR-0010, F46 addressed); F34 as R1.8 (vector stays on `apps` by decision, networks
  of every service pinned by a guard); R1.9 network `docker-api` bootstrapped (external, created
  with `--internal`); F30 as R1.10 (vector reads the Docker API through `socket-proxy`, ADR-0012
  Accepted). R1.11 (cadvisor through `socket-proxy`, F57) failed postdeploy and was reverted: with
  Docker's containerd image store, cadvisor's Docker integration needs the containerd socket,
  which no proxy can filter (increment log, F57). R1.12 per-service config hash for vector (first slice of
  F1/F29, prerequisite for F58); F58 as R1.13 (vector API on loopback); F59 as R1.14 (`make ci`
  hooks also cover new, untracked files); group j — F60 as R1.15 (APT remount hook for the
  read-only `/boot/firmware`, ADR-0013) and R1.17 (permanent postdeploy checks: `dpkg --audit`
  empty, boot files equal the running kernel's); F7's `restart` part as R1.16; group k — F62 as
  R1.18 (persistent journal, proven by an attended reboot); F57's `cap_drop` as R1.19 (cadvisor
  keeps only `DAC_OVERRIDE`, measured by a `cap_capable` trace, ADR-0011 amendment 2026-10-01);
  F57's `no-new-privileges` as R1.20 (cadvisor execs only itself, measured by an exec trace;
  every service now guarded); R1.21 — one feature, three increment commits, one deploy by the
  operator's decision: F57's `read_only` for cadvisor (no `tmpfs`, measured), F66 part B and F67's
  denylist of development and diagnostic packages and IDE servers, F67's `sshd` drop-in (every
  forwarding and root login off, with a `Match all` block); group l done; R1.22 — F57's
  `/dev/kmsg` dropped (measured in use, for the OOM watcher only; operator decision, ADR-0011
  amendment "/dev/kmsg"), no service may map a host device (`DEVICES_ALLOWLIST` empty). See §6 and
  `.claude/increment-log.md`.
- **Next increment:** R1.23 F57 `pid: host` for cadvisor (group b; Due moved to R1.23 by the
  operator, IN16). What cadvisor reads through the host PID namespace with `--docker_only=true`
  (per-container network counters from `/proc/<pid>/net`, ADR-0011 Context) is [I]. It is
  measured first (IN18 skeleton), and the result is checked by `test_25`'s families and
  cadvisor's log. F57's socket part needs a decision first: switch Docker to
  `overlay2` (own ADR, after the R3 backup is proven) or accept the risk in an ADR. Other
  candidates: the rest of group h — F47 (doctor test skips instead of pulling), F23/F25
  (`lint`-marked tests never run), F11, F56 — small, no Pi runtime effect.
- **Stages re-planned on 2026-09-26:** a new R2 (quality and lifecycle, §9) sits between R1 and
  backup (now R3); a new R4 (service standard, §9.7) follows backup; core and apps moved to R5
  and R6.
- **Starting a new session:** read `.claude/CLAUDE.md`, this file, and the findings named in the next
  increment. Then plan with the `increment-plan` skill and present the plan before writing.

## 2. Delivery rules (permanent)

Moved unchanged in substance from the transition plan (§10.1 there); the IDs are cited by skills
and rules.

| ID | Rule |
|---|---|
| IN1 | Exactly one feature is in progress at any time. A new feature starts only after the previous one is deployed and its postdeploy tests are green. |
| IN2 | A feature is split into increments. Each increment is small enough to review in one sitting, changes one concern, and leaves the system deployable. Splits that create an undeployable intermediate state are not allowed. |
| IN3 | Every increment ships with matching tests: static tests (`tests/precommit` or `tests/guards`) for repo-level contracts, and postdeploy tests (`tests/postdeploy`) for runtime behaviour. Tests are written or extended **before or together with** the implementation. |
| IN4 | Local gate before commit: Claude runs `make ci` (or the non-mutating `readonly-gate` skill) and reports the result verbatim. Validate first, commit afterwards. |
| IN5 | Claude proposes a Conventional Commit message and a short change summary. The operator reviews the diff and commits personally. Claude never commits, pushes, or deploys (C4, C5). |
| IN6 | Deployment is manual by the operator: on the Pi `git pull --ff-only`, then `sudo ./deploy.sh` (which runs `make postdeploy`). |
| IN7 | An increment is **done** only when: CI green, deploy succeeded, postdeploy green, its Pi footprint cleaned up and verified (IN18), increment log updated (`.claude/increment-log.md`, §7). |
| IN8 | If deploy or postdeploy fails: no new increment. Either fix forward within the same increment scope or roll back with `git revert` (via branch + PR per IN11/IN12) + pull + deploy. |
| IN9 | Every increment that adds or changes persistent data, host secrets, ports, UFW rules, Docker networks, or host configuration also updates: backup inventory (ADR-009 §4/§5), `.env.example`, reconciliation scripts (`.claude/rules/host-runtime.md`) and their postdeploy checks, network/firewall docs, and Renovate package rules. |
| IN10 | Version pins only (no `latest`); new images go through the pinning rule and Renovate coverage in the same increment. |
| IN11 | One feature = one short-lived branch from current `main` (`feat/…`, `fix/…`, `chore/…`, `docs/…`). Increments are commits on that branch. Branch is deleted after merge. |
| IN12 | Operator pushes the branch and opens a pull request; CI (`ci.yml`, trigger `pull_request`) must be green before merge. Claude proposes PR title and description but does not create the PR (`gh` denied). |
| IN13 | Only `main` is deployed. On the Pi: `git pull --ff-only`, `sudo ./deploy.sh`. Feature branches are never checked out on the Pi. Every merged state must pass IN7. |
| IN14 | **Capture.** Anything observed — in Pi output, code, logs or docs — that contradicts a repository rule, an ADR or a best practice of the platform *named with its source* is reported by Claude in the same answer as a finding candidate: evidence ([V]/[I]), proposed severity and Due. Confirmed by the operator, it is recorded in `.claude/reports/repo-findings.md` at the latest with the next log row; declined, the log row says so and why. A candidate is never fixed inside the running increment, unless it is Critical. |
| IN15 | **Schedule by severity** (Due column of the report index): **Critical** → `next`; no other increment starts first, a running one is finished or reverted (IN8). **High** → the increment after the next planned one (`R<x>.<y>`); several High findings queue in the order found, Critical goes first. **Med** → the stage after the current one (`R<x>`), in that stage's first increment; **Low** → the stage after the current one, any order. At every stage close, each Med/Low finding of that stage gets its group in the next stage (§4). |
| IN16 | **Override.** Only the operator changes a Due that IN15 gives — earlier (taking a finding along with a group of the current stage that touches the same files or ADR) or later — with a dated `**Scheduling:**` line in the entry that says why. An override changes the form, never the deadline: an overdue finding fails `check_findings.py` either way. |
| IN17 | **Prevention.** Every finding (IN14) and every failure — CI, deploy or postdeploy red, a revert, a prediction that proved wrong, a claim or promise of Claude's that did not hold — comes with a proposal how it is caught **earlier or automatically** next time. (1) *Where:* the earliest rung that could have caught it — plan or skill → static test or guard (CI) → checker in `.claude/tools` → hook → postdeploy → stage-close audit → only at a reboot or outage. (2) *Which mechanism*, preferred in this order: test or guard > checker > hook > rule > skill or agent > a lesson in §8; a lesson alone needs the reason why nothing can check it. (3) *Where it goes:* into the fix increment's plan when it belongs there, otherwise its own finding candidate scheduled by IN15; declined, the log row says so. A finding from F64 on carries it as its **Prevention** field (`check_findings.py`); a failure carries it as "Prevention: …" in the notes of its log row. |
| IN18 | **Leave no trace.** Every temporary change on the Pi — a file, an installed package, a configuration or sysctl change, a stopped service — is planned in the increment's "Pi footprint and cleanup" line with its undo and a command that proves the undo, undone **before the deploy**, and recorded in the log row as `Footprint: none` or `Footprint: cleaned — <evidence>` (`check_findings.py` from the row after R1.20 on). Measurement scripts run over stdin (`sudo bash -s`), keep every helper file in one `mktemp -d` directory that a `trap … EXIT` removes, and never install anything themselves; a tool a measurement needs is installed and removed as separate, proven steps. A container restart is no footprint; a leftover is a finding (F66). |

Practice established in R1: tests first as a separate commit with `xfail(strict=True)`, verified
with `--runxfail` to fail for the intended reason; the fix commit removes the markers. The log row
of an increment is recorded on a short `docs/` branch after its deploy: at the top of
`.claude/increment-log.md` and as the single row of §7, and every finding that became `addressed`
moves to `.claude/reports/repo-findings-archive.md` in the same commit.

## 3. Increment template (output of skill `increment-plan`)

```markdown
## R<stage>.<n> – <title>
- Feature: <feature this increment belongs to>
- Goal (one sentence):
- Scope: files expected to change
- Out of scope:
- Tests first: <new/changed test files and what each asserts>
- Implementation steps:
- Local gate: `make ci` result (run by Claude) plus the resulting `git diff` if fixers rewrote files
- Proposed commit message:
- Branch: <feat|fix|chore|docs>/<short-name>
- Proposed PR title/description:
- Pi steps (after merge to main): git pull --ff-only; sudo ./deploy.sh
- Acceptance: <observable postdeploy criteria>
- Rollback: git revert <merge-or-commit> on a fix branch → PR → merge → Pi: git pull --ff-only; sudo ./deploy.sh
- Backup/docs/Renovate impact (IN9):
- Pi footprint and cleanup (IN18): every temporary change on the Pi, its undo and the command that proves it — or "none"
- Prevention (IN17): how recurrence of what this increment fixes is caught earlier, and by which mechanism
```

## 4. Roadmap

| Stage | Feature | Entry criteria | Exit criteria |
|---|---|---|---|
| **R0** | Claude transition (Phases 0–8) | — | **Complete** 2026-09-24; record in `.claude/ClaudeTransition.md` |
| **R1** | Review of the existing implementation, including host/runtime/network reconciliation | R0 done | Every finding re-verified against `main`; decision (ADR) on which host state `deploy.sh` reconciles vs. which stays manual (UFW, network attributes, daemon.json restart policy); each accepted finding fixed or scheduled as its own increment |
| **R2** | Quality and lifecycle: ADRs ↔ rules, dev-environment lifecycle, stack review against the rules, Grafana dashboard lifecycle, documentation (§9) | R1 done | Exit criteria of R2.1, R2d, R2a, R2c and R2b in §9 met |
| **R3** | Backup: finish implementation and tests (ADR-009); then the Pi runtime lifecycle (R3b, §9) | R2 done, or at least the findings affecting backup fixed | `make backup`, `make backup_verify` on the Pi green; fixture tests from ADR-009 §14.2 green in CI; restore dry-run and one non-critical live restore proven (§14.3); open GPG steps (doc step 6 ff.) completed; first increment after that: the Grafana major upgrade (R2c.6); exit criteria of R3b in §9 met |
| **R4** | Service standard: templates, rule, skill and guard for service documentation and a class-based Definition of Done; every existing monitoring service documented and checked against it (§9.7) | R3 done (backup and restore state is proven and can be documented) | Exit criteria in §9.7 met |
| **R5** | Core stack: Traefik with automated Let's Encrypt — the first new service under the R4 standard | R4 done | `stacks/core/compose/` deployed; valid LE certificates with automatic renewal; existing LAN UIs routed via Traefik; postdeploy tests for routing, TLS, redirects, and cert expiry; backup inventory extended; service docs and DoD per R4 |
| **R6.1** | App stack: Stirling PDF | R5 done | Per-app stack under `stacks/apps/stirling-pdf/`, behind Traefik, tests, docs, Renovate rule enabled; service docs and DoD per R4 |
| **R6.2** | App stack: AdGuard Home | R6.1 done | Same as R6.1 plus DNS-specific tests |
| **R6.3** | App stack: Home Assistant | R6.2 done | Same as R6.1 plus backup of HA data verified by restore test |

**Every stage close (IN15)** adds to the exit criteria above: (1) each Med/Low finding found during
the stage is assigned to a group of the next stage, with Due `R<x+1>` — none is left with the
closing stage's Due, which `check_findings.py` reports as overdue once **Stage** in §1 moves on;
(2) from the R2e baseline on (F64), the host best-practice audit is run on the Pi and each
deviation becomes a finding candidate (IN14); (3) from R4 on, `service-doc` in *review* mode runs
for every service changed during the stage (new, upgraded by Renovate, compose or config changed)
and for every service whose runtime prerequisites name a baseline item that changed — its gaps
become finding candidates too.

Prerequisites to clarify at the start of the respective stage:

- **R5 – Let's Encrypt with a LAN-only Pi:** `rpi-hub.fritz.box` is not a publicly registered domain, so no public CA can validate it. HTTP-01 needs public reachability; DNS-01 proves control via a TXT record and only makes sense for automation if the DNS provider offers an API (https://letsencrypt.org/docs/challenge-types/). For a LAN-only Pi, DNS-01 with a public domain is the likely path. Open: which domain (`Todo.txt` mentions an existing domain at WebHostOne), whether that provider is supported by Traefik's ACME DNS providers (not yet verified), and how local name resolution for the public names is done (AdGuard rewrites in R6.2, or FritzBox DNS).
- **R5 – Firewall:** Traefik adds inbound 80/443 (and possibly removes direct LAN exposure of 3000/9428). This depends on the R1 decision on UFW reconciliation (F15, F45).
- **R5 – deploy.sh:** currently deploys only the monitoring stack. Multi-stack deployment (order, per-stack env files, per-stack config hash) is an ADR decision at the start of R5.
- **R6.2 – AdGuard Home:** needs port 53 on the Pi and a decision on how clients use it (FritzBox DNS setting); conflicts with any existing local DNS listener must be checked on the Pi.
- **R6.3 – Home Assistant:** device discovery commonly relies on host networking, which conflicts with the explicit-network rule. Needs an ADR exception or an alternative before implementation.

## 5. Decisions in force

Full text in `.claude/ClaudeTransition.md` §2 (archive).

| ID | Decision |
|---|---|
| E6 | Artefacts and docs in English (`Todo.txt` stays German). |
| E2 | Claude Code in WSL, plan mode, confirmation per write step. |
| Q1 | C1/C2 (write only in `.claude/`) were transition-only and retired in Phase 8; C3–C6 are permanent. |
| Q7, Q8 | Guard: Python stdlib, `shlex` tokenising; unclassified Bash commands pass to deny rules and plan-mode approval. |
| D1 | One feature at a time in small, tested increments; the operator commits, pulls on the Pi and deploys. |
| D2 | Roadmap R0 → R1 → R2 → R3 → R4 → R5 → R6 (§4). On 2026-09-26 the operator inserted R2 (quality and lifecycle) and R4 (service standard); the original R2 backup, R3 core and R4 apps became R3, R5 and R6. |
| — | Service standard (operator, 2026-09-26): per service `docs/services/<stack>/<service>.md` and `<service>_dod.md` from `docs/services/_template.md` and `_template_dod.md`; classification in YAML front matter with five dimensions (lifecycle, state per ADR-009, exposure, privilege, criticality) checked by a guard against compose; one rule `service-docs.md`, one skill `service-doc` (modes onboard/review), no new subagent. |
| — | ADRs are the decision; a rule that deviates is corrected. An ADR changes only on the operator's decision, by a dated amendment or "Superseded by", never by rewriting; renaming to the four-digit form (F6) touches file name and title only (operator, 2026-09-26). |
| Q9 | Short-lived branch per feature, CI on the pull request, only `main` is deployed. |

## 6. R1 plan — findings by group

The report `.claude/reports/repo-findings.md` holds the entries and their status. This table
assigns every finding that is not `addressed` to exactly one group; `.claude/tools/check_findings.py`
enforces that, and that each group here matches the R1 column of the report index. Order: security
first, then the mechanisms other fixes depend on.

| Group | Scope | Open | Done | Why this order / state |
|---|---|---|---|---|
| a | Alertmanager renderer: modes, errors, escaping, determinism | F26b | F26, F35, F36, F8, F39, F48 | Done except F26b's restore fixture test, which needs the R3 backup harness (F9) |
| b | Docker socket and privilege | F57 | F28, F46, F34, F30, F58 | Host-root equivalence. F46 (2)+(3) docs/ADR-0010/allowlist in R1.3; F46 (4) `privileged` dropped in R1.7 (ADR-0011); F34 reason recorded and networks pinned in R1.8; `docker-api` network in R1.9; socket proxy for vector in R1.10 (F30, ADR-0012). R1.11 cadvisor on the proxy reverted — containerd image store needs the containerd socket (F57 socket part blocked, decision open). R1.12 per-service config hash for vector, R1.13 vector API on loopback (F58). R1.19 cadvisor `cap_drop: [ALL]` + `DAC_OVERRIDE` (F57, measured). R1.20 `no-new-privileges` (F57, exec trace; guard for every service). R1.21 `read_only` (F57, `docker diff` minus mount targets; guard for every service, grafana excepted by F41). R1.22 `/dev/kmsg` dropped (OOM watcher only, operator decision; guard: no host devices). Next: R1.23 `pid: host` |
| c | LAN exposure and firewall contract | F45, F31, F42, F15 | — | F45 needs a Pi-side measurement first; decides F15 |
| d | Config hash that works | F1, F2, F29, F13 | — | Makes every later config change actually deploy; candidate: `up --renew-anon-volumes` (F48) |
| f | Compose contract guard test | F41, F7, F33, F27, F32, F38 | — | One test file becomes the home of all hardening checks. F7's `restart` part done as R1.16 (2026-09-29); its healthchecks stay here |
| e | Host reconciliation ADR | F16, F17, F18, F43, F19, F20, F63 | — | Needs an ADR decision before code (R1 exit criterion). F63 (kernel command line for the memory cgroup, hand-edited on the read-only `/boot/firmware`) found 2026-10-01 in the first persistent boot journal; its postdeploy check can come before the ADR |
| g | Supply chain | F3, F24, F44 | F37 | Digest pins together; F37 went with F8; F4 moved to R2d |
| h | Toolchain and dead tests | F23, F25, F47, F11, F56 | F49, F21, F22, F59 | F21 + F22 done as R1.4–R1.6; F59 as R1.14; rest low risk, quick |
| j | Host update path with a read-only firmware partition | — | F60 | Found 2026-09-29 while preparing the F57 capability trace; pulled forward from R3b by the operator the same day, before R1.15, because every APT run fails and security updates are blocked. R1.15 deployed (APT hook, ADR-0013); first unattended-upgrades run with the hook successful (2026-09-30); permanent postdeploy checks as R1.17 (2026-10-01). Group done |
| k | Host evidence that survives a reboot | — | F62 | Found 2026-10-01 after R1.17 (volatile journal, `Storage=volatile` measured); pulled forward by the operator the same day as R1.18, before F57, so that every later reboot leaves evidence. Without an ADR: a reversible configuration installed like `daemon.json` and the APT hook. R1.18 deployed and proven by an attended reboot (2026-10-01). Group done |
| l | Leave no trace on the Pi; no development on it | — | F66, F67 | F67 found 2026-10-01 in the cleanup after F66 (VS Code remote server, compiler chain, kernel headers, pip on the Pi), Due R1.21 by the operator. F66 found 2026-10-01 after R1.20 (measurement files in `/tmp` from R1.19 and R1.20, `bpftrace` still installed); pulled forward by the operator before R1.21 so that R1.21 runs under IN18. Part A (IN18, footprint check in `check_findings.py`, measurement skeleton in the `increment-plan` skill) before R1.21; part B (postdeploy denylist of diagnostic packages) with R1.21. R1.21 deployed (2026-10-01): denylist and `sshd` drop-in, `bpftrace` removed, VS Code Remote-SSH fails. Group done |
| R2d | Dev-environment lifecycle | F4, F50 | — | Stage R2, directly after R2.1 (§9) |
| R2e | Host best-practice baseline | F64 | — | Stage R2 (IN15: Med found in R1 → next stage). Found 2026-10-01 as the lesson of F62/F63: a baseline with sources, audited at every stage close, feeds IN14 |
| R2a | Stack review against rules and guidelines (§9.3) | F65, F69, F70, F71, F72 | — | Stage R2 (IN15: Med/Low found in R1 → next stage). F65 found 2026-10-01 in cadvisor's log during the R1.19 capability trace; decided together with F57's socket question. F69–F71 found 2026-10-02 reading `test_45` after R1.22's extra skip: quiet units skip at once, `udevadm` changes host state, `hello-world:latest` unpinned — one test file, likely one fix increment. F72 (node-exporter `pid: host` without a reason) found 2026-10-02 planning R1.23; its entry in `PID_HOST_ALLOWLIST` keeps the new guard green |
| R2b | Documentation | F5, F6, F12, F68 | — | Stage R2, §9 — the former R1 group i, moved 2026-09-26. F68 (backup inventory lacks the host files deploy installs) found 2026-10-01 in R1.21's IN9 check, for R2b.6 |
| R3 | Backup tests | F9 | — | Stage R3 (was R2 before 2026-09-26) |
| R3b | Pi runtime lifecycle | F51, F52, F53, F54, F55, F61 | — | Stage R3, after backup, §9. F61 (unattended-upgrades outside the documented flow) found 2026-09-29 with F60 |

Closed without a group: F10, F14, F40. Groups named by a letter belong to R1; the others name
their stage.

## 7. Increment log

The full log, newest first, is `.claude/increment-log.md`; read a row there when an
increment's history matters. This section holds only the newest row.

| Increment | Date | Commit | CI | Deploy + postdeploy | Notes |
|---|---|---|---|---|---|
| R1.22 F57 cadvisor without `/dev/kmsg` | 2026-10-02 | `49bcd9c` (tests), `d48d475` (fix and skill); merge `77391d1` (PR #72) | green (local `make ci` after every commit: `213 passed, 1 xfailed`, then `214 passed`; PR CI before merge per IN12, operator) | deploy 13:38: `tests: passed`, postdeploy `96 passed, 4 skipped` (predicted 97/3; skips `test_21` ×2 and `test_45` for `systemd-udevd.service` and `ufw.service`); `test_cadvisor_has_no_host_devices` passed; cadvisor logs the expected `disabling OOM events: open /dev/kmsg: no such file or directory` (operator) | Measured first under IN18: M1, one read-only script, no restart — `HostConfig.Devices` only `/dev/kmsg`, `dmesg_restrict 0`, `CapEff 0x2`, one descriptor on `/dev/kmsg` (self-test: the same predicate found `/dev/null`), log complete since the start (first line after `StartedAt`) with `oom_event` enabled and no warning, 11 `container_oom_events_total` series. The device was in use; dropped by the operator's decision of 2026-10-02 because no rule or dashboard reads the metric (ADR-0011 amendment "/dev/kmsg"). Guard `test_no_service_maps_host_devices` (empty `DEVICES_ALLOWLIST`) ran against the old code with `--runxfail` and failed for cadvisor only. Deviation from the plan: the postdeploy test moved from the tests commit to the fix commit (R1.20/R1.21 practice; on its own it would fail on the Pi). The fix and the skill change landed in one commit `d48d475` under the skill's `docs(claude)` subject instead of the two proposed — Prevention: `increment-plan` skill, each proposed commit names its files. Failures: M1 printed `bash: line 25: EOF: command not found`. The login shell missed the terminator, probably trailing whitespace [I]; the values before the error were complete, and the script ended with `CLEANUP ok` — Prevention: `increment-plan` skill, a script ends with `MEASUREMENT END` and nothing may stand between it and `CLEANUP ok` (in `d48d475`). Claude's prediction 97/3 missed: `test_45` skips a quiet unit on the first empty query, so the skip count varies — Prevention: `increment-plan` skill, a prediction names each variable skip and gives a range; root cause F69 with a guard proposed. Guard refusal: a heredoc to Python for the findings edit. New F69 (Low), F70 (Med), F71 (Low), all Due R2, group R2a, found reading `test_45` for the skip. F57 Due moved to R1.23 by the operator (`pid: host`). Footprint: none — M1 printed `CLEANUP ok`; no tool installed, no restart outside the deploy. |

## 8. Lessons from R1 worth keeping in mind

Each has a home in a rule or a test; listed here so a new session sees them at once.

- **A deploy can fail on runtime coupling no static test sees.** R1.1 broke `apk add` by changing
  the renderer's group; R1.2 left an image `VOLUME` uncovered. Answer: test scripts in the pinned
  image with the compose flags (`tests/guards/test_32_alertmanager_renderer_container.py`).
- **Compose carries anonymous volumes over to a recreated container.** Removing the cause in the
  compose file is not enough on a host with history (F48, R1.2-fix).
- **`docker run -v <missing file>` creates a root-owned directory** at the source path; use
  `--mount type=bind`, which refuses instead.
- **Postdeploy runs as root on the Pi**; anything it writes into the checkout is root-owned (F49).
- **The guard refuses some read-only probes** (`docker image inspect`, `python -c`, `sh <file>`).
  A refusal is a result: get the evidence through a test that `make ci` runs, or ask the operator.
- **Pi-side facts come from the operator.** Measured values (`stat`, `find`, `docker volume ls`) go
  into the findings as evidence with the date; never infer them.
- **A green postdeploy run can hide tests that never ran.** R1.10's first deploy reported "64
  passed" with `7 deselected`: test_26 lacked the `postdeploy` marker, and `make ci` never sees
  `tests/postdeploy`. Read the whole summary line, deselected included. Answer:
  `tests/guards/test_43_postdeploy_markers.py`.
- **A container's host access can depend on host state the repository does not record.** R1.11
  removed cadvisor's containerd socket; on this Pi Docker uses the containerd image store, and
  cadvisor's Docker integration then requires that socket (F57). Before changing what a service
  may reach on the host, measure the host first (`docker info` for driver and version) and read
  the integration's code path for that state — the source said so, but only for that driver.
- **`pre-commit run --all-files` means tracked files only.** Until R1.14, `make ci` never ran the
  hooks on a new file; it met `trailing-whitespace` and `ruff-format` first at commit time
  (`test_43`, `test_54`, F59). Since R1.14 `scripts/dev/run-hooks.sh` adds a run over untracked,
  not-ignored files (`tests/guards/test_44_run_hooks.py`), and the interim practice of running
  `ruff format --check` by hand is no longer needed.
- **A package trigger touches more than the package.** R1.15 predicted that finishing
  `initramfs-tools` would only rewrite `initramfs8`; its trigger regenerated the initramfs of every
  installed kernel, including the one the Pi boots. Before a host change, measure the files it may
  touch (hashes before and after), and prove a changed boot path with a reboot while the operator
  is present — not with the next unattended one.
- **A reboot is a test the deploy never runs.** Every deploy starts all services with
  `compose up -d`, so a missing `restart` policy stays invisible until the host reboots (F7,
  2026-09-29). A postdeploy list of expected services that is written by hand drifts from the
  compose file — `test_10_containers.py` checked 7 of 10 long-running services.
- **Host evidence in the journal survives a reboot only since R1.18.** Until 2026-10-01 the
  journal was volatile by configuration (Raspberry Pi OS's `40-rpi-volatile-storage.conf`, F62);
  `journalctl -b -1` now shows the previous boot. vector still forwards only a few units to
  VictoriaLogs (F61), and postdeploy checks keep testing state, not journal history (F60).
- **Ask for pager-free output.** A command piped through the pager pastes only its first screen:
  the first `systemd-analyze cat-config` paste of 2026-10-01 ended after the main file and hid the
  drop-in that was the point of the measurement, and the commands after it never showed their
  output. Ask for `--no-pager` (or `| cat`) and a `grep` that keeps the `# /path` headers.
- **A measurement proves its own coverage, and its decision rule is checked against a known
  value.** R1.19's first capability trace missed cadvisor's start: the instructions asked for a
  restart "in a second terminal while the trace runs", and the restart ran before it. The second
  trace ran as one script and printed `StartedAt` after the trace began. The rule fixed in advance
  ("add every capability with a granted check") would have granted `SYS_ADMIN`: overlayfs checks
  the lower inode with its mounter's credentials, so a granted check is not the task's own right.
  Cross-checking every granted capability against the process's `CapEff` exposed it. Nothing in
  CI can see a measurement on the Pi (C5); the `increment-plan` skill carries the steps.
- **A probe proves itself through the same predicate the measurement uses.** R1.20 needed three
  runs: the first ran without root and on Claude's WSL path, pasted into a login shell that
  `set -e` then closed; the second filtered `sched:sched_process_exec` on `filename`, which
  `bpftrace` v0.23.2 on this kernel returns empty, and it assumed the container's `.Path` was the
  binary (it is `entrypoint.sh`). Only the advance rule "the known start must appear" kept
  `CHILD_EXEC: 0` from reading as "no execs". The third ran as a file with `sudo`, checked root,
  paths and tools before changing anything, waited for a `BEGIN` marker and caught `/bin/true`
  through the exact probe and predicate of the measurement. CI cannot see this either (C5); the
  `increment-plan` skill carries the steps.
- **A measurement leaves traces unless it removes them itself.** R1.19 and R1.20 left eleven files
  in `/tmp` (scripts, `tee` outputs, `mktemp` files; a tmpfs, so they held RAM until a reboot) and
  `bpftrace` installed (F66). "Run it as a file" from the lesson above was itself a cause. Since
  IN18 a script runs over stdin (`sudo bash -s`), keeps its helpers in one `mktemp -d` directory
  removed by a `trap … EXIT`, and every log row states its footprint (`check_findings.py`).

## 9. Stage plans R2, R3b and R4

Planned with the operator on 2026-09-26. Increment numbers are provisional; each block is planned
in detail with the `increment-plan` skill when it starts. Within R2 the order is
**R2.1 → R2d → R2a → R2c → R2b**: consistent yardsticks first, a reproducible toolchain before the
review relies on it, code changes before the documentation that describes them.

### 9.1 R2.1 — ADRs and Claude rules consistent

Scope: ADR-0001, 0007, 0008, 009 against `.claude/CLAUDE.md` §4, `.claude/rules/*.md`, and the
skills and agents that cite ADRs.

- **Rule → ADR:** every rule statement that rests on an ADR, including each "Sources" entry, is
  checked against the cited text — existence of the file is not enough (the R0 lesson).
- **ADR → rule:** every ADR decision that constrains Claude's work appears in `CLAUDE.md`, a rule
  or a skill, or is recorded as not relevant to Claude.
- **Exceptions:** anything a rule tolerates needs an ADR (known: cadvisor root, `pid: host` and
  socket → ADR-0011; LAN exposure of 3000/9428 → F42).
- Result: a "Source" column in `.claude/reports/rule-coverage.md` (R2a) and a reverse section in it.
  Contradictions become findings; ADR precedence per §5. `check_rules.py` requires a section
  reference for every ADR named under "Sources" (form only).
- Exit: all ADR-based rule statements verified; every Claude-relevant ADR decision mapped; all
  contradictions recorded and resolved; both exceptions covered by an ADR or an open finding.
- No deploy (docs and `.claude/` only).

### 9.2 R2d — Dev-environment lifecycle (F4, F50)

Prerequisite: F21/F22 done in R1 (pinned pip, idempotent `make venv`, one dependency source).

| Inc | Content |
|---|---|
| R2d.1 | Renovate managers `pip_requirements`, `pre-commit`, `github-actions`; pins in `requirements-dev.txt`, `constraints-dev.txt` and `.pre-commit-config.yaml` move in one PR (the parity test enforces it); no automerge (F4) |
| R2d.2 | `docs/operations/dev-environment-updates.md`, analogous to `runtime-updates.md`: WSL checklist (apt, Ubuntu release, Docker Desktop + WSL integration, Python version, Claude Code), the flow `make venv-clean venv` → `make ci` → commit pins, and recovery when Docker is missing (F50) |
| R2d.3 | `make doctor` checks versions: Python minor as in CI (3.12), Docker and Compose plugin present, with a pointer to the doc (F50) |
| R2d.4 | GitHub Actions pinned by digest and kept current by Renovate (may join group g / F3 instead) |

Exit: every tool version in the repo is pinned exactly and has a Renovate path; the WSL flow is
documented; `make doctor` detects the typical drifts; one trial Renovate PR (pip or pre-commit)
went through end to end. No Pi runtime effect. IN9: Renovate rules change.

### 9.3 R2a — Stack review against rules and guidelines

Scope: `stacks/monitoring/**`, `deploy.sh`, `init-permissions.sh`, `scripts/host/`,
`scripts/network/`, `scripts/host-runtime/` (static only, nothing is executed — C5), CI and
Renovate. Yardsticks: MUST/SHOULD of `.claude/rules/*.md`, `CLAUDE.md` §4, the ADRs;
`ChatGPTHint.txt` only where not superseded. Backup scripts are R3 (F9).

- **`.claude/reports/rule-coverage.md`** (permanent, maintained for new stacks): every MUST rule has
  exactly one state — *enforced* (test name), *violated* (finding ID), or *documented exception*
  (ADR). "Unclear" is not a state. `check_findings.py` verifies that every finding ID and test file
  it names exists.

| Inc | Content | Tool |
|---|---|---|
| R2a.1 | Matrix for compose-stacks and secrets, service by service | agent `compose-reviewer`, skill `image-pin-audit` |
| R2a.2 | Security review: secrets, exposure, privilege, supply chain | agent `security-reviewer` |
| R2a.3 | Matrix for testing, shell-scripts, host-runtime, ci-renovate; test coverage per service | agent `test-author` for gaps |
| R2a.4 … | Triage and fixes of the new findings, one increment per finding or group | skill `increment-plan` |

Every subagent claim is verified by Claude against the code before it becomes a finding.
Exit: matrix complete; all new **High** findings `addressed`; new Med/Low findings fixed or
assigned to a later stage (group column, checked). Deploy only for the fix increments.

### 9.4 R2c — Grafana dashboard lifecycle

Measured 2026-09-26: `stacks/monitoring/grafana/grafana_dashboards.md` has wrong paths
(`monitoring/…`), a wrong script name (`normalize-dashboard.py`), a wrong state file name
(`gnet-revisions.json` vs `.gnet-revisions.json`), stale dashboard IDs, a Loki reference and two of
three providers; `scripts/grafana/validate_dashboards.sh` runs in no gate; `.gnet-revisions.json`
holds `21743`, which is not in the manifest; `renovate.json5` has no Grafana rule; postdeploy checks
one of seven dashboards (`test_23`). Pinned: `grafana/grafana:11.6.16`. These become findings in
R2c.1.

| Inc | Content | Deploy |
|---|---|---|
| R2c.1 | Review scripts and workflow; move the doc to `docs/operations/grafana-dashboards.md` and correct it; clean the revision state; wire `validate_dashboards.sh` into pre-commit/CI; guard: manifest ↔ files ↔ revisions ↔ provisioning folders | no |
| R2c.2 | Container test in CI: the pinned Grafana image provisions every manifest dashboard without errors (log clean, `/api/search` lists all, each UID fetchable) — the safety net for major upgrades | no |
| R2c.3 | Rule `grafana-dashboards.md` (paths `stacks/monitoring/grafana/**`, `scripts/grafana/**`) and skill `grafana-dashboard-update` (update, add, major-upgrade checklist). No subagent. | no |
| R2c.4 | Renovate: Grafana majors as a separate PR with `dependencyDashboardApproval`; minor/patch as usual | no |
| R2c.5 | Postdeploy: every manifest dashboard provisioned on the Pi (extend `test_23`) | yes |
| R2c.6 | **Moved to R3** (first increment after backup is proven): dashboard refresh and Grafana major upgrade with the new skill and tests — it migrates Grafana data, so it needs a proven restore | — |

Exit: correct workflow doc under `docs/operations/`; validation and container test in CI; rule,
skill and Renovate rule in place; R2c.5 green on the Pi. `download-gnet.sh` fetches from
grafana.com — if the guard refuses it for Claude, the operator runs the download.

### 9.5 R2b — Documentation (F5, F6, F12)

`docs/**` (13 files, 4394 lines on 2026-09-26) and `README.md` against the implementation and the
guidelines. Last in R2, so they describe the state after R2a/R2c.

| Inc | Scope | Known links |
|---|---|---|
| R2b.1 | `README.md` | F5 |
| R2b.2 | ADRs: numbering, titles, content vs implementation | F6, F43 |
| R2b.3 | `docs/monitoring.md`, `docs/services/` — content only; the move into `docs/services/monitoring/` and the templates come in R4 | F42 |
| R2b.4 | `docs/architecture/networking-and-firewall-model.md` | outcome of R1 groups c/e |
| R2b.5 | `docs/operations/`: DevWorkflow, git-branch-workflow, runtime-updates (path `~/iac/…`, "Last verified", plan vs script — F55), renovate | F44, F55 |
| R2b.6 | Backup docs and ADR-009, consistency only (content follows in R3) | F68 |

Method: `docs-steward` drift report with `file:line`, every claim verified by Claude; the operator
reviews each diff. Gaps between doc and system are named, not smoothed over; a code defect becomes
a finding instead of a doc edit. ADRs per §5 (amend, never rewrite). New guard
`tests/guards/test_60_docs_links.py`: relative links and file references in `docs/**` and
`README.md` resolve. Exit: every file reviewed; drift fixed or recorded; link guard green; F5, F6,
F12 addressed. No deploy (IN7's deploy step does not apply).

### 9.6 R3b — Pi runtime lifecycle (F51–F55), after backup

Review of `scripts/host-runtime/` on 2026-09-26: the structure is sound (plan/apply split, no
automatic reboot, EEPROM separate, clean Git tree required, no `rpi-update`); the weaknesses are in
what the scripts do not enforce. Until R3b, routine APT updates continue as today
(`host-upgrade-plan` → `-apply` → postdeploy); EEPROM updates and major OS upgrades wait until R3's
restore is proven.

| Inc | Content | Findings | Deploy |
|---|---|---|---|
| R3b.1 | Testable scripts: `HOMELAB_ALLOW_NON_PI` test mode, `PATH` stubs for `apt-get`, `dpkg-query`, `rpi-eeprom-update`, `docker`, `sudo`; guards: plan mutates nothing, apply refuses a dirty tree, EEPROM never runs in the routine path | F53 | no |
| R3b.2 | Bind plan and apply: the plan writes `package=version` + timestamp to a host file; apply refuses if it is missing, stale or differs from a fresh simulation; explicit conffile policy; `autoremove` list shown in the plan; the plan shows disk space and failed units | F51, F55 | no |
| R3b.3 | Backup gate: `upgrade-apply` and `eeprom-apply` refuse without a verified backup younger than a set age (evidence from R3); override only with an explicit flag and a logged reason | F52 | no |
| R3b.4 | Docker packages: ADR — `apt-mark hold` plus a separate controlled step (stop, upgrade, start, postdeploy) or accepted restart; postdeploy minimum versions for Docker Engine and the Compose plugin | F54 | yes |
| R3b.5 | Machine-readable audit summary (versions, EEPROM channel, reboot state); incomplete sections reported, with a distinct exit code | F55 | no |
| R3b.6 | First controlled cycle under the new flow: backup → verify → plan → apply → reboot if needed → postdeploy, with measured values in the log | — | yes |
| R3b.7 | EEPROM as needed; rebuild path for a major OS upgrade (bootstrap) — scope decided at the start of R3b, possibly its own stage | — | open |

Exit: scripts covered by stub tests; apply executes only the reviewed plan and refuses without a
fresh verified backup; Docker packages settled by ADR; one full cycle logged with postdeploy green;
version state recorded machine-readably. IN9: R3b.2/R3b.3 add host state files — update the backup
inventory (ADR-009 §4/§5) and `.claude/rules/host-runtime.md`.

### 9.7 R4 — Service standard (documentation and Definition of Done)

Goal: introducing and reviewing a service follows one checked standard. Existing services are
documented first; Traefik (R5) is the first new service built under it.

**Layout.** Templates `docs/services/_template.md` and `docs/services/_template_dod.md`; per stack
`docs/services/<stack>/README.md` (stack overview, data flow) and `_profile.md` (stack-specific DoD
items — for monitoring: the vmagent → victoriametrics → vmalert → alertmanager chain, retention,
rule-change process); per service `docs/services/<stack>/<service>.md` and `<service>_dod.md`.
`docs/services/vector.md` moves to `docs/services/monitoring/vector.md`; `docs/monitoring.md`
becomes the monitoring `README.md`.

**Service doc** (understanding and fault analysis): summary with classification and "Last
verified: date + commit"; facts checked against compose (image pin, user, capabilities, networks,
port bindings, mounts with mode and owner, variable names only, config files, limits,
`depends_on`, healthcheck); data flow; state and backup class per ADR-009; configuration and
whether the config hash covers it (F1/F29); observability (health signal, at least three key
metrics with interpretation, a LogsQL example, dashboards, alerts); operations (start/stop,
upgrade, rollback); troubleshooting table (symptom → read-only check → cause → fix, known failure
modes from the log and findings); security (surface, exceptions with ADR); tests; references.

**DoD** — reviewed against the operator's first draft (sections S1–S9 kept, S10 lifecycle end
added):
- YAML front matter declares exactly one value per dimension: `lifecycle` (long-running |
  one-shot), `state` (authoritative | regenerable | stateless — as in ADR-009), `exposure` (none |
  host-local | lan-direct | ingress), `privilege` (unprivileged | runtime-socket | privileged — above
  unprivileged requires an ADR), `criticality` (critical | non-critical, with written criteria).
- One decision table "class → mandatory sections", kept once in the template.
- Every mandatory item carries **evidence** of one kind: a test (preferred), a dated measurement,
  or a doc section. No evidence means open.
- Items already enforced repo-wide point to `.claude/reports/rule-coverage.md` (R2a) instead of
  restating them; the DoD holds only what is service-specific.
- Added from R1 experience: config hash covers the config; Renovate rule; backup-inventory entry
  (IN9); firewall rule if exposed; resource limits; dependencies with `depends_on` conditions;
  secret rotation, including "complete only after backup retention" (F26b); decommissioning
  (data, backups, volumes — F48).
- Items without a mechanism (image vulnerability scan, rate limiting, TLS lifecycle) are optional
  with a reason, or mandatory only once the mechanism or stage exists; an image scanner is its own
  topic, not introduced through the DoD.
- Acceptance per IN7 (CI, deploy, postdeploy, log row), not "one successful deployment".
- **Runtime prerequisites** (added 2026-10-01 with IN14–IN16): the host settings the service
  relies on but cannot show in its own compose file — for example compose memory limits need the
  memory cgroup (F63), logs in VictoriaLogs need the journal or the Docker source vector reads.
  Each refers to an item of the host baseline (R2e, F64) by its ID instead of restating it, with
  the same evidence rule.

**Claude artefacts.** Rule `service-docs.md` (paths `docs/services/**`, `stacks/**/compose/**`):
templates are binding; a service change updates its docs in the same increment; evidence, not
claims. Skill `service-doc` with modes *onboard* (new service: docs from templates, classification,
derived DoD, increment plan) and *review* (existing service against compose, tests and DoD → gap
list → findings, each a finding candidate with severity and Due per IN14/IN15); it uses the existing agents `compose-reviewer`, `security-reviewer`,
`test-author`, `docs-steward`. No new subagent. `new-stack-proposal` requires both documents.

| Inc | Content | Deploy |
|---|---|---|
| R4.1 | Templates, monitoring `README.md` and `_profile.md`, moves of `vector.md` and `monitoring.md` | no |
| R4.2 | Guard `tests/guards/test_70_service_docs.py` (strict xfail per missing service): docs exist for every compose service; front matter consistent with compose (stateful ⇔ bind mount under `/srv/data`, exposure ⇔ port bindings, privilege ⇔ `privileged` or runtime socket); every mandatory DoD item has evidence. Rule `service-docs.md` | no |
| R4.3 | Skill `service-doc`; `new-stack-proposal` updated | no |
| R4.4 … R4.8 | The ten monitoring services (nine long-running plus the one-shot renderer) in packages of two or three; each package lifts its xfail markers and yields a DoD gap list | no |
| R4.9 … | Fixes for the gaps, scheduled by IN15 like any finding: Critical next, High at the increment after next, Med/Low in the next stage; an earlier fix is an operator override (IN16) | as needed |

Exit: guard green for every compose service; no open gap that is mandatory and High; IN7 met for
the fix increments.
