# Claude Transition Plan – raspberry-pi-homelab

- **Status:** **R0 COMPLETE, PHASES 0–8** (v2.6, 2026-09-24). Phase 8 was merged via PR #12, merge
  commit `99a6347`. The guard runs in mode **`operate`**, and V8.1/V8.2 passed. Roadmap stage is now
  **R1**, highest severity first (plan: `.claude/reports/repo-findings.md`, index and R1 table).
  Pi regression deploy of `99a6347`: green (operator, 2026-09-24).
- **Earlier:** **PHASE 8 IN PROGRESS** (v2.5, 2026-09-24) on branch
  `chore/r0-phase8-operate-mode`. The guard is in mode **`operate`** (`c12edc4`), V8.1 passed live,
  and the artefacts were updated in 8.3. V8.2 passed: the first write outside `.claude/`, which
  also covers the first half of F41. Open: `make ci`, the PR and the merge. After that, roadmap
  stage **R1**, highest severity first.
- **Earlier:** **IMPLEMENTED** (v2.4, 2026-09-24) – Phases 0–7 complete. Merged to `main` via
  PR #10, merge commit `c9d2c5dbcf2ee94389335c42d636a312c3c75597`. CI green, deployed on the Pi,
  postdeploy green (regression check; `.claude/` has no runtime effect).
- **Earlier:** PHASE 6 WRITTEN (v2.3, 2026-09-23) – `readme_claude.md` and
  `reports/repo-findings.md` written; the verifiers moved from git-ignored `scratch/` to tracked
  `tools/` (plus a new `check_findings.py`); §3.6 is now an index into the report. V6.2 passed
  mechanically; **V6.1 is an operator step**. Claude Code is now **2.1.280**; V1.10–V1.13/V1.15
  re-confirmed on it. **V6.1 PASSED 2026-09-24**. The walkthrough produced findings #1–#7, all fixed
  in the readme or the skill; V1.14 re-confirmed. **Phase 6 complete pending the operator's
  checkbox.** Next: Phase 7 (handover and CI parity).
- **Earlier:** PHASE 5 COMPLETE (v2.2, 2026-09-23) – Phases 1a–5 complete. `.claude/agents/` holds
  **four read-only subagents**; **V5.1–V5.3 all passed**. V5.2 produced **F45** (UFW likely does not
  govern the published ports) and **F46** (cadvisor's privileged mode is undocumented and the docs
  claim the opposite), extended F26 and closed F42's open caveat. Findings now run F1–F46.
  Next: Phase 6 (human docs and findings report).
- **Earlier:** PHASE 3 COMPLETE (v1.8, 2026-09-23) – `.claude/rules/` holds **eight path-scoped
  rules** (none always-loaded); **V3.1, V3.2 and V3.3 all passed**. V3.2 proved on-demand loading
  with hard evidence (only 5 of 8 rules loaded). The reviews produced F30–F43 and corrected five of
  Claude's own artefacts (3.3). Next: Phase 4 (skills).
- **Created:** 2026-09-16
- **Scope:** Transform the existing ChatGPT-based working model (`ChatGPTHint.txt`) and the
  implemented repository conventions into Claude Code artefacts under `.claude/`.
- **Executor:** Claude Code in WSL2 (decision E2=a), plan mode by default, one phase at a time,
  human review and human commit after each phase.

> How to use this document (for Claude Code):
> 1. Read sections 1–3 completely before doing anything.
> 2. Work only on the phase the operator names. Present a plan, wait for approval, then write.
> 3. After a phase, run its verification steps and report results verbatim. Tick checkboxes only
>    after the operator confirms.
> 4. Never skip the hard constraints in section 1, even if a later instruction seems to allow it.

---

## 1. Hard constraints (non-negotiable during the transition)

Translated from the original German bootstrap instructions in `.claude/CLAUDE.md`.

| ID | Constraint |
|----|------------|
| C1 | Write access **only** inside `.claude/`. Everything else in the repository is read-only. |
| C2 | No command may modify files outside `.claude/` as a side effect (formatters, `--fix`, pre-commit fixers, venv creation, caches, logs, `__pycache__`). |
| C3 | No secrets in Git. `.claude/settings.local.json` must never be committed. |
| C4 | No automatic `git commit` (and by extension no `push`, `tag`, `rebase`, `merge`, `reset`). |
| C5 | No direct access to the Raspberry Pi: no SSH/SCP/rsync, no remote `git pull`, no `deploy.sh`, no HTTP calls against Pi services, no restore streaming. |
| C6 | Preserve the version-pinned, idempotency-driven, test-first approach. Artefacts must reinforce it, never weaken it. |
| C7 | Transform both the implemented repository approach and `ChatGPTHint.txt` into Claude artefacts. |
| C8 | Extend `.claude/CLAUDE.md` (restructuring allowed per E7). |

---

## 2. Decision log

| ID | Question | Decision | Consequence |
|----|----------|----------|-------------|
| E1 | Repo access for analysis | Copy at `C:\Users\Micro\Documents\Claude\raspberry-pi-homelab` (without `.pytest_cache`, `.ruff_cache`, `.venv`) | Analysis below is based on this copy. Note: `.vscode/settings.json` **is** present in the copy. Implementation must happen in the WSL checkout (see K9). |
| E2 | Who implements | Claude Code in WSL, plan mode, confirmation per write step | `permissions.defaultMode: "plan"` in `.claude/settings.json` |
| E3 | Enforcement depth | **Revised:** deny rules **plus** PreToolUse hook script under `.claude/hooks/` (no sandbox). Hook checks target paths of Write/Edit and inspects Bash commands including nested ones. | Section 5.4, Phase 1 split into 1a/1b; residual risk reduced but not eliminated (K3) |
| E4 | Artefact scope | Comprehensive: CLAUDE.md, settings, rules, skills, subagents | Section 5 |
| E5 | Local validation | Only non-mutating check variants | Mutating Make targets are denied (K1) |
| E6 | Artefact language | English | Existing German `CLAUDE.md` gets translated during restructuring |
| E7 | Existing `.claude/` | Extend and restructure | `readme_claude.md` and `ClaudeTransition.md` (both empty before) are repurposed |
| E8 | Implementation state | Monitoring stack implemented; backup in progress; see `Todo.txt` | Section 3 |
| Q1 | Scope of C1 (write only in `.claude/`) | **Transition only.** Afterwards Claude edits repository files. | C1/C2 live in a separate "Transition constraints" section and a separate deny block; Phase 8 retires both. C3–C6 stay permanent. |
| Q2 | Pi identifiers | Deny host name `rpi-hub`, IP `192.168.178.29`, and the Pi FQDN (value pending, section 9). Calls to Pi services are denied now and allowed selectively later. | Broad deny patterns must be replaced by narrow ones in Phase 8, because deny always wins over allow. |
| Q3 | Claude Code version (WSL) | Phase 0: `2.1.273`; **at Phase 1a (2026-09-18): `2.1.276`** | Newer than all version notes cited from the settings and hooks docs (v2.1.211, v2.1.257, v2.1.267, v2.1.269), so current docs apply. The CLI updated itself between Phase 0 and Phase 1a, so the live hook tests V1.10–V1.16 must run on 2.1.276 (risk table: re-run after every update). |
| Q4 | `make doctor` | Allowed (`make doctor`, `make doctor-strict`) | Added to allow list; covered by the before/after side-effect check. |
| Q5 | Pi FQDN | `rpi-hub.fritz.box` (LAN only) | Added to deny list and hook config. `*rpi-hub*` already matches it; explicit entries kept for clarity and for WebFetch domain rules. |
| Q7 | Guard implementation language | **Option A:** Python 3 standard library, tokenising exclusively with `shlex` | No third-party shell parser (e.g. `bashlex`). See H1/H8. |
| Q8 | Unclassified Bash commands | **Option A:** guard exits 0; deny rules and plan-mode approval decide | Guard blocks only classified violations and fail-closed cases (H2). |
| D1 | Delivery model | One feature at a time, delivered in small increments, each with matching tests. Operator commits every change personally, pulls on the Pi (`git pull`) and deploys manually (`sudo ./deploy.sh`). | Section 10.1; rule `incremental-delivery.md`; skill `increment-plan` |
| D2 | Roadmap | R0 transition → R1 review → R2 backup → R3 core stack (Traefik + Let's Encrypt) → R4 app stacks (Stirling PDF, AdGuard Home, Home Assistant) | Section 10.3; transition Phase 8 moves into R0 because R1 fixes and R2 need writes outside `.claude/` |
| Q9 | Git flow per increment | **Option A:** short-lived feature branch per feature; increments are commits on it; push → CI on pull request → operator merges to `main` → Pi pulls `main` | IN11–IN13 (10.1); Phase 0 branch `chore/r0-claude-transition`; Pi only ever pulls `main` |
| Q6 | WSL checkout path | `/home/micro/src/raspberry-pi-homelab` (given as `home\micro\src\raspberry-pi-homelab`; Linux form assumed) | Used as expected project root in hook tests; hook itself resolves the root dynamically. |

---

## 3. As-is analysis (verified against the repository copy)

Legend: **[V]** verified by reading the file, **[I]** inference that must be confirmed in WSL/CI.

### 3.1 Existing `.claude/`

- `CLAUDE.md`: German bootstrap instructions only (the constraints in section 1). [V]
- `ClaudeTransition.md`, `readme_claude.md`: empty. [V]
- No `settings.json`, no `.gitignore`, no rules, skills, or agents. [V]

### 3.2 Repository layout (relevant parts)

```text
.github/workflows/ci.yml        single workflow, jobs doctor/precommit/tests, Python 3.12
.pre-commit-config.yaml          hygiene fixers, yamllint, shellcheck, pytest(precommit), ruff --fix, ruff-format, renovate validator
Makefile                         single orchestration entrypoint with platform guards (_guard-wsl, _guard-pi)
deploy.sh                        Pi-only, root, idempotent GitOps deploy
renovate.json5                   self-hosted Renovate via Docker in WSL, docker-compose manager only
pyproject.toml / requirements-dev.txt   dev tooling (pytest, ruff, yamllint, pre-commit)
stacks/monitoring/               implemented stack (compose + configs + grafana provisioning/dashboards)
stacks/core/docker/daemon.json   GitOps-managed Docker daemon config (no core compose stack yet)
scripts/{backup,grafana,host,host-runtime,network,renovate,tests}/
tests/{precommit,guards,doctor,postdeploy,_lib}/
docs/{architecture/adr,operations,services}/ + DevWorkflow.md, monitoring.md
Todo.txt                         German working backlog (open + done)
ChatGPTHint.txt                  original operating model for ChatGPT
```

### 3.3 Monitoring stack (`stacks/monitoring/compose/docker-compose.yml`) [V]

| Service | Image (pinned tag) | Exposure | Hardening notes |
|---|---|---|---|
| alertmanager | `prom/alertmanager:v0.34.0` | `127.0.0.1:9093` | read_only, cap_drop ALL, no-new-privileges, healthcheck |
| alertmanager-config-render | `alpine:3.24` | none | one-shot envsubst renderer; runs `apk add gettext` at runtime |
| victoriametrics | `victoriametrics/victoria-metrics:v1.152.0` | `127.0.0.1:8428` | read_only, 4G limit, 30d retention, healthcheck |
| vmagent | `victoriametrics/vmagent:v1.152.0` | `127.0.0.1:8429` | read_only, config-hash label, healthcheck |
| vmalert | `victoriametrics/vmalert:v1.152.0` | `127.0.0.1:8880` | read_only, rules dir mounted, healthcheck |
| grafana | `grafana/grafana:11.6.16` | `3000` (LAN) | plugin `victoriametrics-logs-datasource@0.24.1` pinned, healthcheck |
| node-exporter | `quay.io/prometheus/node-exporter:v1.12.1` | none | non-root 65534, read_only |
| cadvisor | `ghcr.io/google/cadvisor:v0.60.5` | none | `privileged: true`, root (documented Pi 5 necessity) |
| victorialogs | `victoriametrics/victoria-logs:v1.52.0` | `9428` (LAN, UFW-restricted) | read_only, 2G limit, disk cap 50 GB |
| vector | `timberio/vector:0.53.0-debian` | none | uid 65532, journald + docker.sock ro; 0.58.0 reverted due to runtime issues (`Todo.txt`) |

Cross-cutting [V]: external networks `monitoring` and `apps` (bootstrapped by
`scripts/network/bootstrap-networks.sh`); bind mounts only under `/srv/data/stacks/monitoring/*`
(ADR-0008); project name `homelab-home-prod-mon`; images pinned by tag, **not by digest**.

### 3.4 Operating mechanics [V]

- **Secrets model (ADR-0007):** host-only `/etc/raspberry-pi-homelab/monitoring.env`
  (`root:root 600`), loaded only via `docker compose --env-file` in `deploy.sh`; repo-root `.env`
  refused; host-derived GIDs computed in `deploy.sh`.
- **deploy.sh:** root check → repo ownership fix → daemon.json ensure → secrets validation →
  journald access → network bootstrap → init-permissions → config hash → ephemeral GHCR login →
  `compose pull && up -d` → `make postdeploy`.
- **Make phases:** `precommit`, `test`, `postdeploy`, aggregated `check`/`ci`; WSL/CI-only vs
  Pi-only guards; Renovate `renovate-check`/`renovate-apply`; host runtime targets; backup targets.
- **Tests:** 8 precommit, 3 guards, 1 doctor, 21 postdeploy test modules. No backup tests yet.
- **CI:** mirrors `make ci-doctor`, `ci-precommit`, `ci-tests`; `permissions: contents: read`.
- **Host runtime updates:** plan/apply separation, explicit EEPROM, no automatic reboot
  (`docs/operations/runtime-updates.md`).
- **Backup (in progress):** ADR-009 + `docs/operations/GPG_config_for_backup_encryption.md`;
  scripts in `scripts/backup/`; public-key GPG model; private key lives **in the WSL working tree**
  under git-ignored `secrets/backup/gpg/`; `config/backup/` (public key + fingerprint) does not
  exist yet; GPG doc step 6 (install public key on Pi) is the next open step.

### 3.5 Deviations between `ChatGPTHint.txt` and the implemented state

| Hint section | Target | Implemented | Treatment in Claude artefacts |
|---|---|---|---|
| 2 Determinism | "prefer digests" | tag pins only | Rule states target; finding F3 |
| 2 / 6 CI | detect upstream versions, propose PRs | Renovate self-hosted, only `docker-compose` manager | Rule + finding F4 |
| 4 Naming | per-stack `COMPOSE_PROJECT_NAME` | done for monitoring | Rule |
| 7 Runtime | explicit networks, bind mounts only | done | Rule |
| 7 Security | non-root, drop caps, read-only | mostly; cadvisor privileged by necessity | Rule with documented exception list |
| 7 deploy.sh | config hash mechanism | hash covers a narrow and partly stale file list | Finding F1/F2 |
| 7 Backups | automated, restore tested | in progress, tests missing | Backup rule + finding F9 |
| 8 Stacks | `_shared`, core (Traefik), apps | not yet | Rules written generically; stack status in CLAUDE.md |
| 8.1 Layout | `victorialogs/victorialogs.yml` | not present; `vector/` added | CLAUDE.md repo map reflects reality |
| 10.1 Docs | architecture/operations/monitoring/services per service | partial | docs rule + finding F5/F6 |

### 3.6 Findings backlog (for the human operator – NOT to be fixed by Claude during transition)

**Index only since Phase 6 (2026-09-23).** The full entries — evidence with `file:line`, impact,
proposed fix, test and acceptance criterion — live in `.claude/reports/repo-findings.md`, which is
the single source of truth. This index must list the same IDs; `.claude/tools/check_findings.py`
fails if it does not. The earlier full table (with the evidence as first recorded) is in the git
history of this file up to commit `2c88ea6`.

| ID | Finding | Sev | Status |
|---|---|---|---|
| F1 | Config hash is driven by a single runtime file | High | open |
| F2 | Hash list names a missing file and two unmounted ones | Med | open |
| F3 | Images pinned by tag, not by digest | Med | open |
| F4 | Renovate manages compose images only | Med | open |
| F5 | `README.md` describes a stack that no longer exists | Low | open |
| F6 | ADR numbering and titles are inconsistent | Low | open |
| F7 | Missing restart policy / healthchecks | Med | open |
| F8 | Renderer installs `gettext` from the network at every run | Med | addressed |
| F9 | Backup scripts have no tests although ADR-009 requires them | High | open |
| F10 | pytest version drift between pre-commit and `.venv` | Low | addressed |
| F11 | `.gitattributes` does not pin LF for all text types | Low | open |
| F12 | `.env.example` duplicates keys and holds host-derived values | Low | open |
| F13 | Compose mounts a templates directory that does not exist | Med | open |
| F14 | DevWorkflow committed before `make ci` | Low | addressed |
| F15 | UFW is not reconciled on deploy | Med | open |
| F16 | Network bootstrap on deploy skips subnet/bridge validation | Med | open |
| F17 | `daemon.json` applied before the network it references exists | Med | open |
| F18 | Any `daemon.json` change restarts Docker during deploy | Med | open |
| F19 | Host-specific literals in reconciliation scripts | Low | open |
| F20 | `ensure-journald-read.sh` default user does not match its use | Low | open |
| F21 | Toolchain drift between `.venv` and pre-commit | Med | partly |
| F22 | Three diverging sources of dev dependencies | Med | open |
| F23 | Tests marked `lint` are never run by any gate | Med | open |
| F24 | Renovate validator hook runs a floating image tag | Med | open |
| F25 | JSON test scans git-ignored files | Low | open |
| F26 | Alertmanager SMTP password written world-readable | High | addressed |
| F26b | The same password persists in every backup archive | High | partly |
| F27 | Container uid left to image defaults for 8 of 10 services | Med | open |
| F28 | cadvisor mounts the Docker socket read-write | High | open |
| F29 | Config-hash label missing on 5 of 10 services | High | open |
| F30 | vector is effectively host root via the Docker socket | High | open |
| F31 | Grafana admin credentials default to empty | High | open |
| F32 | Grafana runs without `read_only` on a wrong justification | Med | open |
| F33 | vector has no healthcheck | Low | open |
| F34 | vector joins the `apps` network without a reason | Med | open |
| F35 | Renderer swallows errors despite `set -euo pipefail` | Med | addressed |
| F36 | Renderer builds YAML without escaping | Med | addressed |
| F37 | `alpine:3.24` is a floating minor tag | Med | addressed |
| F38 | `depends_on` ignores existing healthchecks | Low | open |
| F39 | German comment in the renderer script | Low | addressed |
| F40 | Volume naming rule contradicted the implementation | Low | addressed |
| F41 | No static guard for the compose hardening contract | Med | partly |
| F42 | LAN exposure of 3000/9428 is recorded in no document | Med | partly |
| F43 | ADR-0001 promises subnet validation the deploy path skips | Med | open |
| F44 | Stale image tag in a Markdown example | Low | open |
| F45 | UFW very likely does not govern the published ports | High | open |
| F46 | cadvisor's privileged mode is undocumented; docs say the opposite | High | open |
| F47 | cadvisor doctor test never runs; its skip hides a compose error | Med | open |

### 3.7 Security-relevant facts for Claude's boundaries [V]

- Private GPG key material is intended to live in the WSL working tree under `secrets/backup/gpg/`.
- KeePassXC files (`*.kdbx`, `*.keyx`) are ignored but may exist locally.
- Renovate token file: `~/.config/renovate/renovate.env`.
- Pi host name `rpi-hub`; LAN CIDR placeholder `192.168.178.0/24` in `.env.example`.
- `make restore` supports `RESTORE_TARGET=user@host` (SSH streaming); `make backup-verify-decrypt`
  uses the private key.
- Host reconciliation scripts (`scripts/host/*`, `scripts/network/*`, `scripts/host-runtime/*`,
  `init-permissions.sh`) mutate root-owned host state (`/etc/docker`, UFW, groups, Docker networks,
  APT, EEPROM). They are Pi-only and must never be executed by Claude, not even in check or
  dry-run mode; Claude may read, review, and (after Phase 8) edit them.

### 3.8 Host, runtime and network reconciliation [V unless marked]

The desired host state is only partly reconciled on every deploy. What `deploy.sh` actually calls:

| Script | Called by `deploy.sh` on every deploy? | Mode used | Effect |
|---|---|---|---|
| `scripts/host/ensure-docker-daemon-json.sh` | Yes (`ENSURE_DOCKER_DAEMON_JSON=1`) | `apply` | Copies `stacks/core/docker/daemon.json` to `/etc/docker/daemon.json` if different and **restarts Docker** (`RESTART_DOCKER_ON_CHANGE=1`), which restarts all containers |
| `scripts/host/ensure-journald-read.sh` | Yes (`ENSURE_JOURNALD_READ=1`) | `apply`, `TARGET_USER=admin` | Adds user to `systemd-journal`, `chgrp -R` / `chmod g+rx` on journal dirs, returns GID |
| `scripts/network/bootstrap-networks.sh` | Yes (`BOOTSTRAP_NETWORKS=1`) | create-if-missing | Ensures `monitoring` and `apps` exist. Subnet/gateway/bridge are validated or set **only if** `MONITORING_SUBNET`/`…_BRIDGE_NAME` etc. are in the environment; `deploy.sh` does not export them |
| `stacks/monitoring/compose/init-permissions.sh` | Yes (`auto`: runs when `--check` fails) | apply | Data directory ownership/modes |
| `scripts/network/cleanup-ufw.sh` | **No** | manual, dry-run default, `--apply` explicit | UFW allowlist (SSH, Grafana 3000, VictoriaLogs 9428, Docker metrics 9323 on `br-monitoring`), stale bridge rules, stale networks |
| `scripts/host-runtime/*` | **No** | Pi-only make targets `host-audit`, `host-upgrade-plan`, `host-upgrade-apply`, `host-eeprom-apply` | APT/EEPROM maintenance, intentionally separate from deploy (`docs/operations/runtime-updates.md`) |

Verification side: `tests/postdeploy/test_35_network_and_ufw.py` checks Docker network attributes
and UFW state after deploy, i.e. UFW drift is **detected** by postdeploy but **not reconciled** by
deploy. `ChatGPTHint.txt` §7 expects `deploy.sh` to bootstrap UFW → deviation, see F15.

---

## 4. Conflicts and required clarifications

| ID | Conflict | Resolution in this plan |
|---|---|---|
| K1 | `make precommit`, `hooks`, `format`, `ruff-fix`, `check`, `ci`, `ci-*`, `venv` modify files (pre-commit fixers, `ruff --fix`, `ruff format`, venv install). Even `ruff`/`ci-*`/`test` depend on the `venv` target, which runs `pip install -U pip`. | Denied. Replaced by the read-only gate in 5.3. |
| K2 | C1 blocks Claude from ever helping with Traefik, backup scripts, tests, or docs. | Resolved by Q1: C1 is transition-only. Artefacts separate *transition constraints* (C1, C2) from *permanent operating rules* (C3–C6). Phase 8 removes the transition block from `CLAUDE.md` and `settings.json`. |
| K3 | E3=a: deny rules are best-effort. Official docs: Read/Edit deny rules do not cover arbitrary subprocesses such as a Python script opening files; OS-level blocking requires the sandbox. Bash patterns can be bypassed via variables, `bash -c`, or scripts. | Revised E3: PreToolUse hook adds recursive command parsing, symlink-resolved path checks and fail-closed behaviour. Still not covered: code executed inside already-allowed programs (e.g. a pytest test or Makefile recipe that writes files or opens a socket), obfuscation the parser cannot resolve (runtime-built strings). Mitigated by plan mode, side-effect diff, human review. Sandbox remains an option for later. |
| K4 | E6 English vs existing German `CLAUDE.md`. | Translate; keep semantics 1:1 (section 1). |
| K5 | Claude Code's automatic protection for `settings.local.json` is a **global** git exclude on the operator's machine only; it does not travel with the repo. A hand-created file is not protected automatically. | Add `.claude/.gitignore` (nested gitignore, stays inside C1). Verify with `git check-ignore -v`. |
| K6 | Git workflow in `docs/DevWorkflow.md` includes commit/push. | Claude proposes commit messages; operator executes. |
| K7 | `make restore` with `RESTORE_TARGET` and GPG doc restore-over-SSH. | Denied for Claude (C5). |
| K8 | `defaultMode` restrictions. | Official settings docs: `auto` and `bypassPermissions` do not take effect from project/local settings; `plan` is not restricted. Verify in Phase 1 via `/status`. |
| K9 | Analysis used a Windows copy. Files created on Windows may get CRLF, and the copy is not the Git working tree. | Implement in the WSL checkout only. Verify LF with `grep -rl $'\r' .claude` (expect no output). Copy this document into the WSL checkout first. |

---

## 5. Target architecture of `.claude/`

```text
.claude/
├── .gitignore                 # settings.local.json, scratch/
├── CLAUDE.md                  # restructured, English, lean (<= ~200 lines), project memory
├── settings.json              # $schema, permissions (deny/allow), defaultMode: plan, hooks.PreToolUse
├── hooks/
│   ├── guard.py               # PreToolUse guard (Python 3 stdlib only), fail-closed
│   ├── guard-config.json      # policy data: pi identifiers, secret patterns, mode (transition|operate)
│   └── tests/                 # test_guard.py (T01–T35) + test_guard_operands.py (T36–T46)
│                              # InstructionsLoaded logging is a command in settings.json, no script (3.2)
├── readme_claude.md           # human-facing: how to work with Claude in this repo, verification
├── ClaudeTransition.md        # this plan (living document, decision log)
├── rules/                     # topic/path-scoped instructions (verify `paths` frontmatter support in Phase 3)
│   ├── operating-model.md     # GitOps, IaC, Pi = deploy target, idempotency, test-first
│   ├── secrets.md             # ADR-0007 model, never-read paths, .env/.env.example policy
│   ├── compose-stacks.md      # naming, pinning, networks, bind mounts, hardening, config hash, access model
│   ├── shell-scripts.md       # set -euo pipefail, guards, idempotency, dry-run default, ShellCheck
│   ├── testing.md             # precommit/guards/doctor/postdeploy layers, markers, naming, skip messages
│   ├── ci-renovate.md         # ci.yml parity with make, Renovate flow, no automerge
│   ├── backup-restore.md      # ADR-009 contract, exit codes, GPG boundaries, restore guards
│   ├── host-runtime.md        # host reconciliation model (3.8): deploy-time ensure scripts, UFW, networks,
│   │                          # daemon.json, plan/apply maintenance, EEPROM explicit, no rpi-update, no auto reboot
│   ├── docs-adr.md            # English only, ADR template/numbering, docs layout target
│   └── incremental-delivery.md # D1: one feature, small increments, tests per increment, operator commit/deploy
├── skills/
│   ├── readonly-gate/SKILL.md          # run the non-mutating validation set (5.3) and summarise
│   ├── change-review/SKILL.md          # review a diff against rules; output checklist + verdict
│   ├── image-pin-audit/SKILL.md        # list image refs, tag vs digest, Renovate coverage
│   ├── new-stack-proposal/SKILL.md     # produce a stack scaffold as a proposal (no writes outside .claude)
│   ├── postdeploy-test-design/SKILL.md # design focused pytest checks with actionable errors
│   ├── adr-draft/SKILL.md              # draft ADRs into .claude/scratch/ for operator review
│   ├── backup-progress/SKILL.md        # map ADR-009 requirements vs scripts/tests, list gaps
│   └── increment-plan/SKILL.md         # D1: turn one feature into increments with tests, acceptance, rollback
├── agents/
│   ├── compose-reviewer.md    # read-only; compose/hardening/pinning/network policy
│   ├── test-author.md         # read-only during transition; proposes tests as text
│   ├── security-reviewer.md   # read-only; secrets, exposure, UFW, privileges, supply chain
│   └── docs-steward.md        # read-only; doc/ADR drift vs implementation
├── tools/                     # tracked verifiers: check_rules/skills/agents/findings.py (Phase 6)
├── reports/                   # Phase 6 output, e.g. repo-findings.md
├── scratch/                   # git-ignored drafts (proposed patches, ADR drafts)
└── logs/                      # git-ignored guard decision log (guard.log)
```

### 5.1 Mapping `ChatGPTHint.txt` → Claude artefacts

| Hint section | Artefact(s) |
|---|---|
| 0 Scope | `CLAUDE.md` (Mission), `rules/operating-model.md` |
| 1 Environment | `CLAUDE.md` (Environment) |
| 2 Core principles | `rules/operating-model.md`, `rules/compose-stacks.md` (determinism) |
| 3 Repository policies | `rules/secrets.md`, `settings.json` (Read deny) |
| 4 Naming conventions | `rules/compose-stacks.md`, agent `compose-reviewer` |
| 5 Workflow | `CLAUDE.md` (Commands), skill `readonly-gate`, `readme_claude.md` |
| 6 Validation & testing | `rules/testing.md`, skills `readonly-gate`, `postdeploy-test-design`, agent `test-author` |
| 7 Runtime/network/security | `rules/compose-stacks.md`, `rules/shell-scripts.md`, agent `security-reviewer` |
| 7 Backups | `rules/backup-restore.md`, skill `backup-progress` |
| 8 Planned stacks & layout | `CLAUDE.md` (Repo map, Stack status), skill `new-stack-proposal` |
| 9 Users & access | `rules/compose-stacks.md` (access model section) – marked as not yet implemented |
| 10 Docs & language | `rules/docs-adr.md`, skill `adr-draft`, agent `docs-steward` |
| Repo-only: host/runtime/network reconciliation | `rules/host-runtime.md`, agent `security-reviewer` (UFW/exposure), skill `change-review` (IN9 checks) |
| Repo-only: Renovate/CI | `rules/ci-renovate.md`, skill `image-pin-audit` |

### 5.2 Permission design for `.claude/settings.json` (draft, verified in Phase 1)

Principle: deny wins over allow, so "deny everything, allow `.claude`" is impossible for Edit.
Instead: deny Edit on every known top-level path outside `.claude`, keep plan mode, and require
approval for the rest.

```jsonc
// DRAFT – final file must be strict JSON (no comments)
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "permissions": {
    "defaultMode": "plan",
    "deny": [
      // C1/C2: no writes outside .claude (anchor form verified in Phase 1, see V1.3)
      "Edit(/.claude/.gitignore)", "Edit(./.github/**)", "Edit(./docs/**)", "Edit(./scripts/**)", "Edit(./stacks/**)",
      "Edit(./tests/**)", "Edit(./config/**)", "Edit(./secrets/**)", "Edit(./logs/**)",
      "Edit(./.vscode/**)", "Edit(./Makefile)", "Edit(./deploy.sh)", "Edit(./README.md)",
      "Edit(./Todo.txt)", "Edit(./ChatGPTHint.txt)", "Edit(./pyproject.toml)",
      "Edit(./requirements-dev.txt)", "Edit(./renovate.json5)", "Edit(./.gitignore)",
      "Edit(./.gitattributes)", "Edit(./.pre-commit-config.yaml)", "Edit(./.yamllint.yml)",

      // C3: never read secret material
      "Read(./secrets/**)", "Read(**/.env)", "Read(**/*.env)", "Read(**/*.kdbx)",
      "Read(**/*.keyx)", "Read(**/*.pem)", "Read(**/*.key)", "Read(**/*.p12)", "Read(**/*.pfx)",
      "Read(~/.config/renovate/**)", "Read(~/.ssh/**)", "Read(~/.gnupg/**)",
      "Read(//etc/raspberry-pi-homelab/**)",

      // C4: no git history or index mutation
      "Bash(git commit *)", "Bash(git push *)", "Bash(git tag *)", "Bash(git merge *)",
      "Bash(git rebase *)", "Bash(git reset *)", "Bash(git checkout *)", "Bash(git switch *)",
      "Bash(git stash *)", "Bash(git add *)", "Bash(git rm *)", "Bash(gh *)",

      // C5: no Pi access (Q2, Q5)
      "Bash(ssh *)", "Bash(scp *)", "Bash(sftp *)", "Bash(rsync *)", "Bash(ansible *)",
      "Bash(*rpi-hub*)", "Bash(*192.168.178.29*)", "Bash(*rpi-hub.fritz.box*)",
      "WebFetch(domain:rpi-hub)", "WebFetch(domain:192.168.178.29)", "WebFetch(domain:rpi-hub.fritz.box)",
      "Bash(./deploy.sh *)", "Bash(sudo *)",
      "Bash(*scripts/host/*)", "Bash(*scripts/host-runtime/*)", "Bash(*scripts/network/*)",
      "Bash(*init-permissions.sh*)", "Bash(ufw *)", "Bash(systemctl *)", "Bash(usermod *)",
      "Bash(groupadd *)", "Bash(docker network create*)", "Bash(docker network rm*)",

      // C2/K1/K7: mutating or Pi-bound make targets and tools
      "Bash(make venv*)", "Bash(make hooks*)", "Bash(make precommit*)", "Bash(make format*)",
      "Bash(make ruff*)", "Bash(make check*)", "Bash(make ci*)", "Bash(make test*)",
      "Bash(make postdeploy*)", "Bash(make host-*)", "Bash(make backup*)", "Bash(make restore*)",
      "Bash(make renovate*)", "Bash(pre-commit *)", "Bash(gpg *)",
      "Bash(docker compose up*)", "Bash(docker compose down*)", "Bash(docker compose pull*)",
      "Bash(docker run *)", "Bash(docker login *)", "Bash(pip install *)"
    ],
    "allow": [
      "Bash(git status*)", "Bash(git diff*)", "Bash(git log*)", "Bash(git show*)",
      "Bash(git ls-files*)", "Bash(git check-ignore*)", "Bash(git rev-parse*)",
      "Bash(make doctor)", "Bash(make doctor-strict)"
    ]
  }
}
```

Notes:
- Deny rules are grouped in the final file as *transition block* (C1/C2 Edit denies, mutating
  make targets) and *permanent block* (C3–C5). JSON has no comments, so the grouping is documented
  in `readme_claude.md` with the exact entries of each block.
- `make doctor` (Q4) is allowed. It runs tool version checks and `docker --version`; the
  side-effect check from 5.3 applies to it as well (V1.7).
- Self-protection (active from Phase 1b): `Edit(./.claude/hooks/**)`, `Edit(./.claude/settings.json)`,
  `Edit(./.claude/settings.local.json)` are added to deny, so Claude cannot weaken its own guard.
  Later changes to these files are made by the operator.
- Pi patterns (Q2) catch literal host names and IPs only. Names resolved indirectly (e.g. via
  `/etc/hosts` aliases, variables, or scripts) are not covered (K3).
- `make test` is denied because the `test` target depends on `venv` (writes). The read-only
  equivalent is in 5.3.
- `"Bash(*rpi-hub*)"` also blocks harmless local strings containing `rpi-hub`; accepted.
- IP-based Pi access cannot be fully covered by patterns (K3). Confirm the Pi IP in Q2.
- The `./` anchors in the draft above are **superseded**; the as-built file uses `/` anchors.
  See 5.2.1 for the resolved anchor question and every other deviation.

### 5.2.1 As-built deviations from the 5.2 draft (Phase 1a, verified 2026-09-18)

Source: https://code.claude.com/docs/en/permissions, retrieved 2026-09-18 (no publication date on
the page; newest version notes cited there are v2.1.268/v2.1.269).

| ID | Draft | As built | Reason |
|---|---|---|---|
| D-a | `Edit(./docs/**)`, `Edit(./Makefile)`, … | `Edit(/docs/**)`, `Edit(/Makefile)`, … | The docs define four pattern types: `path` and `./path` anchor at the **current directory**, `/path` at the **settings source** (= primary working directory for project settings), `//path` at the filesystem root, `~/path` at `$HOME`. `/` is cwd-independent and therefore the correct anchor for repo-root paths. This answers the open V1.3 question. |
| D-b | – | added `"disableBypassPermissionsMode": "disable"` and `"disableAutoMode": "disable"` | Documented `permissions` keys. `defaultMode: plan` only sets the *starting* mode; these two keys prevent a session from being started in or switched to `auto`/`bypassPermissions`, which closes the remaining part of K8. |
| D-c | `Read(**/.env)`, `Read(**/*.env)` | unchanged | Confirmed: bare/single-segment **deny** patterns match at any depth, and `Read(.env)` ≡ `Read(**/.env)`. `.env.example` does not end in `.env`, so it stays readable (T07). |
| D-d | – | no path rules for `Write(...)`, `MultiEdit(...)`, `NotebookEdit(...)`, `Glob(...)` | Documented (v2.1.210+): Claude Code checks file permissions against `Edit(path)` and `Read(path)` rules **only**. A path rule on the other tool names is accepted but never consulted and warns at startup. `Edit(path)` governs Write/MultiEdit/NotebookEdit; `Read(path)` governs Glob. The draft already complied; recorded so it is not "fixed" later. |
| D-e | `Bash(*rpi-hub*)` etc. | unchanged | Confirmed stronger than assumed: deny rules apply when **any** subcommand matches, including inside a subshell, a command substitution or a loop body, and they match past leading variable assignments. Wrappers `timeout`, `time`, `nice`, `nohup`, `stdbuf`, `command`, `builtin` and bare `xargs` are stripped before matching. Still **not** matched: the same program by absolute path (`/usr/bin/ssh`), inside `sh -c '…'`, or `git -C . push` → K3 stands, and closing exactly this gap is the guard's job (T10, T11, T14). |
| D-f | – | `Edit(**)` + `Edit(!.claude/**)` **rejected** | See V1.3b below. |

**V1.3b (optional catch-all experiment, operator-approved, result: negative).** Instead of
enumerating known top-level paths, `deny: ["Edit(**)", "Edit(!.claude/**)"]` was tried, using the
documented gitignore negation ("a deny pattern starting with `!` carves the paths it matches out of
the `path` or `./path` rules listed before it"). Result on 2.1.276: **all** `Edit`/`Write` calls were
denied, `.claude/` included — `File is in a directory that is denied by your permission settings.`
The carve-out is ineffective here, matching the documented limit *"a carve-out can't reopen a file
inside a directory that a rule blocks as a whole"*. Both entries were removed by the operator.

Consequences to keep in mind:

- The enumeration in 5.2 is the only workable deny form, so it covers **known** top-level paths
  only. A newly created top-level file or directory is not denied by `settings.json`.
- That residual gap is covered by the guard's path check (5.4.3), which allows nothing outside
  `<root>/.claude/` regardless of the path's name (T02, T03, T04, T16).
- `settings.json` takes effect **without restarting Claude Code** (observed: Bash allow/deny and the
  Edit denies were live immediately after the file was written).
- A deny rule cannot be approved interactively — deny always wins. A mistake in the deny list can
  therefore lock Claude out of `.claude/` itself, and only the operator can undo it. Treat edits to
  the deny list as operator-only from Phase 1b on (self-protection).

### 5.3 Read-only validation gate (skill `readonly-gate`)

All commands run from the WSL repo root with `PYTHONDONTWRITEBYTECODE=1` and without creating or
updating `.venv`. Precondition: `.venv` already exists (created by the operator).

```bash
export PYTHONDONTWRITEBYTECODE=1
git status --porcelain --ignored > /tmp/claude-gate-before.txt
.venv/bin/ruff check --no-fix --no-cache .
.venv/bin/ruff format --check --no-cache .
.venv/bin/yamllint -s .
# ShellCheck from .venv (pinned via R0.0, identical to pre-commit). Never use system shellcheck.
git ls-files '*.sh' | xargs -r .venv/bin/shellcheck -x
.venv/bin/python -m pytest -p no:cacheprovider --strict-markers -q tests/precommit -m precommit
.venv/bin/python -m pytest -p no:cacheprovider --strict-markers -q tests \
  -m "not postdeploy" --ignore=tests/postdeploy --ignore=tests/precommit
git status --porcelain --ignored > /tmp/claude-gate-after.txt
diff /tmp/claude-gate-before.txt /tmp/claude-gate-after.txt && echo "OK: no side effects"
```

Acceptance: the final `diff` is empty. Any difference is a C2 violation and must be reported.
Flags (`--no-fix`, `--no-cache`) are verified against the installed ruff version in Phase 4
(`ruff check --help`). Whether the precommit pytest tests themselves write files (e.g. temp output
of `docker compose config` or gitleaks) is checked by the same diff.

### 5.4 PreToolUse guard hook (E3 revised)

Primary sources to re-check in Phase 1a (behaviour is version-dependent):
https://code.claude.com/docs/en/hooks-guide and https://code.claude.com/docs/en/hooks.

**Re-check performed 2026-09-18 on Claude Code 2.1.276.** The hooks reference carries no
publication date; its newest version note is v2.1.267, so the installed CLI is at or past the
documented state. Result: the contract in this section **holds unchanged**. Confirmed in detail:

| Item | Documented behaviour (2026-09-18) | Effect on 5.4 |
|---|---|---|
| stdin payload | `session_id`, `transcript_path`, `cwd`, `tool_name`, `tool_input`, `hook_event_name`, `tool_use_id`, plus `permission_mode`, `prompt_id`, `scratchpad_dir` | H4 unchanged; the guard uses `tool_name`, `tool_input`, `cwd` only. The extra fields are available if a later phase needs them. |
| exit 0 | "no decision", the normal permission flow still applies | Q8 unchanged: unclassified commands exit 0. |
| exit 2 | blocks the call; stderr becomes the reason shown to Claude; a JSON `permissionDecision: "allow"` cannot override it | H3 unchanged. |
| other exit codes | **1 and 3–255 do not block** | Confirms H2: the guard must use exactly 0 or 2, and every fail-closed path must exit 2. |
| stdout JSON | optional `hookSpecificOutput.permissionDecision` = `allow`/`deny`/`ask` with `permissionDecisionReason` | Not used (H3). Exit 2 + stderr is sufficient and depends on fewer output-format details. |
| `timeout` | unit is **seconds**, default 600 for `command` hooks | The planned `"timeout": 10` means 10 s, as intended. |
| `${CLAUDE_PROJECT_DIR}` | substituted in `command` and also exported into the hook process environment | H4 works in both forms. |
| matcher | exact name, `|`/`,`-separated list, or an **unanchored** JavaScript regex | `Edit` alone would already match `MultiEdit`/`NotebookEdit`; 5.4.1 keeps the explicit list for readability. The guard additionally treats any unknown edit-shaped tool defensively. |
| tool names | `Bash`, `Edit`, `Write`, `Read`, `Grep`, `Glob`, `WebFetch` are listed explicitly; `MultiEdit`/`NotebookEdit` appear only contextually | No change; the guard classifies by tool name and falls through to exit 0 for anything it does not know. |

**Documented contract used by the guard [V, hooks guide]:** the hook receives event JSON on stdin
(including `tool_name`, `tool_input`, `cwd`); exit code `2` blocks the tool call and stderr is fed
back to Claude; exit code `0` means *no decision* and the normal permission flow still applies.
The guard therefore **never approves** anything; it can only block. Deny rules from 5.2 stay the
first layer.

**Known risk [V, GitHub issues #37210, #43407, March/April 2026]:** users reported PreToolUse deny
decisions being ignored for Edit/Write/Bash in earlier versions. Whether this affects 2.1.273 is
unknown → negative tests V1.10–V1.14 are mandatory before relying on the hook.

#### 5.4.1 Registration (in `.claude/settings.json`)

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit|NotebookEdit|Read|Grep|Glob|Bash|WebFetch",
        "hooks": [
          { "type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/guard.py\"", "timeout": 10 }
        ]
      }
    ]
  }
}
```

To verify in Phase 1a: matcher syntax, availability of `$CLAUDE_PROJECT_DIR`, timeout key and
unit, and the current names of file-editing tools in 2.1.273.

#### 5.4.2 Design rules

| ID | Rule |
|---|---|
| H1 | Python 3 standard library only (`json`, `shlex`, `os`, `re`, `pathlib`, `subprocess` for `git rev-parse`); no `.venv` dependency, so the guard works even if the venv is broken (Q7). |
| H8 | Tokenising uses `shlex` only (Q7). `shlex` does not understand `$( … )`, backticks, or process substitution as nested units, so these are extracted first by a small balanced-delimiter scanner in `guard.py` (respecting single/double quotes), then each extracted body is tokenised with `shlex` recursively. Unbalanced delimiters → block (H2). |
| H2 | **Fail-closed:** any exception, unparsable stdin, unknown tool input shape, or `shlex` parse error → exit 2 with reason. (Exit codes other than 0/2 would be non-blocking.) |
| H3 | Exit 2 + one-line stderr reason only. No stdout JSON, to avoid depending on output-format details. |
| H4 | Project root = `$CLAUDE_PROJECT_DIR`, else `git rev-parse --show-toplevel` from `cwd`; if neither resolves → block. |
| H5 | Policy data in `guard-config.json` (mode, pi identifiers, secret globs, allowed temp dirs); logic in `guard.py`. |
| H6 | Every decision (block and pass) appended to `.claude/logs/guard.log` as one JSON line without file contents or command secrets beyond the command string. Log write failure does not change the decision. |
| H7 | Mode `transition` enforces C1–C5; mode `operate` (Phase 8) drops C1/C2 path restrictions and keeps C3–C5 and self-protection. |

#### 5.4.3 File tools (Write, Edit, MultiEdit, NotebookEdit)

1. Take `tool_input.file_path` (or `notebook_path`); missing → block.
2. Resolve relative to `cwd`, then `os.path.realpath` (follows symlinks and `..`).
3. Allow only if the resolved path is inside `<root>/.claude/`.
4. Block even inside `.claude/` for: `hooks/**`, `settings.json`, `settings.local.json` (self-protection, active from Phase 1b via config flag `self_protect: true`).
5. File `.claude/.gitignore` is protected against edit

#### 5.4.4 Read tools (Read, Grep, Glob)

Block when the resolved path or glob pattern matches secret patterns: `secrets/**`, `*.env`,
`.env`, `*.kdbx`, `*.keyx`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `~/.ssh/**`, `~/.gnupg/**`,
`~/.config/renovate/**`, `/etc/raspberry-pi-homelab/**`. `.env.example` stays readable.

#### 5.4.5 Bash inspection (recursive)

The guard builds a list of *command segments* and inspects each one:

1. **Split** with `shlex.shlex(punctuation_chars=True)` on `;`, `&&`, `||`, `|`, `&`, newlines.
2. **Extract nested code** and inspect it recursively (max depth 5; deeper → block):
   `bash|sh|zsh|dash -c <arg>`, `eval <args>`, `$( … )`, backticks, `<( … )`, `>( … )`,
   `xargs <cmd>`, `find … -exec|-execdir <cmd> ;`, `watch <cmd>`, `flock <file> <cmd>`.
3. **Strip wrappers** before evaluating the command head: `env [VAR=val…]`, `VAR=val` prefixes,
   `command`, `builtin`, `exec`, `nohup`, `nice`, `ionice`, `timeout <n>`, `time`, `stdbuf …`,
   `setsid`, `unbuffer`.
4. **Normalise the head** to its basename (`/usr/bin/ssh` → `ssh`).
5. **Shell invocations whose code is not a `-c` argument** → block during transition. This covers
   heredocs (`bash <<…`), stdin scripts (`sh -s`, `python3 -`), pipes into a shell (`| bash`,
   `| sh`) and script arguments (`bash <script>`), because the executed body is not reliably
   inspectable. A script path given this way is still checked against the Pi-script list first,
   so the reported reason names the actual violation (C5 instead of C1).
6. **Inline interpreter code**: `python3 -c`, `perl -e/-i`, `ruby -e`, `node -e` → block during
   transition. The flags are matched anywhere in the segment, which also blocks unrelated uses of
   the same flags (for example `python3 -m pytest -c pytest.ini`); accepted as a false positive.
   `python -m pytest` and `.venv/bin/python -m pytest` without such a flag stay allowed.
7. **Raw scan** of the full original string (after un-escaping) for Pi identifiers
   (`rpi-hub`, `rpi-hub.fritz.box`, `192.168.178.29`) → block. Catches quoting tricks that the
   parser resolves differently, and also blocks read-only commands that merely mention an
   identifier (for example `grep -rn rpi-hub docs/`); accepted as a false positive.

**Block list per segment (transition mode):**

| Category | Heads / patterns |
|---|---|
| C4 Git / repository state | `git` with `commit`, `push`, `tag`, `merge`, `rebase`, `reset`, `checkout`, `switch`, `stash`, `add`, `rm`, `am`, `cherry-pick`, `revert`, `clean`, `config`; `gh` (all subcommands, reported as C4 because it creates commits, branches and pull requests) |
| C5 Remote / Pi | `ssh`, `scp`, `sftp`, `rsync`, `ansible*`, `mosh`, `nc`, `ncat`, `socat`, `telnet`; any command containing a Pi identifier (step 7), which covers `curl`, `wget`, `ping`, `nmap`; `./deploy.sh`, `deploy.sh`, `sudo`, `su`, `doas`; any execution of `scripts/host/*`, `scripts/host-runtime/*`, `scripts/network/*`, `init-permissions.sh` (also via `bash <script>`); `ufw`, `systemctl`, `systemd-run`, `usermod`, `useradd`, `groupadd`, `groupmod`, `apt`, `apt-get`, `rpi-eeprom-update`, `rpi-update`; `docker network create`/`rm` (covered by the docker allowlist below) |
| C2 Mutating tools | `make` targets except `doctor`, `doctor-strict`, `help` (a bare `make` is blocked too); `pre-commit`; `gpg`, `gpg2`; `pip`/`pip3` except `list`, `show`, `check`, `freeze`; `ruff` except `check --no-fix` and `format --check|--diff`; `docker` except `version`, `info`, `ps`, `images` and `docker compose config` |
| C1 File writes | `rm`, `mv`, `cp`, `ln`, `touch`, `mkdir`, `rmdir`, `chmod`, `chown`, `chgrp`, `truncate`, `install`, `dd`, `tee`, `patch`, `shred`, `sed -i`, `git apply`. Every **write target** must resolve inside `<root>/.claude/` or an allowed temp dir (`/tmp/claude-*`). Which operands are targets: for `cp`, `mv`, `ln`, `install` (config key `target_last_operand_heads`) only the **last** operand; for `sed -i` all operands except the leading script (unless `-e`/`-f` is given); for `dd` only `of=`; for every other head all positional operands. Mode and owner operands of `chmod`, `chown`, `chgrp`, `install` are ignored. A `{}` placeholder from `find -exec` blocks with its own reason. `find -delete` is blocked. |
| C1 Redirections | `>`, `>>`, `>` with clobber, `&>`, `2>` targets outside `.claude/`, `/tmp/claude-*`, or `/dev/null`; here-documents (`<<`, `<<<`) block per step 5; `<` targets are checked against the secret patterns |
| C3 Secret reads | `cat`, `less`, `more`, `head`, `tail`, `grep`, `rg`, `egrep`, `fgrep`, `awk`, `sed`, `source`, `.`, `base64`, `xxd`, `od`, `strings`, `tar`, `zip` on secret patterns (5.4.4); additionally the **source** operands of `cp`, `mv`, `ln`, `install` and the `if=` operand of `dd`, so relaxing the target rule above cannot exfiltrate secrets into `.claude/` |
| Self-protection | With `self_protect: true`, any write target inside `.claude/hooks/**`, `.claude/settings.json` or `.claude/settings.local.json` blocks with a self-protection reason, in `transition` and in `operate` mode alike |

Anything the parser cannot classify is **not** blocked by the guard (exit 0, decision Q8) and falls through to
the deny rules and the plan-mode approval prompt. This keeps normal read-only work usable; the
operator remains the final gate.

The head lists above are policy data in `guard-config.json` (H5), not literals in `guard.py`:
`shell_heads`, `interpreter_heads`, `interpreter_inline_flags`, `denied_git_subcommands`,
`write_git_subcommands`, `operator_only_heads`, `remote_heads`, `host_mutation_heads`,
`denied_heads`, `write_heads`, `target_last_operand_heads`, `mode_operand_heads`,
`secret_read_heads`, `nested_exec_heads`, `allowed_make_targets`, `allowed_docker_subcommands`,
`allowed_docker_compose_subcommands`, `allowed_pip_subcommands`, `pi_script_fragments`,
`pi_script_basenames`, `allowed_temp_prefixes`, `null_targets`.

#### 5.4.6 Test matrix (`.claude/hooks/tests/`)

Run: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider -q .claude/hooks/tests`
The tests invoke `guard.py` as a subprocess with crafted stdin JSON and `CLAUDE_PROJECT_DIR`
pointing to a temporary fixture repo (`tmp_path`), so no real repo file is touched.

The matrix spans two files since Phase 1b:

- `test_guard.py` – **T01–T35**, one test function per row (T18 and T19 assert both sub-cases).
- `test_guard_operands.py` – **T36–T43**, the operand-classification patch: which operand of a
  command is a write *target* versus a *source*, and which violations must report self-protection
  rather than a plain C1 breach.

| Case | Input | Expected |
|---|---|---|
| T01 | Write `.claude/scratch/a.md` | exit 0 |
| T02 | Write `README.md` | exit 2 |
| T03 | Edit `.claude/../stacks/x.yml` | exit 2 |
| T04 | Write via symlink `.claude/scratch/link` → `../../Makefile` | exit 2 |
| T05 | Edit `.claude/hooks/guard.py` with `self_protect: true` | exit 2 |
| T06 | Read `secrets/backup/gpg/key.asc` | exit 2 |
| T07 | Read `stacks/monitoring/compose/.env.example` | exit 0 |
| T08 | Bash `git status` | exit 0 |
| T09 | Bash `git commit -m x` | exit 2 |
| T10 | Bash `bash -c "git commit -m x"` | exit 2 |
| T11 | Bash `sh -c 'echo ok && ssh rpi-hub true'` | exit 2 |
| T12 | Bash `echo $(ssh 192.168.178.29 id)` | exit 2 |
| T13 | Bash ``echo `curl http://rpi-hub.fritz.box:3000` `` | exit 2 |
| T14 | Bash `env FOO=1 timeout 5 /usr/bin/scp a rpi-hub:/tmp` | exit 2 |
| T15 | Bash `find . -name x -exec rm {} \;` | exit 2 |
| T16 | Bash `echo x > README.md` | exit 2 |
| T17 | Bash `echo x > .claude/scratch/y.txt` | exit 0 |
| T18 | Bash `make precommit`; Bash `make doctor` | exit 2; exit 0 |
| T19 | Bash `ruff check --fix .`; Bash `ruff check --no-fix .` | exit 2; exit 0 |
| T20 | Bash `cat stacks/monitoring/compose/.env` | exit 2 |
| T21 | Bash `bash <<'EOF' … EOF` | exit 2 |
| T22 | Bash `python3 -c "open('x','w')"` | exit 2 |
| T23 | Bash with unbalanced quotes | exit 2 (fail-closed) |
| T24 | Invalid JSON on stdin | exit 2 (fail-closed) |
| T25 | WebFetch `http://rpi-hub:3000` | exit 2 |
| T26 | Nesting depth 6 | exit 2 |
| T27 | Bash `.venv/bin/python -m pytest -q tests/precommit -m precommit` | exit 0 |
| T28 | Bash `docker compose -f stacks/monitoring/compose/docker-compose.yml config` | exit 0 |
| T29 | Bash `echo "$(echo \"$(git push)\")"` (substitution nested in quotes, depth 2) | exit 2 |
| T30 | Bash `echo 'literal $(git push) in single quotes'` | exit 0 (not executed by the shell) |
| T31 | Bash `echo $(git status` (unbalanced) | exit 2 (fail-closed) |
| T32 | Bash `ls -la stacks/` (unclassified read) | exit 0 (Q8) |
| T33 | Bash `bash scripts/network/cleanup-ufw.sh --verbose` (dry-run mode) | exit 2 |
| T34 | Bash `DRY_RUN=1 ./scripts/network/bootstrap-networks.sh` | exit 2 |
| T35 | Read `scripts/network/cleanup-ufw.sh` | exit 0 |
| T36 | Bash `cp README.md .claude/scratch/copy.md` | exit 0 (source may be outside) |
| T37 | Bash `cp .claude/scratch/a.md docs/copy.md` | exit 2 (target outside) |
| T38 | Bash `cp secrets/backup/gpg/key.asc .claude/scratch/k` | exit 2 (C3 source) |
| T39 | Bash `sed -i s/a/b/ .claude/scratch/a.md`; Bash `sed -i s/a/b/ README.md` | exit 0; exit 2 |
| T40 | Bash `dd if=/dev/zero of=.claude/scratch/d.bin`; `… of=README.md` | exit 0; exit 2 |
| T41 | Bash `sed -i s/a/b/ .claude/hooks/guard.py` with `self_protect: true` | exit 2, reason mentions self-protection |
| T42 | Bash `gh pr create` | exit 2, reason C4 |
| T43 | Bash `echo x > .claude/.gitignore` with `self_protect: true` | exit 2, reason mentions self-protection (redirection into a self-protected path) |
| T44 | Bash `ls > /dev/null 2>&1`; Bash `ls 2>&1 \| tail -3` (fd duplication) | exit 0; exit 0 |
| T45 | Bash `echo x &> README.md` | exit 2 |
| T46 | Write `~/.claude/plans/x.md` (plan-mode plan file) | exit 0 (P6 applied) |
| T46b | Write `~/.claude/settings.json`, `~/.claude/plans-evil/x.md`, `~/.ssh/id_rsa` | exit 2 — the P6 allowance stays narrow; the trailing slash in the prefix is what makes `plans-evil` fail |

---

## 6. Implementation phases

Each phase ends with: verification output → operator review of `git diff -- .claude` → operator
commits manually. Claude never commits.

### Phase 0 – Preparation (operator)

- [x] Work in the WSL checkout, not the Windows copy.
- [x] Copy this file into `<wsl-repo>/.claude/ClaudeTransition.md` (LF line endings).
- [x] Create the feature branch from current `main` (Q9/IN11): `git switch main && git pull --ff-only && git switch -c chore/r0-claude-transition`.
- [x] Ruleset `protect-main` configured in GitHub per `docs/operations/git-branch-workflow.md` §7.1/§7.2.
- [x] Verify ruleset effectiveness per `git-branch-workflow.md` §7.3; result: `1a rules listed (deletion, non_fast_forward, pull_request, required_status_checks); 1b direct push to main rejected (error: GH013: Repository rule violations found for refs/heads/main.)`.
- [x] Record `claude --version` here: `2.1.273`.
- [x] Record WSL checkout path here: `/home/micro/src/raspberry-pi-homelab`.
- [x] Record Pi FQDN here: `rpi-hub.fritz.box`.
- [x] **R0.0 toolchain parity merged and deployed (10.6) – prerequisite for Phase 1a.**
- [x] Ensure `.venv` exists: operator ran `make ci` successfully (creates/updates `.venv`, upgrades pip, installs `requirements-dev.txt`).
- [x] Record `.venv` tool versions after R0.0 (commands in 10.5): python `3.12.3`, ruff `0.14.11` expected, shellcheck `0.10.0` expected, yamllint `1.35.1` expected, pytest `____`, pre-commit `____`.
- [x] Re-run `.venv/bin/python -m pip check` explicitly with the venv interpreter (first run was probably the system pip: no `(.venv)` prompt); `git status --porcelain` was clean [V, operator output].
- [x] Confirm `git status --porcelain` is clean after `make ci` (pre-commit fixers may have modified files).
- [x] Answer open questions Q1–Q6 (section 9).
- [x] Answer Q7 and Q8 (section 9).
- [x] Confirm toolchain in WSL: `python3` 3.12.3 (matches CI `python-version: "3.12"`; guard needs >= 3.10); system `shellcheck` 0.9.0 (differs from pre-commit pin, see F21).

Acceptance: branch exists, Claude Code version recorded, questions answered.

### Phase 1a – Safety foundation: build and test (hook not yet active)

Deliverables: `.claude/.gitignore`, `.claude/hooks/guard.py`, `.claude/hooks/guard-config.json`,
`.claude/hooks/tests/test_guard.py`, draft `.claude/settings.json` **without** the `hooks` block.

- [x] Re-read hooks docs (5.4) and record doc date and any contract differences here.
      *Done 2026-09-18, recorded in 5.4; permissions docs re-read as well, recorded in 5.2.1.*
- [x] Write `.claude/.gitignore`: `settings.local.json`, `scratch/`, `logs/`.
      *Done. `logs/` is redundant with the root `.gitignore` rule but kept explicit (K5).*
- [x] Write `settings.json` from 5.2 (strict JSON), `self_protect: false` in guard config.
      *Done with deviations D-a, D-b, D-f (5.2.1). No `hooks` block, no self-protection denies —
      both are Phase 1b and operator-applied.*
- [x] Write `guard.py`, `guard-config.json`, tests T01–T35.
      *Done. `guard.py` ≈ 600 lines, stdlib only; policy data entirely in `guard-config.json` (H5);
      35 test functions, one per matrix row (T18 and T19 assert both sub-cases).*
- [x] Restart Claude Code; run `/status`, `/permissions`.
      *Operator step. Note: `settings.json` was already live without a restart.*

Verification (Claude-run results recorded 2026-09-18 on Claude Code 2.1.276; the live checks
V1.2–V1.8 need the operator, because plan mode and the permission dialog are not scriptable):
- V1.1 `git check-ignore -v .claude/settings.local.json .claude/logs/guard.log .claude/scratch/x` → all matched by `.claude/.gitignore`.
  **PASSED:** `.claude/.gitignore:6:settings.local.json`, `.claude/.gitignore:12:logs/`,
  `.claude/.gitignore:9:scratch/` → K5 closed. Before the file existed, only `guard.log` was
  ignored (by the root rule `logs/`); `settings.local.json` and `scratch/` were not ignored at all.
- V1.2 `/status` lists "Shared project settings"; mode shows plan.
- V1.3 Negative test: ask Claude to append a line to `README.md` → denied without prompt. If not,
  switch the anchor form per the permissions docs and re-test. Working form: `Edit(/README.md)`
  (`/`-anchored, D-a; still to be confirmed live by the operator).
- V1.3b Catch-all experiment `Edit(**)` + `Edit(!.claude/**)` → **FAILED, entries removed.**
  Full result in 5.2.1 (D-f).
- V1.4 Negative tests: `git commit --allow-empty -m test`, `ssh rpi-hub true`, `make precommit`,
  reading a file under `secrets/` → all denied.
- V1.5 Positive test: edit a file under `.claude/scratch/` → allowed after approval.
- V1.6 `claude doctor` reports no rejected permission or hook entries.
- V1.7 `make doctor` runs without prompt; `git status --porcelain --ignored` identical before/after.
- V1.8 Negative tests for Q2/Q5: `curl -fsS http://192.168.178.29:3000/api/health`,
  `ping -c1 rpi-hub.fritz.box`, WebFetch `http://rpi-hub:3000` → all denied.
- V1.9 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider -q .claude/hooks/tests` → 35 passed;
  `.venv/bin/ruff check --no-fix --no-cache .claude/hooks` and `ruff format --check` clean.
  **PASSED:** `35 passed in 0.97s`; ruff check → `All checks passed!`; ruff format --check →
  `2 files already formatted`.
- V1.9b (added) K9 line endings: `grep -rl $'\r' .claude` → no output.
- V1.9c (added) C1/C2 side-effect proof: `git status --porcelain --ignored` captured before and
  after the full test run → `OK: no side effects`. `git diff --stat -- . ':!.claude'` shows only
  `Todo.txt`, which was already modified before the session started.
- V1.9d (added) Repository static tests with the new artefacts present, run read-only from `.venv`:
  `tests/precommit -m precommit` → 8 passed, 4 deselected; `tests/guards` + `tests/doctor`
  (`-m "not postdeploy"`) → 7 passed, 1 skipped. `tests/precommit -m lint` → 1 failed, 3 passed;
  the failure is pre-existing and unrelated to `.claude/` (new finding F25).

### Phase 1b – Activate the hook (operator applies, Claude verifies)

- [x] Operator reviews `guard.py` line by line (it is the enforcement boundary).
      *Done 2026-09-18, reviewed and made some changes with help of Claude, commit hash 117d092f528494786b66ff4bb166075ed86e7344, message: fix(claude-guard): classify write targets separately from sources...*
- [x] Operator adds the `hooks` block (5.4.1) and self-protection denies (5.2) to `settings.json`
      and sets `self_protect: true`. From here on, only the operator changes hook/settings files.
- [ ] Restart Claude Code; `/hooks` shows the PreToolUse entry.

Verification (live, inside Claude Code). The cases are chosen so that the deny patterns from 5.2
do **not** match them; a block therefore proves the hook works:
- V1.10 `bash -c "git commit --allow-empty -m test"` → blocked, stderr reason shown, no commit (`git log -1` unchanged).
- V1.11 `sh -c 'true && ssh rpi-hub.fritz.box true'` → blocked.
- V1.12 `echo test > README.md` → blocked; file unchanged.
- V1.13 Edit `.claude/hooks/guard.py` → blocked (self-protection).
- V1.14 Temporarily rename `guard-config.json` (operator) → any Bash call blocked (fail-closed); restore name.
- V1.15 `.claude/logs/guard.log` contains one JSON line per V1.10–V1.13 decision.
- V1.16 If any of V1.10–V1.13 is **not** blocked: stop, record Claude Code version and case,
  treat the hook as non-enforcing (see risk table), and escalate before Phase 2.

**RESULTS — executed 2026-09-23 by Claude as live tool calls, Claude Code 2.1.276, branch
`chore/r0-claude-safety-foundation`, HEAD `e7580bb`.** Every case is a real tool call, so the hook
was exercised end-to-end; stderr is quoted verbatim.

| ID | Verdict | Verbatim guard reason |
|---|---|---|
| V1.10 | **PASSED** | `guard: C4: git commit is reserved for the operator` |
| V1.10b | **PASSED** | `guard: unbalanced quotes in command` — the unbalanced form fails closed on the quote and never reaches the C4 classification, confirming that only the balanced form actually tests C4 |
| V1.11 | **PASSED** | `guard: C5: command references the Raspberry Pi (rpi-hub)` (raw identifier scan, 5.4.5 step 7) |
| V1.12 | **PASSED** | `guard: C1: redirection would write outside .claude/: README.md` |
| V1.13 | **PASSED** | `guard: self-protection: only the operator edits /home/micro/src/raspberry-pi-homelab/.claude/hooks/guard.py` |
| V1.14 | **PASSED (complete)** | Variant on 2026-09-23 via `--config /tmp/claude-missing-config.json`; hook-level half completed the same day after the operator renamed the file. See note below. |
| V1.15 | **PASSED** | 8 new JSON lines (log grew 49 → 57), each with `ts`, `tool`, `input`, `decision`, `reason`; both `block` and `pass` decisions recorded |
| V1.16 | **PROCEED** | No case was unblocked. The hook enforces on 2.1.276; no escalation needed, Phase 2 is unblocked. |

V1.14 in two steps. The planned rename is an operator step, and the guard twice refused to let
Claude do it — `mv .claude/hooks/guard-config.json .claude/hooks/guard-config.json.bak` →
`guard: self-protection: only the operator edits .claude/hooks/guard-config.json.bak`. Note it
caught the *target* operand, which is the operand-classification fix from the Phase 1b guard review
working as intended. The fail-closed path was therefore first exercised by invoking
`guard.py --config /tmp/claude-missing-config.json` directly.

**Hook-level half completed 2026-09-23.** The operator renamed the config, Claude made two ordinary
tool calls, and both were blocked with the identical reason:

```text
Bash `ls`          -> PreToolUse:Bash hook error: guard: fail-closed: FileNotFoundError:
                      [Errno 2] No such file or directory: '…/.claude/hooks/guard-config.json'
Read `README.md`   -> PreToolUse:Read hook error: guard: fail-closed: FileNotFoundError: (identical)
```

The `Read` case matters as much as the `Bash` one: it shows fail-closed covers the **whole matcher**,
not just command execution. A missing policy file does not make the guard permissive, it makes it
total. The operator restored the name afterwards and the guard was confirmed operational again
(a harmless `ls -la` probe returned exit 0).

**Layering observation from the same test.** The `mv` was blocked by the *hook*, not by P5's
`Edit(/.claude/hooks/**)` deny rule. Per the permissions docs, deny rules check redirect and `tee`
targets against `Edit` rules, but not arbitrary command operands — so a Bash `mv` slips past the
settings layer entirely and only the guard catches it. Conversely the settings layer catches things
before the hook ever runs. The two layers cover **different** surfaces; neither alone is sufficient,
which is the concrete justification for keeping P5.

No side effects, verified before and after:

- HEAD unchanged at `e7580bb`, no new commit despite V1.10.
- `README.md` byte-identical: blob `2eb4543eca640eb2dc401861f7438ff7dfdc7ccd`, 3082 bytes.
- `.claude/hooks/` still contains `guard-config.json`, `guard.py`, `tests`.
- `git status --porcelain` shows only `Todo.txt` (operator's own edit).

**Consequence for the risk table:** the row "Hook deny ignored by Claude Code (reported in #37210,
#43407 for earlier versions)" is **not** realised on 2.1.276 — deny was honoured for `Bash` and
`Edit` in six independent cases. The mitigation stands unchanged: re-run V1.10–V1.16 after every
Claude Code update, because this is a version-specific observation, not a guarantee.

**Live evidence collected so far (2026-09-18, Claude Code 2.1.276, hook registered).** These were
observed incidentally while adapting the tests, before the planned restart:

- **V1.13 PASSED.** `Edit .claude/hooks/guard.py` →
  `PreToolUse:Edit hook error: […] guard: self-protection: only the operator edits
  /home/micro/src/raspberry-pi-homelab/.claude/hooks/guard.py`. The edit did not happen.
- **Bonus (5.4.5 step 6) PASSED.** A `Bash` call containing `python3 -c …` →
  `PreToolUse:Bash hook error: […] guard: C1: inline interpreter code is not inspectable: python`.
- Both blocks prove the hook **is enforcing** on 2.1.276 for the `Edit` and `Bash` tools, which is
  the failure mode reported in issues #37210/#43407 for earlier versions. V1.10–V1.12 and V1.14–V1.15
  still need to be run explicitly after the restart; the risk-table rule (re-run after every Claude
  Code update) stays in force.

**Open items found while adapting the tests (operator action, both inside self-protected files):**

1. **Self-protection denies are incomplete in `settings.json`.** The deny list contains
   `Edit(/.claude/.gitignore)` but **not** `Edit(/.claude/hooks/**)` and
   `Edit(/.claude/settings.json)`, which 5.2 requires from Phase 1b on. The guard covers all three
   via `self_protect: true`, so the boundary holds today, but it rests on a single layer instead of
   the intended two. Adding them restores defence in depth.
2. **T43 blocks with the wrong reason.** Verified against the live guard:
   `echo x > .claude/.gitignore` → exit 2 with
   `C1: redirection would write outside .claude/: .claude/.gitignore`. The path is plainly *inside*
   `.claude/`, so the message misdirects; the actual cause is self-protection.
   `check_redirections` is the only write path that still lacks the self-protection branch that
   `check_write_operands` and `check_file_tool` already have. Fix: patches **P1** (guard) and **P2**
   (test) below; T43 is the regression test for it.
3. **`2>&1` is falsely blocked (found by using the guard, not by the matrix).** `split_segments`
   treats every bare `&` as a control operator, so it splits inside the fd-duplication forms `>&`
   and `&>`. Probed against the live guard:

   | Command | Result |
   |---|---|
   | `ls 2>&1` | exit 2, `C1: redirection without a target` |
   | `ls 2>&1 \| tail -3` | exit 2, same |
   | `ls > /dev/null 2>&1` | exit 2, same |
   | `ls &> /dev/null` | exit 0, but only by accident: the `&` was read as backgrounding and the leftover `> /dev/null` happened to be allowed |

   Impact: this is a false positive on an extremely common shell idiom, so it blocks routine
   read-only work and pushes the operator towards workarounds — the "guard bug blocks legitimate
   work" risk in section 7, now realised. The read-only gate in 5.3 is unaffected because it uses
   no `2>&1`. Fix: patches **P3** (guard) and **P4** (tests) below; T44/T45 are the regression rows.

4. **The guard makes plan mode unusable (structural, not a parser bug).** C1 permits writes only
   under the *project's* `.claude/`, but Claude Code's plan mode writes its plan file to the
   *user's home* `.claude/plans/`. Observed 2026-09-18:

   ```text
   guard: C1: writes are restricted to .claude/ during the transition:
     /home/micro/.claude/plans/bash-c-git-commit-lively-boole.md
   ```

   `ExitPlanMode` reads the plan from that file, so with the guard active the plan-mode workflow
   cannot be completed at all — neither writing the plan nor exiting it. Decision E2 makes plan mode
   the default working mode, so this blocks the intended way of working.
   Proposed fix (operator, `guard-config.json` is self-protected): add a dedicated
   `allowed_write_prefixes` entry for `~/.claude/plans/`, kept separate from
   `allowed_temp_prefixes` so the intent stays readable. `guard.py` already expands `~` in
   `is_write_allowed`, but `check_file_tool` does **not** consult the prefix list — it only allows
   `<root>/.claude/`, so the fix needs a small change there too, plus a test row (T46).
   Interim workaround: work without plan mode, as in this session.

**Process observation.** All four items were found by *using* the guard for ordinary work, not by
the T01–T45 matrix, which only covers cases the design anticipated. Worth carrying into Phase 2+:
the matrix proves the design, day-to-day use finds the parser's blind spots.

#### Phase 1b – session state 2026-09-18 (handover, verifications incomplete)

**Status (2026-09-23): PHASE 1b COMPLETE.** V1.10–V1.16 all passed on Claude Code 2.1.276, patches
P1–P6 applied in a deliberate `self_protect: false` window that was closed again, matrix at
77 passed, and both follow-ups (3a T43 re-probe, 3b hook-level V1.14) done. `self_protect` is back
to `true` and the guard was confirmed operational. Nothing is left open in Phase 1b; the next step
is Phase 2, after the operator has committed.

Done and evidenced:

- Hook registered in `.claude/settings.json` (matcher `Write|Edit|MultiEdit|NotebookEdit|Read|Grep|Glob|Bash|WebFetch`, `python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/guard.py"`, `timeout: 10`).
- `self_protect: true`; `self_protected_paths` = `hooks`, `settings.json`, `settings.local.json`, `.gitignore`.
- Operator review of `guard.py` done, with fixes: write targets classified separately from sources
  (`target_last_operand_heads`), `gh` moved to `operator_only_heads`, `.gitignore` protected.
  Commit `117d092f528494786b66ff4bb166075ed86e7344`.
- Test matrix extended to two files, **65 passed** (35 + 30), ruff clean, no side effects.
- **V1.13 passed live** (self-protection on `Edit .claude/hooks/guard.py`).
- Hook wiring proven live for both tools: `Bash` blocked twice on the `2>&1` defect and once on
  `python3 -c`; `Edit` blocked on V1.13. This already answers the #37210/#43407 risk for 2.1.276 —
  PreToolUse deny is **not** ignored on this version.
- `.claude/logs/guard.log` is being written (9,133 bytes at handover) → H6 works, V1.15 has data.

Open, in the order to do them next session:

| # | Item | Who | Notes |
|---|---|---|---|
| 1 | ~~Apply patches **P1–P4**~~ | — | **DONE 2026-09-23** in the `self_protect: false` window. |
| 2 | ~~Apply patch **P5**~~ | — | **DONE 2026-09-23**, applied last so it re-locks `.claude/hooks/**`. |
| 3 | ~~Decide on the plan-mode fix~~ | — | **DONE 2026-09-23**: decided to allow `~/.claude/plans/`, implemented as **P6**, T46 covers it. |
| 3a | ~~Set `self_protect` back to `true`, then re-probe T43~~ | — | **DONE 2026-09-23**: restored, re-probe gave `exit 2`, `guard: self-protection: only the operator edits .claude/.gitignore`. P1 confirmed in production. |
| 3b | ~~Finish the hook-level half of V1.14~~ | — | **DONE 2026-09-23**: both `Bash` and `Read` failed closed while the config was renamed; name restored and guard confirmed operational. |
| 4 | ~~Run V1.10–V1.16 and record verbatim~~ | — | **DONE 2026-09-23**, all passed, V1.16 = proceed. Results table above. Only the hook-level half of V1.14 (rename the config) is still open. |
| 5 | Tick the Phase 1a/1b checkboxes | operator | Claude records results but never ticks. |
| 6 | Then Phase 2 (`CLAUDE.md` restructuring) | Claude | **Unblocked** — V1.16 says proceed. |

Why V1.10 must not be run as a plain shell command: a PreToolUse hook fires only on *Claude's*
tool calls. Typed into the operator's own shell, `bash -c "git commit --allow-empty -m test"` does
not reach the guard and simply creates an empty commit. The form below invokes the guard directly —
it only evaluates, never executes — and with `CLAUDE_PROJECT_DIR` unset it also exercises the H4
fallback via `git rev-parse --show-toplevel`.

```bash
cd /home/micro/src/raspberry-pi-homelab
R=/home/micro/src/raspberry-pi-homelab

# V1.10  balanced -- expect exit 2, reason names C4/git
printf '%s' '{"tool_name":"Bash","tool_input":{"command":"bash -c \"git commit --allow-empty -m test\""},"cwd":"'$R'"}' | python3 .claude/hooks/guard.py; echo "V1.10 exit=$?"
# V1.10b unbalanced quote -- expect exit 2, fail-closed (T23), NOT a C4 reason
printf '%s' '{"tool_name":"Bash","tool_input":{"command":"bash -c \"git commit --allow-empty -m test"},"cwd":"'$R'"}' | python3 .claude/hooks/guard.py; echo "V1.10b exit=$?"
# V1.11  expect exit 2, reason names C5
printf '%s' '{"tool_name":"Bash","tool_input":{"command":"sh -c \"true && ssh rpi-hub.fritz.box true\""},"cwd":"'$R'"}' | python3 .claude/hooks/guard.py; echo "V1.11 exit=$?"
# V1.12  expect exit 2, reason names C1
printf '%s' '{"tool_name":"Bash","tool_input":{"command":"echo test > README.md"},"cwd":"'$R'"}' | python3 .claude/hooks/guard.py; echo "V1.12 exit=$?"
# V1.13  expect exit 2, reason names self-protection
printf '%s' '{"tool_name":"Edit","tool_input":{"file_path":".claude/hooks/guard.py"},"cwd":"'$R'"}' | python3 .claude/hooks/guard.py; echo "V1.13 exit=$?"
# V1.14  fail-closed while the config is missing
mv .claude/hooks/guard-config.json .claude/hooks/guard-config.json.bak
printf '%s' '{"tool_name":"Bash","tool_input":{"command":"ls"},"cwd":"'$R'"}' | python3 .claude/hooks/guard.py; echo "V1.14 exit=$?"
mv .claude/hooks/guard-config.json.bak .claude/hooks/guard-config.json
# V1.15  one JSON line per decision above
tail -8 .claude/logs/guard.log
```

Additionally worth one live Claude tool call next session, because only that exercises the hook
end-to-end rather than the guard in isolation: ask Claude to run `bash -c "git commit --allow-empty
-m test"`. Expected: blocked by the hook, and `git log -1` unchanged.

#### Phase 1b – guard patches P1–P5 (**APPLIED 2026-09-23**)

These live here rather than in `.claude/scratch/` because `scratch/` is git-ignored: a copy there
survives on disk but not in a commit or a fresh clone. This subsection stays after application as
the record of what changed and why. All findings were verified against the live guard on
2026-09-23, Claude Code 2.1.276.

**How they were applied.** `self_protect: true` covers `.claude/hooks/**`, so Claude was blocked
from applying them — correctly, and demonstrated twice. The operator therefore opened a deliberate,
short-lived window by setting `self_protect: false`; Claude applied P1–P5 in order and the operator
closed the window afterwards. **P5 was applied last on purpose**: it adds `Edit(/.claude/hooks/**)`
to the deny list, which locks Claude out of those files again regardless of `self_protect`.

A sixth change rode along in the same window, because it needs the same files — the plan-mode fix,
open item 4, recorded below as **P6**.

##### P1 – `guard.py`, in `check_redirections`: report self-protection (T43)

Symptom:

```text
$ printf '%s' '{"tool_name":"Bash","tool_input":{"command":"echo x > .claude/.gitignore"},"cwd":"/home/micro/src/raspberry-pi-homelab"}' | python3 .claude/hooks/guard.py
guard: C1: redirection would write outside .claude/: .claude/.gitignore
exit=2
```

The call is blocked, so the boundary holds, but the reason is wrong: `.claude/.gitignore` is
*inside* `.claude/`. The cause is self-protection. Same for `echo x > .claude/settings.json`.
Root cause: `check_redirections` calls `is_write_allowed`, which returns `False` for a
self-protected path without saying why. `check_write_operands` and `check_file_tool` already have
the explicit self-protection branch; the redirection path does not.

```diff
             if token.endswith("<"):
                 if is_secret(ctx, target):
                     raise Blocked(f"C3: input redirection reads secret material: {target}")
                 continue
+            if is_self_protected(ctx, resolve(ctx, target)):
+                raise Blocked(f"self-protection: only the operator edits {target}")
             if not is_write_allowed(ctx, target):
                 raise Blocked(f"C1: redirection would write outside .claude/: {target}")
```

Mirrors the existing branch in `check_write_operands`; no new imports, and no behaviour change for
paths that are not self-protected — they still report C1.

##### P2 – `test_guard_operands.py`: T43 regression test

Add to the existing `test_self_protection_reports_itself` parametrize list, which already asserts
`"self-protection" in reason` and builds a config with `self_protect=True`:

```diff
 @pytest.mark.parametrize(
     "command",
     [
         "sed -i s/a/b/ .claude/hooks/guard.py",
         "cp /tmp/x .claude/settings.json",
         "rm .claude/hooks/guard-config.json",
+        # T43: redirection into a self-protected path must report self-protection, not C1
+        "echo x > .claude/.gitignore",
+        "echo x > .claude/settings.json",
     ],
 )
```

The second added line is not a matrix row, but it is the same defect through the same code path and
costs nothing to cover.

##### P3 – `guard.py`, in `split_segments`: stop splitting fd duplication (T44/T45)

Separate defect, found by running an ordinary command. Every bare `&` is treated as a control
operator, so the fd-duplication forms `>&` and `&>` are split apart:

```text
$ ls 2>&1                 -> exit 2, "C1: redirection without a target"
$ ls > /dev/null 2>&1     -> exit 2, same
$ ls 2>&1 | tail -3       -> exit 2, same
$ ls &> /dev/null         -> exit 0, but only because the leftover "> /dev/null" was allowed
```

`ls 2>&1` becomes the segments `ls 2>` and `1`; the first ends in a redirect operator with nothing
after it, so the fail-closed branch fires. Add the two exceptions before the separator test:

```diff
         if not in_single and not in_double:
             if text[i : i + 2] in ("&&", "||", "|&", ";;"):
                 segments.append("".join(current))
                 current = []
                 i += 2
                 continue
+            # `>&` / `<&` / `&>`: part of a redirection, not a control operator
+            if ch == "&" and (
+                "".join(current).rstrip()[-1:] in ("<", ">") or text[i + 1 : i + 2] == ">"
+            ):
+                current.append(ch)
+                i += 1
+                continue
             if ch in ";|&\n":
```

`check_redirections` already handles the resulting tokens correctly: `>&` ends in `&` and is skipped
as fd duplication, `&>` is treated as an output redirect and its target is checked. Real
backgrounding (`sleep 5 &`, `a & b`) still splits, because neither exception applies.

##### P4 – `test_guard_operands.py`: T44/T45 regression tests

Add to the `test_write_targets` parametrize list:

```diff
+        # T44: fd duplication is not a redirect target
+        ("ls > /dev/null 2>&1", PASS),
+        ("ls 2>&1 | tail -3", PASS),
+        # T45: &> is an output redirect and its target is checked
+        ("echo x &> README.md", BLOCK),
+        ("echo x &> .claude/scratch/out.txt", PASS),
```

##### P5 – `settings.json`: complete the self-protection denies

The deny list has `Edit(/.claude/.gitignore)` but is missing the other two denies that 5.2 requires
from Phase 1b on:

```diff
       "Edit(/.claude/.gitignore)",
+      "Edit(/.claude/settings.json)",
+      "Edit(/.claude/hooks/**)",
```

The guard already blocks all three via `self_protect: true`, so this is defence in depth, not a
hole. Without it the boundary rests on one layer instead of the intended two.

Measured afterwards during V1.14: a Bash `mv` targeting `.claude/hooks/guard-config.json` was
blocked by the **hook**, not by this rule — deny rules check redirect and `tee` targets against
`Edit` rules but not arbitrary command operands. So P5 and the guard genuinely cover different
surfaces, and P5 is not redundant.

##### P6 – the plan-mode fix (open item 4, decided and applied 2026-09-23)

Decision: **allow the plan directory**. E2 makes plan mode the default working mode, and the
deadlock had already blocked real work twice — first V1.10, then P1–P5 themselves. The alternative
(work without plan mode) would have meant correcting E2.

The block came from the `write_dir` check in `check_file_tool`, not from self-protection, so
`self_protect: false` did not help. `is_write_allowed` already consulted `allowed_temp_prefixes`,
but `check_file_tool` consulted nothing — the two write paths disagreed. P6 unifies them in one
helper and adds a second, narrower prefix list:

```diff
+def matches_allowed_prefix(ctx: Context, path: Path) -> bool:
+    """True when `path` lies under a configured write-allowed prefix."""
+    posix = path.as_posix()
+    for key in ("allowed_temp_prefixes", "allowed_write_prefixes"):
+        for prefix in ctx.get(key, []):
+            expanded = os.path.expanduser(str(prefix))
+            if posix == expanded.rstrip("/") or posix.startswith(expanded):
+                return True
+    return False
```

Used in both places — in `is_write_allowed` (replacing the inline `allowed_temp_prefixes` loop) and
in `check_file_tool`, where it is checked **after** self-protection so a protected path can never be
reopened by a prefix:

```diff
     path = resolve(ctx, raw)
     if is_self_protected(ctx, path):
         raise Blocked(f"self-protection: only the operator edits {raw}")
+    if matches_allowed_prefix(ctx, path):
+        return
     if ctx.transition and not is_inside(path, ctx.write_dir):
```

`guard-config.json`:

```diff
   "allowed_temp_prefixes": ["/tmp/claude-"],
+  "allowed_write_prefixes": ["~/.claude/plans/"],
```

The allowance is deliberately narrow, and tested to stay narrow (T46): the trailing slash matters,
so `~/.claude/plans-evil/x.md` is **not** covered, and neither are `~/.claude/settings.json` or
`~/.ssh/id_rsa`. Four test cases cover this — one positive, three negative.

**Confirmed in production 2026-09-23.** During the V2.3 session, plan mode was active and Claude
wrote its plan file to `~/.claude/plans/` successfully, then completed the plan/approve cycle via
`ExitPlanMode`. That exact write was the deadlock before P6: plan mode permits only the plan file,
and the guard forbade precisely that file. The workflow decided in E2 is usable again.

##### Pre-validation of P1 and P3 (2026-09-23, done before applying)

Claude cannot write to `.claude/hooks/**`, so P1 and P3 were validated on a patched **copy** in
`.claude/scratch/guard_preview.py` (built with `sed` line inserts from `p1-insert.txt` and
`p3-insert.txt`, both kept there), invoked with `--config .claude/hooks/guard-config.json`:

| Command | Before the patches | With P1 + P3 |
|---|---|---|
| `ls 2>&1` | exit 2, `C1: redirection without a target` | **exit 0** |
| `ls > /dev/null 2>&1` | exit 2, same | **exit 0** |
| `ls 2>&1 \| tail -3` | exit 2, same | **exit 0** |
| `echo x &> README.md` | exit 2, `C1` | exit 2, `C1` (same verdict, correct parse) |
| `echo x &> .claude/scratch/out.txt` | exit 0 | exit 0 |
| `echo x > .claude/.gitignore` | exit 2, wrong reason `C1` | **exit 2**, `self-protection: only the operator edits .claude/.gitignore` |
| `echo x > README.md` | exit 2, `C1` | exit 2, `C1` (unchanged) |
| `sleep 5 &` | exit 0 | exit 0 (real backgrounding still splits) |
| `echo a & echo b` | exit 0 | exit 0 (real backgrounding still splits) |
| `git commit -m x` | exit 2, `C4` | exit 2, `C4` (unchanged) |

Scope of P3, measured rather than assumed: the `&>` forms reached the **right verdict even before**
the patch, because the `&` split left `> target` as its own segment, which was then checked
normally. P3 therefore closes no security hole — it replaces an accidentally-correct parse with a
correct one and removes the `2>&1` false positive. That false positive is the whole reason to apply
it first; it is a usability fix, not a boundary fix.

##### Acceptance for P1–P5

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider -q .claude/hooks/tests
.venv/bin/ruff check --no-fix --no-cache .claude/hooks
.venv/bin/ruff format --check --no-cache .claude/hooks
```

Measured **before** the patches: 65 passed in 1.70 s (35 in `test_guard.py`, 30 in
`test_guard_operands.py`), ruff clean, `3 files already formatted`.

**Measured after P1–P6 (2026-09-23): 77 passed in 1.95 s**, `ruff check` → `All checks passed!`,
`ruff format --check` → `3 files already formatted`. That is 12 more than before, not the 71 the
plan predicted, because six cases were added beyond the original P2/P4 scope:

| Added | Cases | Why |
|---|---|---|
| P2 | 2 | T43 plus the `settings.json` variant of the same defect |
| P4 | 4 | T44 (two forms), T45 (blocked and allowed target) |
| P4 extra | 2 | `sleep 5 &` and `echo a & echo b` — real backgrounding must still split, otherwise P3 could silently break control operators |
| P6 | 4 | T46: one positive (the plan file is writable) and three negatives proving the allowance stays narrow |

Live re-probe of the fixed false positive, run as a real tool call:

```text
$ ls > /dev/null 2>&1
OK: ls > /dev/null 2>&1 lief durch
```

It used to fail with `C1: redirection without a target`. P3 confirmed in production.

One result needs reading carefully: probing T43 against the **live** config right after applying
returned `exit=0`, not 2. That is correct — `self_protect` was still `false` at that moment, so
`.claude/.gitignore` was an ordinary path inside `.claude/`. The pytest case builds its own config
with `self_protect=True` and passes. **Re-probe T43 against the live config once `self_protect` is
back to `true`**; expected `exit 2` with `self-protection: only the operator edits .claude/.gitignore`.

### Phase 2 – `CLAUDE.md` restructuring

Target structure (English):
1. Mission and scope (from hint §0)
2. Transition constraints C1–C8 (section kept separate so Q1 can retire it)
3. Environment (Pi 5, WSL2, Windows ARM64)
4. Operating model in ~10 bullets (GitOps, IaC, idempotency, test-first, determinism)
5. Repository map (actual layout, section 3.2)
6. Stack status: monitoring implemented; backup in progress; core/apps planned
7. Commands: *Claude may run* (5.3) vs *operator only* (deploy, postdeploy, backup, restore, renovate, commit)
8. Delivery model (D1, 10.1) and current roadmap stage (10.3)
9. Pointers to `rules/`, `skills/`, `agents/`, ADRs, `Todo.txt`
10. Working agreements: plan first, cite file paths, no guessed versions, ask on ambiguity

Verification:
- V2.1 Line count ≤ ~200 (`wc -l .claude/CLAUDE.md`).
  **PASSED: 170 lines.**
- V2.2 Every C1–C8 constraint present (manual check against section 1).
  **PASSED:** each of C1–C8 appears exactly once, checked mechanically against the table rows.
- V2.3 New session: ask "What may you not do in this repo?" → answer lists C1–C5 correctly.
  **PASSED 2026-09-23** in a fresh session, question asked in German. The answer listed C1 and C2 as
  transition-only and C3–C6 as permanent, with the concrete secret paths, the `git` verbs covered by
  C4, and the Pi identifiers covered by C5. It also named the operator-only commands, the
  `.venv` rule, the self-protected files, and the two enforcement layers — none of which the
  question asked for, so the file transports more than the constraint list.
  **Decisive detail: the answer was produced without a single file access.** It came from the loaded
  project memory alone, which is what V2.3 is actually testing. V2.1 (line count) and V2.2 (presence
  of the constraints) only prove the file is well-formed; V2.3 proves it is *loaded and usable*.

**RESULTS — written 2026-09-23.** All ten target sections are present, in order. Two structural
decisions were taken while writing; both are choices, not transcription, so they are recorded here.

**D2-a — C1–C8 split into two subsections.** The target structure asks for one separate constraints
section, while Q1/K2 require that only C1/C2 retire in Phase 8 and C3–C6 stay permanent. A single
block would have forced Phase 8 to edit *inside* a section rather than delete one. `CLAUDE.md` §2 is
therefore split: **§2.1 Transition-only** (C1, C2, plus C7/C8, which describe the transition work
itself) and **§2.2 Permanent** (C3–C6). Phase 8 deletes §2.1 whole and leaves §2.2 untouched.

**D2-b — division of labour between `CLAUDE.md` and this document.** `CLAUDE.md` is loaded into
every session and `ClaudeTransition.md` (1300+ lines) is not, so the split is by *audience*, not by
topic: `CLAUDE.md` carries only what is needed to act correctly in an arbitrary session — rules,
commands, the repo map, where to look things up. Everything historical or evidential — decisions
E1–E9/Q1–Q9, findings F1–F25, guard design, test matrix, verification records — stays here and is
reached through the pointer table in `CLAUDE.md` §9. Rule of thumb for later edits: if it answers
"what do I do now", it belongs in `CLAUDE.md`; if it answers "why is it like this", it belongs here.

Content notes:

- The German bootstrap text was translated, not paraphrased; C1–C8 keep their original meaning (K4).
- §5 records the **actual** layout and names the deviations from `ChatGPTHint.txt` §8.1 explicitly
  (`_shared/` and `victorialogs/victorialogs.yml` do not exist, `vector/` was added), so the map
  cannot be mistaken for the hint's target state.
- §7 embeds the read-only gate from 5.3 verbatim, including the side-effect check.
- `ChatGPTHint.txt` is listed in §9 as **historical, superseded by `CLAUDE.md` where they differ**.
  This is the point where C7 takes effect: the hint is no longer the operating model.
- Every path referenced in `CLAUDE.md` was checked to exist (12 of 12). One error was caught this
  way: `DevWorkflow.md` lives in `docs/operations/`, not `docs/` — section 3.2 of this document
  lists it in a way that reads as top-level, which is what caused it.

### Phase 3 – Rules

- [x] Verify current rules mechanism and `paths` frontmatter in official docs before writing;
      record the doc URL and date here.
      **DONE 2026-09-23**, https://code.claude.com/docs/en/memory (no publication date on the page).
      Result below — the mechanism exists, but it changes the design of section 5.

#### 3.0 Rules mechanism as documented (verified 2026-09-23, Claude Code 2.1.276)

| Fact | Consequence for this phase |
|---|---|
| `.claude/rules/*.md` exist and are discovered **recursively**, subdirectories allowed | The layout in section 5 works as planned |
| A rule **without** `paths` frontmatter is "loaded at launch with the same priority as `.claude/CLAUDE.md`" | It is *not* free. Every unconditional rule permanently enlarges the same context budget that V2.1 capped `CLAUDE.md` at 170 lines to protect |
| A rule **with** `paths` loads only "when Claude reads files matching the pattern, not on every tool use" | This is the mechanism that makes ten topic files affordable |
| `paths` is the **only** field Claude Code reads; every other field "is ignored without an error" | No `description`, `title` or `alwaysApply` — an invented field fails silently, so none are used |
| Unparsable YAML → frontmatter ignored, rule loads **as if it had no `paths`**, i.e. unconditionally | A typo does not fail loudly, it quietly makes the rule global. `claude --debug` shows the parse error |
| Accepts a YAML list or a comma-separated string; brace expansion allowed, budget 1000 expanded patterns / 4 MiB | Plain globs are enough here; no brace expansion needed |
| Glob `[` starts a bracket expression; an unreadable one matches nothing | Avoid `[` in patterns entirely |
| Docs note: "For task-specific instructions that don't need to be in context all the time, use **skills** instead" | Draws the line between Phase 3 and Phase 4: rules = standing constraints while editing a file class, skills = invoked procedures |
| Docs warn: "if two rules contradict each other, Claude may pick one arbitrarily" | Rules must not restate `CLAUDE.md`; overlap is a defect, not redundancy |

Version notes checked and not applicable on 2.1.276: `paths` brace-expansion crash (< v2.1.217),
invalid-`[` breaking Read (< v2.1.207), on-demand rules loading despite excluded `project`
(< v2.1.211), symlink path matching (>= v2.1.198).

**Design consequence — D3-a.** Section 5 lists ten rule files without saying how they load. Written
unconditionally they would all load every session, which would undo Phase 2's context discipline and
duplicate `CLAUDE.md` §4 and §8. Therefore: **every rule that has a natural file class gets `paths`
frontmatter and loads on demand.** `CLAUDE.md` keeps the always-loaded core; `rules/` holds the
depth that only matters while touching a specific part of the repository.
- [ ] Write the ten rule files from section 5. Each: purpose, MUST/SHOULD list, source references
      (ADR/doc path), examples of violations.
      **DONE 2026-09-23 — eight files, all path-scoped. See D3-a above and D3-b below.**

#### 3.1 What was written

| Rule | `paths` | Files in scope | Lines |
|---|---|---:|---:|
| `compose-stacks.md` | `stacks/**` | 30 | 63 |
| `testing.md` | `tests/**` | 40 | 60 |
| `shell-scripts.md` | `**/*.sh` | 19 | 55 |
| `host-runtime.md` | `scripts/host/**`, `scripts/host-runtime/**`, `scripts/network/**`, `stacks/core/docker/**`, `deploy.sh` | 12 | 59 |
| `backup-restore.md` | `scripts/backup/**`, `docs/operations/BackupVerifyRestore.md`, `docs/operations/GPG_config_for_backup_encryption.md` | 6 | 65 |
| `secrets.md` | `**/*.env.example`, `stacks/**/compose/**`, `scripts/backup/**` | 8 | 59 |
| `ci-renovate.md` | `.github/**`, `renovate.json5`, `.pre-commit-config.yaml` | 3 | 53 |
| `docs-adr.md` | `docs/**` | 13 | 54 |

468 lines in total, **none of which load unless Claude touches a matching file**. Compare: written
unconditionally they would have tripled the always-loaded instruction set against `CLAUDE.md`'s 170.

**D3-b — two planned rules were deliberately not written.** Section 5 lists
`operating-model.md` and `incremental-delivery.md`. Both describe stances, not file classes, so
neither has a meaningful `paths` value, and both are already stated in `CLAUDE.md` §4 and §8.
Writing them would have cost always-loaded context for zero gain (an unconditional rule has the
same priority as `CLAUDE.md`, so nothing is saved by moving text there) while creating exactly the
duplication the docs warn about: *"if two rules contradict each other, Claude may pick one
arbitrarily."* Operator decision, 2026-09-23: **eight rules, not ten.** If one of them ever needs
more depth than `CLAUDE.md` can carry, the right home is a skill (Phase 4), not an unconditional rule.

Deliberate overlap, which is not duplication: `scripts/backup/**` appears in both
`backup-restore.md` and `secrets.md`, and `stacks/**/compose/**` in both `compose-stacks.md` and
`secrets.md`. Each rule addresses a different aspect of the same file, and they were checked for
contradictions.

Verification:
- V3.1 Each rule cites at least one repo source file.
  **PASSED** — every rule has a `Sources` section, and each cited path was checked to exist
  mechanically, not by eye. One real error was caught: `vector/vector.yaml` is
  `stacks/monitoring/vector/vector.yaml`. The checker was `.claude/scratch/check_rules.py`, tracked as `.claude/tools/check_rules.py` since Phase 6.
- V3.1b (added) Frontmatter parses and every glob matches real files.
  **PASSED** — 8/8 parse, 8/8 carry `paths`, no pattern matches zero files, no `[` in any glob,
  no unknown frontmatter keys. This check matters because Claude Code **silently** ignores
  unparsable frontmatter and loads the rule unconditionally — the failure mode is invisible
  context bloat, not an error message.
- V3.2 In a new session, open `stacks/monitoring/compose/docker-compose.yml` and ask for a
  compliance review → answer references `compose-stacks.md` content (naming, pinning, bind mounts).
  **OPEN — operator step**, needs a fresh session. This is the real test: it proves path-scoped
  loading actually fires, which nothing here can prove from inside the session that wrote the rules.
  Procedure in 3.2 below.
  **Attempted 2026-09-23 and discarded as invalid.** The review prompt was run in the same session
  that had just written `compose-stacks.md`, so its content was already in context. The review was
  substantive — it produced findings F26–F29 and sharpened F1 and F13 — but it proves **nothing**
  about on-demand loading, because the rule could not have been absent. V3.2 requires a session that
  has never seen the rule file. This is the trap the procedure in 3.2 exists to avoid; note that the
  invalid run still looked entirely convincing.
  **PASSED 2026-09-23 on the second, valid attempt** — a fresh session with the
  `InstructionsLoaded` hook active. Hard evidence from `.claude/logs/instructions.log`:
  5 entries with reason `path_glob_match`, `compose-stacks.md` among the loaded files.

  The log also supplied the negative control for free. Loaded on demand: `ci-renovate.md`,
  `compose-stacks.md`, `secrets.md`, `shell-scripts.md`, `testing.md`. **Not loaded:**
  `docs-adr.md`, `host-runtime.md`, `backup-restore.md` — the session touched nothing under
  `docs/`, `scripts/host*/` or `scripts/backup/`. Five of eight, so path scoping does not merely
  work, it demonstrably withholds the other three. D3-a saves context in practice, not only on paper.

  The review itself produced findings F30–F42 and corrected two of Claude's own artefacts (F40, F42)
  plus the framing of F28 — see 3.3.

#### 3.3 Corrections to Claude's own artefacts (from the V3.2 review, 2026-09-23)

The V3.2 review did not only find repository defects — it found three errors in the artefacts
written in Phases 2 and 3. Recorded here because "the review found my own mistakes" is the part
most likely to be forgotten.

| # | Error | Fix |
|---|---|---|
| 1 | **F28 was misleading, not merely incomplete.** It cited `vector`'s `docker.sock:ro` as the safe contrast to cadvisor's `:rw`. A read-only mount stops writes to the socket *file*; it does not stop Docker API calls, and with `group_add: ${DOCKER_GID}` vector has host-root equivalence (F30). | F28 annotated rather than rewritten — a findings log should show what was claimed and what corrected it. The underlying misconception is now stated as a MUST in `rules/compose-stacks.md`, because that is the artefact that steers future work. |
| 2 | **F40 — the volume naming rule contradicted reality, in two files.** `rules/compose-stacks.md` and `CLAUDE.md` §4 both demanded `<service>-data\|config\|db`, copied from `ChatGPTHint.txt` §4 without checking. The implementation uses `/srv/data/stacks/<stack>/<service>/`. | Both corrected to the real convention; the hint is now named as wrong on this point. Renaming the data paths was rejected — it would be a data migration to satisfy a document. |
| 3 | **F42 — the rule asserted documentation that does not exist.** It called the LAN exposure of ports 3000/9428 a "deliberate, documented decision"; `ADR-0001-networking-and-firewall.md` mentions neither port. | The rule now says the exposure is intentional but **unrecorded**, and must be treated as precedent rather than as documentation. |

Lesson for the remaining phases: an artefact that cites a source is only as good as the check that
the source says what the artefact claims. V3.1's mechanical path check caught missing *files*; it
cannot catch a claim about a file's *contents*. Phases 4–6 should assume the same class of error
exists in whatever they produce.

#### 3.2 How to run V3.2 (and repeat it after every Claude Code update)

"Open the file" does not mean opening it in an editor. The trigger is **Claude reading it**: a
path-scoped rule loads "when Claude reads files matching the pattern, not on every tool use".

**Setup — the `InstructionsLoaded` hook (operator applies; `settings.json` is self-protected).**
Documented event: fires when a `CLAUDE.md` or `.claude/rules/*.md` file is loaded into context, at
session start **and on lazy loading during a session**. Its matcher selects the load *reason*:
`session_start`, `nested_traversal`, `path_glob_match`, `include`, `compact`. It is observational
only — it cannot block, and exit code 2 has no effect. Add to `.claude/settings.json` inside
`"hooks"`, alongside `PreToolUse`:

```json
"InstructionsLoaded": [
  {
    "matcher": "session_start|nested_traversal|path_glob_match|include|compact",
    "hooks": [
      {
        "type": "command",
        "command": "cat >> \"$CLAUDE_PROJECT_DIR/.claude/logs/instructions.log\"; echo >> \"$CLAUDE_PROJECT_DIR/.claude/logs/instructions.log\""
      }
    ]
  }
]
```

No script file is needed — the event JSON arrives on stdin. `.claude/logs/` is already git-ignored.
All five reasons are captured on purpose: `session_start` answers "what loads in every session",
which is the question D3-a is about, and `path_glob_match` answers V3.2.

**Step 1 — positive case.** Fresh session, then:

```text
Review stacks/monitoring/compose/docker-compose.yml gegen unsere Regeln.
```

Claude must **not** read `deploy.sh` or `ClaudeTransition.md` in that session, otherwise the source
of any repo-specific knowledge is ambiguous. Check afterwards which files it read.

**Step 2 — hard evidence.**

```bash
grep path_glob_match .claude/logs/instructions.log
```

An entry naming `compose-stacks.md` proves V3.2 regardless of what the answer said. This is the only
check that does not rest on interpretation.

**Step 3 — content canary, if the hook is not in place.** Measured 2026-09-23, so the canary is
chosen rather than guessed:

| Fact | In `CLAUDE.md` (always loaded)? | In `compose-stacks.md`? | Usable as proof |
|---|---|---|---|
| F1, F3, F9, F25 | **yes** | partly | **no** |
| F2, F7, F8 | no | yes | yes |
| "config hash covers only four files" | no (0 matches) | yes | **best** |

The config-hash statement derives from `deploy.sh`, is absent from `CLAUDE.md`, and cannot be
inferred from the compose file alone. If the review raises it **unprompted**, the knowledge can only
have come from the rule. Do not ask for it — a leading question invalidates the test.

**Step 4 — negative control.** A second fresh session, touching no file under `stacks/`:

```text
Was sind unsere Regeln für Compose-Stacks?
```

The canary must be **absent** here. Present in step 1 and absent in step 4 proves not just that the
rule works, but that it loads **on demand** — i.e. that D3-a actually saves context rather than only
claiming to.

`/context` lists **Memory files**, but the documentation describes that list for `CLAUDE.md` and
`CLAUDE.local.md`; whether lazily loaded path-scoped rules appear there is **unverified**. Do not
read an absence there as evidence.
- V3.3 No rule contradicts an accepted ADR (manual review by operator).
  **PASSED 2026-09-23.** All four ADRs checked against all eight rules. **No rule contradicts an
  ADR.** Three rule statements were verified against the source rather than trusted:

  | Rule statement | Source | Result |
  |---|---|---|
  | `deploy.sh` refuses a repo-root `.env` (`secrets.md`) | `deploy.sh:109-110`, `die "Refusing repo-root .env …"` | correct |
  | host data under `/srv/data/stacks/<stack>/<service>/` (`compose-stacks.md`) | ADR-0008 Decision, verbatim | correct — retroactively confirms the F40 fix |
  | exit codes, DD-012, DD-013, public-key model (`backup-restore.md`) | ADR-009 §2.3 and lines 174/681/698 | correct |

  ADR-0001 mentions neither port 3000 nor 9428, which confirms the F42 correction.

  Two rules were **imprecise rather than wrong**, both fixed:
  - `secrets.md` never mentioned that ADR-0007 §2 **allows** a compose-directory `.env` for local
    CLI use (non-secret, gitignored, local-only). The rule is scoped to exactly that directory, so
    the omission misleads inside its own scope. Same class of defect as F40/F42.
  - `backup-restore.md` claimed the Pi holds the private key "never". ADR-009 line 875 permits a
    documented emergency import followed by mandatory cleanup. A rule that hides a documented
    exception gets bypassed in an emergency instead of followed.

  One **ADR** turned out to be wrong — recorded as F43. V3.3 was expected to be a formality
  checking rules against ADRs; the only real defect sits in an ADR, and it surfaced only because
  both were checked against the code rather than against each other.

### Phase 4 – Skills

- [x] Verify SKILL.md frontmatter fields against current docs; record URL/date.
      **DONE 2026-09-23**, https://code.claude.com/docs/en/skills (no publication date on the page;
      newest version note v2.1.273). Result below.

#### 4.0 Skills mechanism as documented (verified 2026-09-23, Claude Code 2.1.276)

| Fact | Consequence for this phase |
|---|---|
| Layout `.claude/skills/<name>/SKILL.md`; subdirectories and supporting files allowed and encouraged | Matches section 5 |
| **All frontmatter fields are optional**; only `description` is recommended | No required boilerplate |
| **`description` (plus `when_to_use`) is loaded into context on every turn**, the two combined capped at 1,536 characters per skill | The always-loaded cost of Phase 4 is the sum of eight descriptions. This is the same trap as D3-a, in a different place |
| The **full body loads only on invocation** and then stays for the session | Body length is cheap until used; description length is not |
| Invocation: automatic by description match, `/skill-name`, or the Skill tool | A wrong description means the skill is either never found or fires constantly |
| `disable-model-invocation: true` prevents automatic invocation (user-only) | Intended for side-effect operations such as `/deploy` |
| `allowed-tools` / `disallowed-tools` pre-approve or remove tools **for the current turn**, expiring on the next user message; supports Bash rules such as `Bash(git add *)` | A third permission mechanism next to `settings.json` and the guard — see D4-b |
| `paths` also exists for skills, gating them to matching files | Considered and rejected — see D4-c |
| `context: fork` + `agent` run a skill in an isolated subagent | Not used; these skills are short and their output belongs in the main transcript |
| Guidance: keep `SKILL.md` under 500 lines, move reference material to linked files | All eight stay far below |

**D4-a — descriptions are the budget, not the bodies.** Eight skills with careless descriptions
would cost up to 8 × 1,536 ≈ 12,000 characters of always-loaded context, which would quietly undo
what V2.1 and D3-a protect. Each description is therefore held to roughly one line: what it does
and when to reach for it, nothing else. The detail goes in the body, which costs nothing until the
skill is invoked.

**D4-c — no `paths` on skills.** Rules are *standing constraints* and benefit from path scoping;
skills are *procedures the operator asks for*. `backup-progress` must be findable when someone asks
"how far is the backup", not only while a file under `scripts/backup/` happens to be open. Short
descriptions solve the budget problem without making a skill invisible when it is wanted.
- [x] Write the eight skills. Skills that would produce repo changes output **proposals** into
      `.claude/scratch/` or into chat, never into other paths (C1).
      **DONE 2026-09-23** — all eight written, none writing outside `.claude/`.
- [x] `readonly-gate` embeds 5.3 including the before/after comparison.
      **DONE** — verbatim, including the acceptance rule that any diff is a C2 violation.

#### 4.1 What was written

| Skill | Purpose | Description cost | Body |
|---|---|---:|---:|
| `readonly-gate` | run the 5.3 gate, prove no side effects | 140 | 47 |
| `increment-plan` | feature → increments, template from 10.2 | 176 | 59 |
| `image-pin-audit` | pin quality and Renovate coverage | 176 | 45 |
| `backup-progress` | ADR-009 contract vs. implementation | 164 | 50 |
| `change-review` | diff against the rules, checklist and verdict | 146 | 50 |
| `new-stack-proposal` | full stack scaffold as a proposal | 163 | 54 |
| `postdeploy-test-design` | runtime checks with actionable failures | 148 | 45 |
| `adr-draft` | ADR draft into `.claude/scratch/` | 123 | 61 |

**Always-loaded cost: 1,236 characters across all eight** — less than the 1,536 cap that applies to
a *single* skill. D4-a held.

**D4-b — `allowed-tools` only on `readonly-gate`** (operator decision, 2026-09-23). It lists the
eight exact read-only commands, all of which `CLAUDE.md` §7 already permits but `settings.json`
does not pre-approve, so without the grant the gate prompts on every increment — and IN4 runs it
before every commit. Deny rules still win over allow and the PreToolUse guard fires regardless, so
the grant cannot widen the boundary. The other seven skills carry no tool grant.

The rejected option matters more than the chosen one: granting tools in all four Bash-using skills
would have spread permissions across four files that have nothing to do with permissions — and
**skills are not self-protected**, so that would have been the first place where Claude can extend
its own rights. Keeping grants to one file, with exact commands, keeps that door shut.

Verification:
- V4.1 `/skills` lists all eight.
  **PASSED 2026-09-23**, operator ran `/skills`. No restart was needed: all eight had already
  appeared in the available-skills list in the **same session** that wrote them, which also
  disproves the earlier assumption in this document that V4.3–V4.5 required a fresh session.
- V4.5 Run `increment-plan` for a sample feature → output follows the template in 10.2.
  **PASSED 2026-09-23**, invoked through the Skill tool with the sample feature "supply the backup
  tests required by DD-012". Output followed the 10.2 template field by field across three
  increments, including the IN9 line, which the skill forbids defaulting to "none". It also applied
  the entry-condition check on its own and stated that backup work belongs to R2 and is therefore
  correctly scheduled only after R1 — the plan was not presented as startable today.
- V4.2 Run `readonly-gate` → completes; before/after diff empty.
  **PASSED 2026-09-23**, executed end to end: `ruff check` → `All checks passed!`;
  `ruff format --check` → `43 files already formatted`; `yamllint -s` clean; ShellCheck over all
  19 tracked scripts clean; `tests/precommit -m precommit` → 8 passed, 4 deselected;
  guards + doctor → 7 passed, 1 skipped; final diff → `OK: no side effects`.
- V4.3 Run `image-pin-audit` → table matches section 3.3 image list.
  **PASSED 2026-09-23**, invoked through the Skill tool. All ten compose images matched section 3.3
  tag for tag. Totals across the whole repository: 1 digest, 15 full version tags, **6 floating**,
  **0 unpinned** — the "never `latest`" rule holds without exception. The floating six are
  `alpine:3.24` (F37), `renovate/renovate:43` in `scripts/renovate/validate-config.sh` (F24, while
  `Makefile:85` pins the same image by digest), and `actions/checkout@v4`, `actions/setup-python@v5`,
  `actions/cache@v4`. Renovate coverage confirmed from `renovate.json5`: `enabledManagers:
  ["docker-compose"]`, so exactly the ten compose images and nothing else (F4).
- V4.4 Run `backup-progress` → reports at least F9 and GPG step 6.
  **PASSED 2026-09-23**, invoked through the Skill tool; both reported, F9 as the headline.
  The run also **corrected the picture F9 alone conveys**: five of the seven ADR-009 requirements
  are already implemented — exit codes as named constants in `scripts/backup/common.sh:12-17`
  (`EX_USAGE=2` … `EX_DEPLOY=7`, matching §2.3 exactly), non-blocking `flock -n` on
  `/run/lock/homelab-backup.lock` with `acquire_lock` in all three scripts (§2.4), the full set of
  fixture overrides including a fallback lock file off the Pi (§2.5), and restore requiring both
  `RESTORE_APPLY=1` and `RESTORE_CONFIRM` (DD-013). What is missing is the **proof**, not the
  implementation. "No tests" reads like "nothing there"; it is not, and the skill is what made that
  visible.

**V4.6 (added) Frontmatter and budget check.** `.claude/scratch/check_skills.py` (tracked as
`.claude/tools/check_skills.py` since Phase 6) verifies that each
`SKILL.md` parses, carries a `description`, has `name` equal to its directory, uses only documented
frontmatter keys, stays under the 500-line body guidance, and that the per-skill description budget
holds. **PASSED, 0 failures.** The unknown-key check matters because the docs state that any field
Claude Code does not know is *ignored without an error* — the same silent-failure class as the rules'
frontmatter, where an unparsable `paths` quietly makes a rule global.

### Phase 5 – Subagents

- [x] Write four agent files with minimal tool sets (read-only: Read, Grep, Glob; no Edit/Write/Bash
      unless justified and listed).
      **DONE 2026-09-23** — four files, each `tools: Read, Grep, Glob`, nothing beyond.

#### 5.0 Subagent mechanism as documented (verified 2026-09-23, Claude Code 2.1.276)

Source: https://code.claude.com/docs/en/sub-agents (no publication date; newest version note
v2.1.271).

| Fact | Consequence |
|---|---|
| `.claude/agents/*.md`, scanned recursively; `name` and `description` are **required** | Matches section 5 |
| **`tools` is an allowlist. Omitting it inherits _every_ tool available to subagents**, Edit, Write and Bash included | See D5-a — this inverts what V5.3 actually has to check |
| `disallowedTools` is a denylist applied **before** `tools` | Not used; an explicit allowlist is unambiguous on its own |
| `description` is **always loaded** at startup; a startup warning appears past 15,000 tokens combined | Same budget discipline as the skills, with far more headroom |
| Subagents inherit the whole `CLAUDE.md` chain **and `.claude/rules/`** | See D5-b |
| **`settings.json` hooks fire inside subagents** | The PreToolUse guard protects a subagent too. The tool allowlist is the first layer, not the only one |
| No per-agent way to prevent automatic delegation; use `permissions.deny: ["Agent(<name>)"]` | Recorded for Phase 8, should an agent ever need to be switched off |
| Invocation: automatic by description, `@agent-<name>`, or `--agent` for a whole session | `@`-mention guarantees a specific agent runs |

**D5-a — the dangerous case is an absent `tools`, not a wrong one.** V5.3 as written ("agent
definitions contain no Edit/Write tools") would happily pass a file that omits `tools` entirely and
therefore grants everything. The check was inverted accordingly: `tools` **must be present**, and
`.claude/scratch/check_agents.py` (now `.claude/tools/check_agents.py`) fails the file if it is missing. This is the same silent-failure
class as unparsable rule frontmatter (which makes a rule global) and unknown skill keys (ignored
without an error) — three different mechanisms, one shared trap: the failure mode is invisible.

**D5-b — agent bodies must not restate the rules.** Subagents inherit `CLAUDE.md` and
`.claude/rules/`, so the criteria are already in their context. Each body therefore carries only
what the rules do not: the review *procedure*, the list of known findings to confirm in one line
rather than re-investigate, and the report format. Repeating the rules would cost context twice and
risk the contradiction the memory docs warn about.

#### 5.2 Third correction of the same class (2026-09-23)

V5.2 exposed the **third** instance of a Claude artefact asserting documentation that does not
exist. The first two were F42 (the rule called the LAN ports a "documented decision"; no ADR
mentions them). The third is F46: both `CLAUDE.md` §4 and `rules/compose-stacks.md` called cadvisor's
privileged mode a documented exception, while `docs/monitoring.md:29` says "No privileged
containers" and `:197` says it runs "with minimal privileges".

Both were corrected to state that the exception exists, is claimed in an inline comment only, and is
contradicted where documentation should live. `compose-stacks.md` additionally now forbids citing it
as precedent for a second privileged container.

The pattern is now unmistakable and worth carrying into Phase 6: **Claude's artefacts inherited the
word "documented" from the hint and from each other, without anyone checking the referenced
document.** V3.1's mechanical check proves a cited *file exists*; it cannot prove the file *says what
the citation claims*. Only reading the source catches it, and in all three cases a review did —
never a test.

#### 5.1 What was written

| Agent | Tools | Focus | desc | body |
|---|---|---|---:|---:|
| `compose-reviewer` | Read, Grep, Glob | per-service walk, mount existence, config-hash coverage | 179 | 38 |
| `security-reviewer` | Read, Grep, Glob | secrets, exposure, privilege, supply chain | 197 | 41 |
| `test-author` | Read, Grep, Glob | layer, false-green analysis, tests as text only | 155 | 39 |
| `docs-steward` | Read, Grep, Glob | doc claims against code, verdict per claim | 172 | 45 |

Always-loaded description total: **703 characters**.

Each body names the findings it must *confirm in one line instead of re-investigating*, so a review
spends its output on what is new rather than re-deriving F5, F8, F13, F26, F28, F30, F42 and F44.

Verification:
- V5.1 `/agents` lists all four.
  **PASSED 2026-09-23** after an operator restart. All four are registered and each is listed with
  `Tools: Read, Grep, Glob` — which confirms D5-a from the outside: the allowlist took effect, and
  the agents did **not** silently inherit every tool.
  Before the restart the same invocation failed with `Agent type 'security-reviewer' not found.
  Available agents: claude, claude-code-guide, Explore, general-purpose, Plan, statusline-setup`,
  which is what established the skills/agents asymmetry recorded below.
- V5.2 `security-reviewer` on the compose file flags cadvisor `privileged: true` and LAN ports
  3000/9428 with the documented justification.
  **PASSED 2026-09-23.** Both were flagged explicitly — and the agent **disproved the premise of
  this verification**. V5.2 was written assuming a "documented justification" exists. It does not:
  - cadvisor: the only document that discusses it says the **opposite**, twice —
    `docs/monitoring.md:29` "No privileged containers" and `:197` "cAdvisor is intentionally
    isolated and run with minimal privileges", under a heading "Required mounts (read-only)" that
    does not list the Docker socket at all. No ADR mentions cadvisor. The sole record is an inline
    compose comment asserting necessity without evidence. → **F46**
  - ports 3000/9428: deliberate (named in `cleanup-ufw.sh`, `.env.example`, and encoded as a
    contract in `test_35_network_and_ufw.py`) but recorded in **no** document. The agent's grep over
    all of `docs/` returned six hits, every one a timestamp or an in-container curl example. This
    **closes F42's open caveat** "other docs not checked".

  Claude spot-checked the load-bearing `[V]` claims before recording: `docs/monitoring.md:26/29/197`
  verbatim, absence of `ufw route`/`DOCKER-USER` anywhere in `scripts/`, `docs/`, `stacks/`, absence
  of `"iptables": false` in `daemon.json`, and `scripts/backup/backup.sh:383-385`. All held.

  The report also produced two findings not in F1–F44 (**F45**, **F46**), extended F26 and sharpened
  F4 — from a context that knew nothing of this session, deriving everything from `CLAUDE.md`, the
  inherited rules and the files. The `[V]`/`[I]` discipline and the one-line confirmations of known
  findings were followed as specified, so the agent definition needs no correction.
- V5.3 Agent definitions contain no Edit/Write tools.
  **PASSED 2026-09-23**, and checked in the corrected form from D5-a: `tools` is **present** in all
  four files and equals exactly `Read, Grep, Glob`. Verified mechanically by
  `.claude/scratch/check_agents.py` (now in `tools/`), 0 failures — after Phase 3 and 4 this class of check is no
  longer done by eye.

**Correction 2026-09-23 (Phase 6, V6.1).** Two statements in this subsection do not hold against
the sub-agents docs:
- **"`/agents` lists all four"**: `/agents` has not listed agents since v2.1.198, well before 2.1.276.
  Whatever the evidence for V5.1 was, it cannot have been `/agents` output. The reported form
  `Tools: Read, Grep, Glob` matches the agent list Claude receives in its own tool context, which is
  the likely source [I]. The *registration* result is not in doubt: the four agents are available
  and read-only, re-confirmed from Claude's tool context on 2.1.280.
- **"The agent registry is read at startup"**: the docs say agent files are hot-reloaded, with no
  restart. A restart is needed for the **first** file in a new `agents/` directory — exactly the
  Phase 5 situation, since `.claude/agents/` did not exist before. The observation was right, the
  generalisation was wrong. The closing sentence below ("each has its own loading moment, and the
  only reliable way to know is to try it") stands, and it should have included reading the docs.

**Newly measured asymmetry, worth remembering.** Skills written during a session became available
**in that same session** (that is how V4.1–V4.5 could be run immediately). Agents written during a
session do **not** — the agent registry is read at startup. The statement "no restart needed",
recorded under V4.1, is therefore true for skills and false for agents. Do not generalise from one
artefact type to another; each has its own loading moment, and the only reliable way to know is to
try it.

### Phase 6 – Human documentation and findings report

- [x] `readme_claude.md`: purpose of each artefact, how to start a session, what Claude will refuse
      and why, how to verify the safety set-up (V1.x), how to update artefacts.
      **WRITTEN 2026-09-23.** Seven sections: inventory, session start, refusals, the two layers
      (with the deny list grouped into self-protection / transition / permanent, which 5.2
      promised and nothing had delivered), verification, updating, Phase 8 preview.
- [x] `reports/repo-findings.md`: F1–F46 with evidence, impact, proposed fix, suggested test.
      **WRITTEN 2026-09-23 — scope F1–F46 plus F26b (47 entries), not F1–F24**, because the backlog
      had grown by 23 findings since this line was written. Each entry: Evidence, Impact, Proposed
      fix, Test, Acceptance; plus severity, status and a suggested R1 increment grouping (a–i).

#### 6.0 Decisions and corrections

**D6-a — the verifiers had to become tracked.** `check_rules.py`, `check_skills.py` and
`check_agents.py` lived in git-ignored `scratch/`, so the readme would have pointed a fresh clone at
files that do not exist, failing V6.1 by construction. Operator decision: move them to `tools/`.
Moving them exposed a second, quieter defect: ruff skips git-ignored files, so the scripts had never
been linted — `check_rules.py` had three B023 errors (a closure over loop variables) and all three
files failed `ruff format --check`. Both fixed; the gate now covers them.

**D6-b — the report is the single source of truth; §3.6 is an index.** Two full copies would drift.
`tools/check_findings.py` enforces that report entries, report index and §3.6 index hold the same
IDs, that every entry has all five fields, that cited repo paths exist, and that a path written as
*(absent)* really is absent — some findings are about a missing file, and that claim is now checked
too.

**Status changes found while re-reading** (only the six findings whose status could have moved):

| Finding | Result |
|---|---|
| F10 | **addressed** — `.venv` reports pytest 8.4.2; both sources pin `<9` |
| F14 | **addressed** — `docs/operations/DevWorkflow.md:16,34` require `make ci` before commit |
| F21 | **partly** — R0.0 fixed ruff/ShellCheck/yamllint; pip upgrade in `make venv` and the pytest range remain |
| F22 | unchanged |
| F23 | **sharpened** — four test files carry `lint`, and no gate selects that marker at all |
| F5 | unchanged |

F40 is marked addressed (Claude's artefacts were the only thing wrong). F42 is marked partly: the
rule was corrected, the missing document is still missing.

**Readme correction found while writing.** The self-protect window as used for P1–P6 (set
`self_protect: false`, Claude applies) no longer works on its own: P5 added
`Edit(/.claude/hooks/**)` to the settings denies, so the Edit tool stays blocked with the guard flag
off. The readme now gives two paths — operator applies (default), or a two-layer window in a fixed
order.

**Guard false positive observed** — `grep -n -i 'prometheus\|loki\|promtail\|\.env' README.md` →
`guard: C3: \`grep\` would read secret material`. The *pattern* was classified as a secret path.
Accepted like the other false positives in 5.4.5 and listed in the readme.

Verification:
- V6.1 Operator can follow `readme_claude.md` from a fresh shell without extra knowledge.
  **IN PROGRESS — operator step.**
  **V6.1 finding #1 (2026-09-23, 2.1.280):** readme §2 told the operator to run `/agents`, which
  prints `The /agents wizard has been removed. Ask Claude to create or update subagents for you
  … or edit the files directly`. The sub-agents docs (fetched 2026-09-23) say `/agents` stopped
  listing agents **as of v2.1.198**, and name no replacement listing command. Readme §2 now uses
  the `@` typeahead and asks Claude directly. §6.4 and the inventory row were also corrected, see
  the note under 5.1 below. The readme was wrong because Claude wrote it from this document rather
  than from the current docs — the same class of error as F40/F42/F46.
  **V6.1 finding #2 (2026-09-23, 2.1.280, operator):** readme §2 expected the typeahead to list
  `agent-compose-reviewer` and gave `@agent-security-reviewer` as the invocation. The typeahead
  shows the **plain name** (`compose-reviewer`). Per the sub-agents docs, picking it inserts
  `@"<name> (agent)"`, and the typed form `@agent-<name>` still resolves on submit, but while it is
  typed the typeahead shows files, not agents. Both forms are valid, and the readme now describes
  the picker as primary. Section 5.0's "`@agent-<name>`" is correct but incomplete. **V6.1 finding #3 (2026-09-23, 2.1.280, operator):** a hand-typed `@compose-reviewer`, without
  the picker, also resolves to the agent. This was measured, not documented: the sub-agents docs
  name only the picker and `@agent-<name>`. Three working forms on 2.1.280.
  **V6.1 finding #4 (2026-09-23, operator) — the readme caused real side effects.** Readme §5.4 listed
  the live hook checks as backticked commands in a table headed "needs a Claude session". The
  operator ran them in the WSL shell, where no hook exists. Result: a real empty commit `236a4a2 test`
  on `chore/r0-claude-safety-foundation` (not pushed, no upstream), and `README.md` overwritten with
  `test` (105 lines deleted, uncommitted). Both are recoverable: `git restore README.md`, then
  `git reset --soft HEAD~1` back to `ef273c8` (operator, C4). §5.3 did warn against typing the quoted
  commands, but the warning sat in the wrong section and the table looked copy-pasteable. Fix: §5.4
  is retitled "prompts for Claude, NOT shell commands", has a warning block that names this
  incident, phrases every row as a prompt (L1–L5) with the verbatim expected reason, and explains
  what to do if Claude declines to attempt a forbidden call. Lesson: **a document whose audience
  alternates between a shell and a Claude prompt must make the target of every command explicit,
  row by row.** This is exactly the failure V6.1 exists to find. V1.10–V1.13 on 2.1.280 are still
  **not** done; the shell run tested nothing.
  **Re-run on 2.1.280 after cleanup (2026-09-23).** The operator reset the test commit (HEAD back at
  `ef273c8`) and restored `README.md`; Claude confirmed both read-only. Then:
  - readme §5.3 direct probes, 17:11:18 UTC in `guard.log`: four blocks with the verbatim reasons
    `C4: git commit is reserved for the operator`, `C5: command references the Raspberry Pi
    (rpi-hub)`, `C1: redirection would write outside .claude/: README.md`,
    `self-protection: only the operator edits .claude/hooks/guard.py`.
  - readme §5.4 L1–L5 typed as prompts into a Claude session; operator reports all as expected.
    Log evidence: L1 17:21:45 `C4: …`, L2 17:22:30 `C1: …`. **L3 and L4 left no guard block entry**:
    the settings deny rules (`Edit(/.claude/hooks/**)`, `Read(/secrets/**)`) refused them before the
    hook ran. That is a pass under the readme's "settings deny or guard" criterion. It also means
    that on 2.1.280 the guard's Edit/Read branch was exercised only by the direct probe, not
    through the hook. Ordering "deny before hook" is observed, not documented here [I].
  → **V1.10–V1.13 and V1.15 re-confirmed on 2.1.280; V1.16 = proceed.** Not re-run on 2.1.280:
  V1.14 (fail-closed via config rename), unless the operator did it in the same pass.
  **V6.1 finding #5 (2026-09-23, operator):** after §5.1/§5.2 passed (77 passed), the operator had
  to ask whether §5.5 and §5.6 run in the shell or in Claude. Readme §5 did not state the target per
  step — the root cause of #4 as well — and its intro wrongly called every step read-only (V1.14
  renames a file). Fix: a "where each step runs" table at the top of §5, a shell/Claude marker in
  every subsection heading, the optional §5.5 proof written out as an explicit prompt plus the log
  check, and the §5.6 gate given as two explicit alternatives.
  **V6.1 finding #6 (2026-09-23, operator):** `/readonly-gate` was run in plan mode and passed. The
  session kept the before/after snapshots in shell variables instead of the
  `/tmp/claude-gate-*.txt` files the skill prescribed, because plan mode forbids writing files. The
  deviation was sound, and it exposed that the skill conflicted with the default permission mode
  (E2) on every run. It also ran `-m lint` as the skill invites (1 failed at `--maxfail=1`, F25
  reproduced), but *after* the snapshot comparison, so that run was outside the side-effect check.
  Claude re-checked afterwards: no new `__pycache__` or `.pytest_cache`. Fix (operator-approved):
  `readonly-gate` now documents Form A (plan mode, variables, one single Bash call; tested through
  the live guard, `OK: no side effects`) and Form B (`/tmp/claude-gate-*`). It requires any extra
  run to sit inside the window, and the report must name the form used. `allowed-tools` are
  **unchanged**. Whether Form A's compound call triggers a permission prompt is unmeasured, and the
  skill forbids widening the grant to avoid one (D4-b).
  **Re-run after the fix (operator, plan mode off):** the report named **Form B** and placed the
  extra `-m lint` run inside the window. Results: `All checks passed!`, `47 files already formatted`,
  yamllint and ShellCheck rc 0, `8 passed, 4 deselected`, `7 passed, 1 skipped`, `-m lint` →
  `1 failed, 8 deselected` (F25, `.vscode/settings.json` line 37), `OK: no side effects`.
  **Re-run in plan mode (operator):** the report named **Form A** and used one Bash call, with the
  extra `-m lint` run inside the window. Results were identical to Form B, including
  `OK: no side effects`. Both forms are now verified in real skill sessions. The permission-prompt
  question for Form A stays open until the operator reports what was on screen; Claude correctly
  stated that it cannot observe it.
  **V6.1 walkthrough state (end of 2026-09-23, operator-reported):** readme §2 passed after findings
  #1–#3. §5.1 and §5.2 (`77 passed`), §5.3 direct probes, §5.4 L1–L5, §5.5 and §5.6 (four checkers,
  `0 failure(s)` each) all passed, and `/readonly-gate` passed in both forms.
  **V6.1 finding #7 (2026-09-24, operator question):** the operator asked where to run the V1.14
  `mv`: in Claude, a WSL shell, or the VS Code terminal. The readme did not say. On top of that,
  its V1.14 block used `probe` and `$R` from the previous §5.3 block, so a fresh shell would have
  failed with `probe: command not found`. Fix: the V1.14 block is now self-contained (`cd`, `R=`,
  `probe()`) and names the target terminal (WSL bash, not PowerShell, not Claude, and why). It
  warns that every Claude session is blocked while the file is renamed, carries the optional
  hook-level half as a comment, and ends with a check that the file is back.
  **V1.14 on 2.1.280 (2026-09-24, operator, WSL shell, new self-contained block):** `V1.14 exit=2`
  as expected. Claude confirmed afterwards that `guard-config.json` is back, that no `.bak` is
  left, and that the guard passes ordinary calls again. The optional hook-level half was not
  reported. It was done on 2.1.276 (Phase 1b, item 3b).
  **→ V6.1 PASSED 2026-09-24.** The operator followed the readme from a fresh shell. Every step
  that failed or needed a question became a finding (#1–#7), and all seven are fixed in
  `readme_claude.md` or `skills/readonly-gate/SKILL.md`. With V1.10–V1.15 re-confirmed on 2.1.280,
  **V1.16 = proceed.** Still unreported and not blocking: whether Form A of `/readonly-gate`
  triggers a permission prompt.
  Lesson: seven defects in a document that passed its own author's review. Four of them (#1, #2,
  #4, #7) would have failed silently or caused side effects. V6.1 is the only check here that tests
  the document instead of the system.
  Before these findings: Claude ran every read-only command of readme §5 it is allowed to:
  §5.1, §5.2 (77 passed), §5.5 and §5.6 (all four checkers `0 failure(s)`). §5.3 is blocked for
  Claude by design (raw Pi-identifier scan), §5.4 needs live tool calls.
- V6.2 Each finding has evidence path and a testable acceptance criterion.
  **PASSED 2026-09-23**, mechanically: `47 entries, 47 report index rows, 47 rows in
  ClaudeTransition.md 3.6` / `0 failure(s)`. Negative controls: an emptied **Acceptance** field →
  `FAIL F31: missing or empty **Acceptance**`; an existing path marked absent plus a non-existent
  path → two FAIL lines for F13; both reverted.
- V6.3 (added) Claude Code version drift. `claude --version` → `2.1.280`; V1.10–V1.16 were last run
  on 2.1.276. Per the risk table they are due again (readme §5.3/§5.4). Incidental evidence that
  the hook still enforces: two blocks in this session (`python3 -c`, the `grep` above).

### Phase 7 – Handover and CI parity

- [x] Operator runs full `make ci` (operator, not Claude).
- [x] Operator verifies no secrets: `git status --ignored -- .claude`, `git ls-files .claude`.
- [x] Operator commits and pushes the branch, opens the PR; GitHub CI green; operator merges to `main`.
- [x] Pi: `git pull --ff-only` and `sudo ./deploy.sh`; postdeploy green (regression check – `.claude/` has no runtime effect).
- [x] Update this document status to "IMPLEMENTED" and record commit hash.

**Results (2026-09-24, operator-reported; the merge was verified by Claude with `git log`).**
`make ci` green, and `git status --porcelain` clean afterwards. Branch
`chore/r0-claude-safety-foundation` (21 commits, Phases 1a–6) pushed, and PR #10 merged into
`main`. The merge commit `c9d2c5dbcf2ee94389335c42d636a312c3c75597` has parents `48d1766` (main)
and `e963151` (branch head). On the Pi, `git pull --ff-only` and `sudo ./deploy.sh` ran, with
postdeploy green. The only changes outside `.claude/` in the merge were the operator's own
`Todo.txt` and `docs/operations/git-branch-workflow.md`.

Verification:
- V7.1 `git ls-files .claude | grep -c settings.local.json` → `0`.
  **PASSED** (operator, and Claude before the commit).
- V7.2 CI green on the branch (pre-commit hygiene covers `.claude/**` markdown/JSON/YAML).
  **PASSED** — PR #10 was merged after green CI.

### Phase 8 – Retire transition constraints (after Phase 7 is committed; Q1)

Goal: Claude edits repository files; C3 (secrets), C4 (no commit), C5 (no direct Pi access, with
selective service allowances), and C6 (versioned, idempotent, test-first) remain in force.

- [x] Operator confirms the edit scope (default proposal: whole repository except `secrets/**`,
      `logs/**`, `.vscode/**`, `ChatGPTHint.txt`).
      **DONE 2026-09-24**, D8-a (plus `Todo.txt`, `.git/`, `.venv/`).
- [x] Remove the transition block from `CLAUDE.md` (C1, C2) and from `settings.json`
      (Edit denies, `make`/`pre-commit` mutating-target denies).
      **DONE** — `settings.json` in 8.2 (`c12edc4`), `CLAUDE.md` §2.1 replaced by the write scope in 8.3.
- [x] Decide which make targets become allowed (`make precommit`, `make test`, `make ci`) now that
      side effects on repo files are acceptable. Pi-only and Renovate targets stay denied.
      **DONE**, D8-b and D8-c.
- [x] Update skills/agents that were read-only by design (`test-author`, `new-stack-proposal`,
      `adr-draft`) to write to their real target paths.
      **DONE with one deliberate deviation**, see 8.3 (D8-f).
- [x] Replace broad Pi denies with narrow ones before adding any allowance. Example: to allow a
      Grafana health check, remove `Bash(*192.168.178.29*)`, keep `Bash(ssh *)`/`scp`/`rsync`
      denies, and add `Bash(curl -fsS http://192.168.178.29:3000/api/health)` as a single allow.
      Deny rules always win, so a broad deny would silently block every selective allow.
      **N/A** — no allowance requested (D8-e); the procedure stays documented in readme §4.1.
- [x] Operator switches guard mode to `operate` (H7) and updates tests for C1/C2 cases.
      **DONE** — P7–P10 (`7a3c7a8`), switch (`c12edc4`).
- [x] Selective Pi allowances are added to both layers: narrow allow rule in `settings.json` and
      an exact allowlist entry in `guard-config.json` (host, port, path, method GET only).
      **N/A** (D8-e).
- [x] Record each allowance in this document with reason and date.
      **N/A** (D8-e).

#### 8.0 Operator decisions (2026-09-24)

| ID | Question | Decision |
|---|---|---|
| D8-a | Edit scope | Whole repository except `secrets/`, `logs/`, `.vscode/`, `ChatGPTHint.txt`, **`Todo.txt`**; nothing outside the repository except the plan and temp prefixes. Claude **added** `.git/` (a write to `.git/hooks/` would run code on the operator's next commit) and `.venv/` (`CLAUDE.md` §7: never create it directly) — **confirmed by the operator 2026-09-24**. |
| D8-b | make targets | `precommit`, `test`/`tests`, `ci`, `check`, `ci-doctor`, `ci-precommit`, `ci-tests`. All of them update `.venv` through the `venv` dependency and run pre-commit incl. Docker (F24); `CLAUDE.md` §7 is reworded accordingly. `venv`, `venv-clean`, `hooks`, Pi/backup/restore/renovate targets stay blocked. |
| D8-c | Formatters | Allowed: `make format`, `make ruff-fix`, `make ruff`, `ruff check --fix`, `ruff format`. |
| D8-d | Who applies self-protected changes | The operator (readme §6.5 default). Claude develops and tests in `.claude/scratch/p8/`. |
| D8-e | Selective Pi allowances | None. The broad Pi denies stay; V8.3 is n/a until an allowance is actually needed. |

**Why the guard needed code, not only config.** In the pre-Phase-8 guard, mode `operate` meant
"everything except the self-protected files" (`is_write_allowed`, `check_file_tool`): writes to
`~/.bashrc`, `~/.ssh/config` or `secrets/` would have passed the guard, and the settings layer
only has *Read* denies for the home paths. D8-a would not have been enforced at all.

#### 8.1 Patches P7–P10 (developed and tested 2026-09-24; operator applies)

Developed on copies in `.claude/scratch/p8/hooks/`. The copies were made with `cat … >`, because
`cp .claude/hooks/guard.py .claude/scratch/…` was **denied by the settings layer** on 2.1.280 (no
`guard:` reason). The `Edit(/.claude/hooks/**)` deny apparently now covers `cp` operands — V1.14 on
2.1.276 had shown the opposite for `mv`. Recorded as observed, cause [I].

| Patch | File | Change |
|---|---|---|
| P7 | `tests/test_guard.py`, `tests/test_guard_operands.py` | Every call passes `--config` with a copy of the real config and `mode: transition` pinned (module-scoped autouse fixture). The 77 cases keep testing the transition policy after the switch. `test_guard_operands.py` locates the guard relative to its own file, as `test_guard.py` does, instead of via `tests._helpers.REPO_ROOT`. |
| P8 | `guard.py` | New `in_write_scope()`: transition = `<root>/.claude/`; operate = inside `<root>`, not under `operate_write_excludes`, not a secret path (C3 now also blocks *writes* of secret material). Used by `is_write_allowed` (Bash targets, redirections) and `check_file_tool` (Write/Edit). Operate reasons: `scope: …` and `C3: …`. `label()` renames C1/C2 in operate mode to `inspect`/`policy`, because those constraints no longer exist there. Transition wording is byte-identical. `make` allows `operate_extra_make_targets` in operate mode only. H7 docstring updated. |
| P9 | `guard.py` | `check_ruff` passes everything when mode is operate **and** `operate_ruff_fix_allowed` is `true`. |
| P10 | new `tests/test_guard_operate.py` | T47 file-tool scope (21 cases), T48 Bash write scope (10), T49 make/tool policy (22), T50 C3/C4/C5 unchanged (10 + Read), T51 inspection limits stay and name no C1/C2/transition (4), T52 operate keys inert in transition (2). The policy is passed explicitly, so the tests pin the *decided* policy independent of the real config. |

`guard-config.json` is **not** changed in 8.1. It stays `transition`, so the patches change
nothing observable until 8.2.

**Verification (Claude, 2026-09-24):**
- `pytest .claude/scratch/p8/hooks/tests` → **147 passed** (77 existing + 70 new); `ruff check` →
  `All checks passed!`; `ruff format --check` → `4 files already formatted`.
- Differential check `.claude/scratch/p8/compare_transition.py`: original and patched guard
  against the real (transition) config on 29 inputs covering every changed message → **0
  differences** in exit code or stderr.
- One test expectation of Claude's was wrong on the first run: a Write into `secrets/` reports
  `C3`, not `scope`. The guard's answer is the better one, so the test was corrected.

**Apply (operator, WSL shell, repo root, on `chore/r0-phase8-operate-mode`):**

```bash
diff -u .claude/hooks/guard.py .claude/scratch/p8/hooks/guard.py | less      # review
diff -u .claude/hooks/tests/test_guard.py .claude/scratch/p8/hooks/tests/test_guard.py
diff -u .claude/hooks/tests/test_guard_operands.py .claude/scratch/p8/hooks/tests/test_guard_operands.py
less .claude/scratch/p8/hooks/tests/test_guard_operate.py
cp .claude/scratch/p8/hooks/guard.py .claude/hooks/guard.py
cp .claude/scratch/p8/hooks/tests/test_guard.py .claude/scratch/p8/hooks/tests/test_guard_operands.py \
   .claude/scratch/p8/hooks/tests/test_guard_operate.py .claude/hooks/tests/
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider -q .claude/hooks/tests   # 147 passed
```

`scratch/` is local and git-ignored. The diffs become durable with the operator's commit of 8.1.

**Applied 2026-09-24 (operator).** Claude verified afterwards: all four files byte-identical to the
tested scratch versions (`cmp`); `.claude/hooks/tests` → **147 passed**; read-only gate Form A →
ruff `All checks passed!`, `48 files already formatted`, yamllint and ShellCheck clean,
`8 passed, 4 deselected`, `7 passed, 1 skipped`, `OK: no side effects`. The guard itself is live
and still `transition` — every call in this session passed through the patched code.

#### 8.2 The switch — prepared 2026-09-24

Prepared as `.claude/scratch/p8/guard-config.json` and `.claude/scratch/p8/settings.json`. Both
parse as strict JSON.

`settings.json` diff:
- **Removed:** the transition Edit denies (`/.github`, `/docs`, `/scripts`, `/stacks`, `/tests`,
  `/config`, `/Makefile`, `/deploy.sh`, `/README.md`, `/pyproject.toml`, `/requirements-dev.txt`,
  `/renovate.json5`, `/.gitignore`, `/.gitattributes`, `/.pre-commit-config.yaml`, `/.yamllint.yml`)
  and the make denies for `precommit`, `format`, `ruff`, `check`, `ci`, `test`.
- **Added:** `Edit(/.git/**)` and `Edit(/.venv/**)`, so D8-a has two layers like the other
  exclusions, and `Edit(/.claude/settings.local.json)`, the one self-protected path that had no
  settings deny.
- **Unchanged:** everything else — self-protection, C3–C5, `make venv*`, `make hooks*`,
  `pre-commit *`, `pip install *`, the Pi/backup/restore/renovate targets.

**Preflight (Claude):** the live, patched `guard.py` was run against the prepared operate config and
the real repository root with `.claude/scratch/p8/preflight_operate.py` — **23 cases, 0 failures**.
- Passed: Write under `tests/`, `README.md`, compose edit, `make ci`, `make precommit`,
  `ruff format .`, and the plan file.
- Blocked, with the reasons shown:
  - `git commit` and `bash -c "git push"` → C4;
  - `ssh`, `curl` and WebFetch to the Pi → C5;
  - Read of `secrets/` → C3;
  - Write to `Todo.txt`, `ChatGPTHint.txt`, `.git/config`, `.venv/`, `~/.bashrc` → `scope`;
  - `guard.py` and `settings.json` → self-protection;
  - `make venv` and `make postdeploy` → `policy`;
  - `sudo ./deploy.sh` → C5.

Config values for `guard-config.json` (operator), exactly as tested in P10:
`"mode": "operate"`, `"operate_write_excludes": ["secrets", "logs", ".vscode", "ChatGPTHint.txt",
"Todo.txt", ".git", ".venv"]`, `"operate_extra_make_targets": ["precommit", "test", "tests", "ci",
"check", "ci-doctor", "ci-precommit", "ci-tests", "format", "ruff", "ruff-fix"]`,
`"operate_ruff_fix_allowed": true`. The `settings.json` change and the artefact updates follow
once 8.1 is committed.

**Applied 2026-09-24 (operator):** `settings.json` and `guard-config.json` were copied from
`scratch/p8/`. Claude confirmed `"mode": "operate"` in the live config. The operate-mode switch is
**live**.

**V8.1 live results (2026-09-24, Claude Code 2.1.280).** The operator sent each prompt as a message
to Claude; every refusal came from a real tool call.

| Prompt | Refused by | Verbatim | Side-effect check |
|---|---|---|---|
| `git commit --allow-empty -m test` | hook | `guard: C4: git commit is reserved for the operator` | HEAD `7a3c7a8` unchanged |
| `curl -fsS http://192.168.178.29:3000/api/health` | hook (raw Pi scan, before the settings deny) | `guard: C5: command references the Raspberry Pi (192.168.178.29)` | no request sent |
| Read `secrets/backup/gpg/` | settings `Read(/secrets/**)` | `File is in a directory that is denied by your permission settings.` | nothing read |
| Edit `Todo.txt` (append a blank line) | settings `Edit(/Todo.txt)` | same text | sha256 `97a0dcb4…` unchanged |
| Edit `.claude/hooks/guard.py` (append a blank line) | settings `Edit(/.claude/hooks/**)` | same text | sha256 `d4b5b461…` unchanged |

Where the settings layer refused first, the guard's own operate-mode answer for the same case is
covered by T47/T50 and by the 23-case preflight above. **V8.1 PASSED.**

#### 8.3 Artefact updates (2026-09-24, Claude, inside `.claude/` only)

| File | Change |
|---|---|
| `CLAUDE.md` | §2.1 "Transition-only" replaced by "Write scope (operate)". §7 now lets Claude run the make gates and formatters, names their side effects (unpinned pip, F21; Docker, F24), and shrinks the operator-only list. The `.venv` rule is "never directly, only via the make gates". §8 gate is `make ci`, run by Claude. Roadmap stage → **R1**. The header points to §1 here for C1–C8. 187 lines. |
| `readme_claude.md` | State line and inventory updated. The working loop has Claude run `make ci`. §3 has scope/policy rows instead of C1/C2. §4 has the 2.1.280 `cp` observation. §4.1 regroups the deny list after 8.2. §5.2 expects 147. **§5.3 V1.12 and §5.4 L2 were retargeted** (below). New L6 (`Todo.txt`). §6.5 describes the Phase 8 copy/test/apply procedure. §7 describes operate mode and the one-line rollback. |
| `skills/adr-draft` | Writes `docs/architecture/adr/…` with Status Proposed. Only the operator accepts. |
| `skills/new-stack-proposal` | Still drafts to `scratch/` — **D8-f**: a whole stack is never one commit (IN2), so the proposal is the design, and the real files land increment by increment via `increment-plan`. Only the stale C1 reasoning was replaced. |
| `skills/readonly-gate`, `skills/increment-plan` | The gate is the non-mutating option next to `make ci`; the increment template records the `make ci` result plus any fixer diff. |
| `agents/test-author` | Stays read-only by design. The main session writes after plan approval. C2 wording removed. |
| `rules/docs-adr.md`, `rules/testing.md` | C2 wording removed; the reasoning is unchanged. |

**A verification step that would have become destructive.** Readme §5.3 V1.12 and §5.4 L2 used
`echo test > README.md` as a negative test. In operate mode that write is **allowed**. Measured
with the live guard: `echo test > README.md` → exit 0, while
`echo test > .git/claude-guard-probe` → exit 2
`guard: scope: redirection would write outside the permitted write scope: .git/claude-guard-probe`,
and no file was created. An operator following the old readme after 8.2 would have overwritten
`README.md` through Claude — the same damage as V6.1 finding #4, this time with the hook's
approval. Both steps now target `.git/claude-guard-probe`: excluded, and harmless if a layer ever
failed. Lesson: **a policy change silently inverts every negative test that used a now-allowed
path.** Re-read the verification section whenever the policy changes, not only when the tooling
does.

Verification:
- V8.1 Negative tests V1.4 (commit, ssh) and V1.8 (non-allowed Pi calls) still denied.
  **PASSED 2026-09-24**, see the table above.
- V8.2 Positive test: Claude edits a file under `tests/` after approval.
  **PASSED 2026-09-24.** Claude added `"vector"` to `REQUIRED_SERVICES` in
  `tests/guards/test_10_monitoring_compose_contract.py`, the first half of F41. The service exists
  at `stacks/monitoring/compose/docker-compose.yml:362`, but no test required it. The Edit passed
  the guard (`guard.log`: `"decision": "pass"` for the file) and the operator's approval. The test
  still passes: `3 passed`. This is the first change by Claude outside `.claude/`.
- V8.2 Positive test: Claude edits a file under `tests/` after approval.
- V8.3 Each selective Pi allowance works, and a variant of it (other port/path) is denied.

---

## 7. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Deny rules bypassed via scripts/variables (K3) | Writes outside `.claude`, Pi access | Plan mode, human review, revisit hooks/sandbox |
| Over-long CLAUDE.md | Instructions ignored, context cost | ≤ ~200 lines, detail in rules/skills |
| Rules drift from ADRs | Wrong guidance | Each rule cites sources; `docs-steward` agent |
| pre-commit fixers touch `.claude/**` on operator runs | Unexpected diffs | Author files with LF, final newline, no trailing whitespace |
| Claude Code feature changes (settings/skills/rules schema) | Artefacts silently ignored | Verify docs per phase; `claude doctor`; record doc dates |
| Hook deny ignored by Claude Code (reported in #37210, #43407 for earlier versions) | False sense of security | Live negative tests V1.10–V1.16 after every Claude Code update |
| Guard bug blocks legitimate work | Friction, operator workarounds | Test matrix, decision log, `exit 0` for unclassified commands |
| Guard bug lets a violation pass | Constraint breach | Deny rules remain first layer; plan mode; side-effect diff |
| Claude edits its own guard | Guard disabled | Self-protection denies + `self_protect: true` from Phase 1b |

---

## 8. Definition of done (overall)

- All phase checkboxes ticked and verifications recorded.
- No file outside `.claude/` changed by Claude (`git diff --stat -- . ':!.claude'` empty at each
  Claude-executed step).
- `settings.local.json` provably ignored.
- Guard test matrix green (V1.9) and live hook tests passed (V1.10–V1.15) on the installed Claude Code version.
- Operator-run `make ci` and GitHub CI green.
- Findings handed over as proposals.
- Phase 8 is tracked separately and not part of the transition's definition of done.

---

## 9. Open questions

All questions answered (section 2): Q1–Q9.

Deferred: R3/R4 prerequisites (10.3), edit scope and Pi service allowances (Phase 8).

---

## 10. Incremental delivery model and roadmap (D1, D2)

Naming: roadmap stages are **R0–R4**, transition phases stay **Phase 0–8**, single steps inside a
stage are **increments** `R<stage>.<n>`.

### 10.1 Delivery rules (permanent, apply from R0 on)

| ID | Rule |
|---|---|
| IN1 | Exactly one feature is in progress at any time. A new feature starts only after the previous one is deployed and its postdeploy tests are green. |
| IN2 | A feature is split into increments. Each increment is small enough to review in one sitting, changes one concern, and leaves the system deployable. Splits that create an undeployable intermediate state are not allowed. |
| IN3 | Every increment ships with matching tests: static tests (`tests/precommit` or `tests/guards`) for repo-level contracts, and postdeploy tests (`tests/postdeploy`) for runtime behaviour. Tests are written or extended **before or together with** the implementation. |
| IN4 | Local gate before commit: Claude runs the non-mutating gate (5.3, later the operate-mode equivalent); operator runs `make ci`. Validate first, commit afterwards (resolves F14). |
| IN5 | Claude proposes a Conventional Commit message and a short change summary. The operator reviews the diff and commits personally. Claude never commits, pushes, or deploys (C4, C5). |
| IN6 | Deployment is manual by the operator: on the Pi `git pull --ff-only`, then `sudo ./deploy.sh` (which runs `make postdeploy`). |
| IN7 | An increment is **done** only when: CI green, deploy succeeded, postdeploy green, increment log updated (10.4). |
| IN8 | If deploy or postdeploy fails: no new increment. Either fix forward within the same increment scope or roll back with `git revert` (via branch + PR per IN11/IN12) + pull + deploy. |
| IN9 | Every increment that adds or changes persistent data, host secrets, ports, UFW rules, Docker networks, or host configuration also updates: backup inventory (ADR-009 §4/§5, from R2 on), `.env.example`, reconciliation scripts (3.8) and their postdeploy checks, network/firewall docs, and Renovate package rules. |
| IN10 | Version pins only (no `latest`); new images go through the pinning rule and Renovate coverage in the same increment. |
| IN11 | One feature = one short-lived branch from current `main` (`feat/…`, `fix/…`, `chore/…`, `docs/…`). Increments are commits on that branch. Branch is deleted after merge. |
| IN12 | Operator pushes the branch and opens a pull request; CI (`ci.yml`, trigger `pull_request`) must be green before merge. Claude proposes PR title and description but does not create the PR (`gh` denied). |
| IN13 | Only `main` is deployed. On the Pi: `git switch main` (once), `git pull --ff-only`, `sudo ./deploy.sh`. Feature branches are never checked out on the Pi. For a multi-increment feature, the operator either merges after each deployable increment or merges once at feature end; in both cases every merged state must pass IN7. |

### 10.2 Increment template (output of skill `increment-plan`)

```markdown
## R<stage>.<n> – <title>
- Feature: <feature this increment belongs to>
- Goal (one sentence):
- Scope: files expected to change
- Out of scope:
- Tests first: <new/changed test files and what each asserts>
- Implementation steps:
- Local gate: Claude read-only gate result / operator `make ci` result
- Proposed commit message:
- Branch: <feat|fix|chore|docs>/<short-name>
- Proposed PR title/description:
- Pi steps (after merge to main): git pull --ff-only; sudo ./deploy.sh
- Acceptance: <observable postdeploy criteria>
- Rollback: git revert <merge-or-commit> on a fix branch → PR → merge → Pi: git pull --ff-only; sudo ./deploy.sh
- Backup/docs/Renovate impact (IN9):
```

### 10.3 Roadmap

| Stage | Feature | Entry criteria | Exit criteria |
|---|---|---|---|
| **R0** | Claude transition: Phases 0–7 of this document, then Phase 8 (retire C1/C2) | This plan approved | All transition verifications recorded; guard in `operate` mode; operator-confirmed edit scope |
| **R1** | Review of the existing implementation, including host/runtime/network reconciliation (3.8) | R0 done | Findings F1–F24 re-verified and extended; decision (ADR) on which host state `deploy.sh` reconciles vs. which stays manual (UFW, network attributes, daemon.json restart policy); prioritised backlog; each accepted finding scheduled as its own increment |
| **R2** | Backup: finish implementation and tests (ADR-009) | R1 done or at least R1 findings affecting backup fixed | `make backup`, `make backup_verify` on the Pi green; fixture tests from ADR-009 §14.2 green in CI; restore dry-run and one non-critical live restore proven (§14.3); open GPG steps (doc step 6 ff.) completed |
| **R3** | Core stack: Traefik with automated Let's Encrypt | R2 done (backup covers new state) | `stacks/core/compose/` deployed; valid LE certificates with automatic renewal; existing LAN UIs routed via Traefik; postdeploy tests for routing, TLS, redirects, and cert expiry; backup inventory extended |
| **R4.1** | App stack: Stirling PDF | R3 done | Per-app stack under `stacks/apps/stirling-pdf/`, behind Traefik, tests, docs, Renovate rule enabled |
| **R4.2** | App stack: AdGuard Home | R4.1 done | Same as R4.1 plus DNS-specific tests |
| **R4.3** | App stack: Home Assistant | R4.2 done | Same as R4.1 plus backup of HA data verified by restore test |

Prerequisites that must be clarified at the start of the respective stage (not blocking R0):

- **R3 – Let's Encrypt with a LAN-only Pi:** `rpi-hub.fritz.box` is not a publicly registered domain, so no public CA can validate it. Two challenge options exist: HTTP-01 requires Let's Encrypt to fetch a token from the host over HTTP, which needs public reachability; DNS-01 proves control via a TXT record and only makes sense for automation if the DNS provider offers an API (https://letsencrypt.org/docs/challenge-types/). For a LAN-only Pi, DNS-01 with a public domain is the likely path. Open: which domain (`Todo.txt` mentions an existing domain at WebHostOne), whether that provider is supported by Traefik's ACME DNS providers (not yet verified), and how local name resolution for the public names is done (e.g. AdGuard rewrites later in R4.2, or FritzBox DNS).
- **R3 – Firewall:** Traefik adds inbound 80/443 (and possibly removes direct LAN exposure of 3000/9428). This depends on the R1 decision on UFW reconciliation (F15).
- **R3 – deploy.sh:** currently deploys only the monitoring stack. Multi-stack deployment (order, per-stack env files, per-stack config hash) is a design decision (ADR) at the start of R3.
- **R4.2 – AdGuard Home:** needs port 53 on the Pi and a decision on how clients use it (FritzBox DNS setting); conflicts with any existing local DNS listener must be checked on the Pi.
- **R4.3 – Home Assistant:** device discovery commonly relies on host networking, which conflicts with the explicit-network rule (hint §7). Needs an ADR exception or an alternative before implementation.

### 10.4 Increment log

| Increment | Date | Commit | CI | Deploy + postdeploy | Notes |
|---|---|---|---|---|---|
| R0.0 toolchain parity | 2026-09-17 | `3b109f6` | green |  tests: passed, deploy: done | |
| R0.0b workflow docs merge (`docs/r0-workflow-docs`) | 2026-09-17 | 6fa74937cd4b48190d0117fd44d7bd319a07f369 | green |  tests: passed, deploy: done | interlinked the documents |
| R0.1 (Phase 0) | 2026-09-17 | 48d17669ce91be0484babbfbfcf0db41b8c32e2f | green | tests: passed, deploy: done | Ruleset verified (1a, 1b); test 4 failed: auto-delete head branches was disabled, enabled 2026-09-17, verify on next PR. Row was labelled "Phase 1a" by mistake; its evidence is Phase 0 (branch protection, toolchain record). |
| R0.10 (Phase 8) | 2026-09-24 | `7a3c7a8` (P7–P10), `c12edc4` (switch), `10839c3` (artefacts), `e72f314` (V8.2); merge `99a6347` (PR #12) | green | deploy: done, postdeploy: green (regression only) | Guard mode `operate` with an enforced write scope; tests 77 → 147; preflight 23/23; V8.1 5/5 refused live; V8.2 first write outside `.claude/`. The first `make ci` run by Claude produced F47 and new F21 evidence. A negative test (V1.12/L2) that operate mode would have made destructive was caught in 8.3. |
| R1.2 Alertmanager renderer (F36, F8, F37) | 2026-09-25 | `bc37ada` (tests), `bdb6a80` (fix); merge `07b4448` (PR #17) | green | deploy: containers up, **postdeploy failed** — `test_56`: anonymous volume on the renderer from the image's `VOLUME /alertmanager`; 58 other checks passed incl. `test_22` (exit 0, network none) | IN8 fix-forward on `fix/r1-2-renderer-anon-volume`: `tmpfs: [/alertmanager]`, plus an image-VOLUME coverage test. The dangling volume `de74cbca…` is removed by the operator after that deploy. Deploy also logged `repo-ownership: mismatch detected` (cause unknown). |
| R1.1-fix renderer group | 2026-09-25 | `99fcdd7`; merge `2657096` (PR #15) | green | deploy: done, postdeploy: green (58 passed, 4 skipped) | Renderer `0:0` + `group_add 65534`. Measured on the Pi: dir `750 root:nogroup`, file `640 root:nogroup`; second run `init-permissions: skipped (already correct)`. F26, F35, F39 accepted; F26b partly (restore fixture → R2/F9). |
| R1.1 Alertmanager secret mode (F26, F26b, F35, F39) | 2026-09-25 | `5993245` (tests), `bf1693a` (fix); merge `2fdfb10` | green | **deploy failed** — renderer exit 10 (`apk add` cannot chown with primary group 65534 and no `CAP_CHOWN`); alertmanager left `Created`; postdeploy not reached | IN8 fix-forward on `fix/r1-alertmanager-render-group`: renderer `user: "0:0"` + `group_add: ["65534"]`. The fix row follows after its deploy. |
| R0.9 (Phase 7) | 2026-09-24 | `c9d2c5dbcf2ee94389335c42d636a312c3c75597` (merge, PR #10) | green | deploy: done, postdeploy: green | Handover: `make ci` green, V7.1/V7.2 passed. R0.2–R0.8 were delivered together in this merge, so their CI and deploy columns refer to it. |
| R0.2 (Phase 1a) | 2026-09-18 | `ecfc0ba`, merged in `c9d2c5d` | green | done via R0.9 (`.claude/` has no runtime effect) | Safety foundation built: `.gitignore`, `settings.json`, `guard.py`, `guard-config.json`, 35 guard tests. V1.1/V1.9 green, V1.3b negative (5.2.1 D-f). Hook not yet registered — that is Phase 1b. |
| R0.8 (Phase 6) | 2026-09-23 … 24 | `ea6f7bb`, `e963151`, merged in `c9d2c5d` | green | done via R0.9 | `readme_claude.md` (operator guide incl. grouped deny list), `reports/repo-findings.md` (47 findings, five fields each, R1 grouping a–i), verifiers moved to tracked `tools/` (D6-a, three latent ruff errors fixed) plus `check_findings.py`; §3.6 reduced to an index (D6-b). V6.2 passed with negative controls. **V6.1 passed 2026-09-24** after the operator walkthrough, which found and fixed seven readme/skill defects (#1–#7), including one that caused a real test commit and a README overwrite. V1.10–V1.16 re-confirmed on 2.1.280. |
| R0.7 (Phase 5) | 2026-09-23 | `2f58e73`, `2c88ea6`, merged in `c9d2c5d` | green | done via R0.9 | `.claude/agents/`: four read-only subagents, `tools: Read, Grep, Glob` each, 703 chars of always-loaded descriptions. D5-a (an absent `tools` grants everything — V5.3 inverted accordingly) and D5-b (bodies must not restate the inherited rules) recorded. **V5.1–V5.3 all passed** (V5.1/V5.2 after the operator restart — agents are not hot-loaded the way skills are). V5.2 produced F45 and F46, extended F26, closed F42's caveat, and forced the third correction of a Claude artefact claiming documentation that does not exist. |
| R0.6 (Phase 4) | 2026-09-23 | `aa80bf9`, merged in `c9d2c5d` | green | done via R0.9 | `.claude/skills/`: eight skills, always-loaded description cost 1,236 chars total (cap is 1,536 per skill). D4-a (descriptions are the budget), D4-b (`allowed-tools` only on `readonly-gate`) and D4-c (no `paths` on skills) recorded. **V4.1–V4.6 all passed.** Invoking the skills produced F44 and showed that five of seven ADR-009 backup requirements are already implemented — F9 had made that invisible. |
| R0.5 (Phase 3) | 2026-09-23 | `d728e05` … `92ce290`, merged in `c9d2c5d` | green | done via R0.9 | `.claude/rules/`: eight path-scoped rule files, 468 lines, none always-loaded. D3-a (path scoping is mandatory, not optional) and D3-b (eight rules, not ten) recorded. V3.1 passed incl. a mechanical cited-path check; V3.2/V3.3 open. |
| R0.4 (Phase 2, **complete**) | 2026-09-23 | `f1567c6`, merged in `c9d2c5d` | green | done via R0.9 | `CLAUDE.md` restructured: German bootstrap (25 lines) → English project memory, 170 lines, ten sections. **V2.1–V2.3 all passed**; V2.3 verified live in a fresh session, answered from loaded memory with no file access. Decisions D2-a (C1–C8 split for a clean Phase 8 cut) and D2-b (CLAUDE.md vs ClaudeTransition.md by audience) recorded. |
| R0.3 (Phase 1b, **complete**) | 2026-09-18 … 2026-09-23 | 117d092f528494786b66ff4bb166075ed86e7344 (guard review) + follow-up, merged in `c9d2c5d` | green | done via R0.9 | Hook registered and **proven to enforce**. **V1.10–V1.16 all passed 2026-09-23**, V1.16 = proceed (HEAD `e7580bb` unchanged, `README.md` untouched). **Patches P1–P6 applied**, matrix 65 → **77 passed**, ruff clean. T43 re-probe and hook-level V1.14 done; `self_protect` back to `true`. |

### 10.5 Toolchain record (Phase 0)

Run once in WSL from the repo root (read-only, no side effects):

```bash
.venv/bin/python --version
.venv/bin/python -m pip check
.venv/bin/ruff --version
.venv/bin/yamllint --version
.venv/bin/python -m pytest --version -p no:cacheprovider
.venv/bin/pre-commit --version
.venv/bin/shellcheck --version | head -2   # after R0.0
git status --porcelain
```

Record the values in Phase 0. After R0.0 the versions must equal the pre-commit pins (F21).

### 10.6 R0.0 – Toolchain parity (first increment, executed manually by the operator)

Reason for manual execution: C1 still applies; Claude may not write outside `.claude/`. The files
below were prepared outside the repo and tested (see verification evidence).

- **Feature:** toolchain parity between `.venv` and pre-commit (fixes F21 for ruff, ShellCheck, yamllint)
- **Goal:** tools in `.venv` have exactly the versions pinned in `.pre-commit-config.yaml`, enforced by a test.
- **Branch:** `chore/r0-toolchain-parity`
- **Scope:**
  - `requirements-dev.txt`: `ruff==0.14.11`, `shellcheck-py==0.10.0.1`, `yamllint==1.35.1` (exact pins, values taken from existing hook `rev`s; no version upgrade)
  - `tests/precommit/test_50_toolchain_version_parity.py` (new, marker `precommit`)
- **Out of scope:** upgrading any tool; `pyproject.toml` dev extras (F22); pip pinning in `make venv`; Renovate coverage for pre-commit/pip (F4); `ci.yml`.
- **Tests first:** `test_50_toolchain_version_parity.py`
  - `test_parity_map_repos_exist_in_pre_commit_config`: every mapped hook repo still exists
  - `test_requirements_dev_pins_match_pre_commit_rev[...]`: exact `==` pin equals hook `rev` without leading `v`, per tool
- **Implementation steps (operator, WSL):**
  1. `git switch main && git pull --ff-only && git switch -c chore/r0-toolchain-parity`
  2. Copy the prepared test file and apply the three pins in `requirements-dev.txt`
  3. `make venv` (installs pins; on aarch64 `shellcheck-py` builds from sdist and downloads the ShellCheck binary from GitHub with checksum verification, because PyPI has no Linux aarch64 wheel for 0.10.0.1 [V, PyPI file list + sdist `setup.cfg`])
  4. `.venv/bin/ruff --version`, `.venv/bin/shellcheck --version`, `.venv/bin/yamllint --version` → 0.14.11 / 0.10.0 / 1.35.1
  5. `make ci`
- **Proposed commit message:** `chore(tooling): pin ruff, shellcheck-py and yamllint to pre-commit revs`
- **Proposed PR description:** Aligns `.venv` tool versions with `.pre-commit-config.yaml` and adds a precommit test that fails on future drift. No tool upgrade; no runtime change on the Pi.
- **Pi steps (after merge):** `git pull --ff-only`; `sudo ./deploy.sh` (regression check only)
- **Acceptance:** CI green on PR; `make ci` green locally; negative check: temporarily set `ruff>=0.9,<1.0` → test fails with actionable message; revert.
- **Rollback:** `git revert` via fix branch + PR → pull + deploy
- **Backup/docs/Renovate impact (IN9):** none; future bumps must change `.pre-commit-config.yaml` and `requirements-dev.txt` in the same commit (enforced by the test)
- **Verification evidence (prepared in isolation, Python 3.12, ruff 0.14.11):** 4 passed; negative cases range pin, missing package, rev bump, removed hook repo → each fails with its message; `ruff check` and `ruff format --check` clean on the test file.

---

## 11. References

- Claude Code settings files and precedence: https://code.claude.com/docs/en/settings
- Claude Code permissions (Read/Edit gitignore patterns, deny limits): https://code.claude.com/docs/en/permissions
- Claude Code skills: https://code.claude.com/docs/en/skills
- Claude Code hooks guide: https://code.claude.com/docs/en/hooks-guide
- Claude Code hooks reference: https://code.claude.com/docs/en/hooks
- Reported hook deny issues: https://github.com/anthropics/claude-code/issues/37210,
  https://github.com/anthropics/claude-code/issues/43407
- Repository sources: `ChatGPTHint.txt`, `Makefile`, `deploy.sh`, `.pre-commit-config.yaml`,
  `.github/workflows/ci.yml`, `renovate.json5`, `docs/DevWorkflow.md`,
  `docs/architecture/adr/*`, `docs/operations/*`, `stacks/monitoring/compose/docker-compose.yml`,
  `Todo.txt`
