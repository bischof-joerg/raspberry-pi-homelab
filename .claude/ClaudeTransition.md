# Claude Transition Plan – raspberry-pi-homelab

- **Status:** READY FOR PHASE 0/1a (v0.9) – Q1–Q9 answered; R0.0 toolchain parity defined as first increment (10.6)
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
| Q3 | Claude Code version (WSL) | `2.1.273` | Newer than all version notes cited from the settings docs (v2.1.211, v2.1.257, v2.1.267), so current docs apply. WSL checkout path still pending. |
| Q4 | `make doctor` | Allowed (`make doctor`, `make doctor-strict`) | Added to allow list; covered by the before/after side-effect check. |
| Q5 | Pi FQDN | `rpi-hub.fritz.box` (LAN only) | Added to deny list and hook config. `*rpi-hub*` already matches it; explicit entries kept for clarity and for WebFetch domain rules. |
| Q7 | Guard implementation language | **Option A:** Python 3 standard library, tokenising exclusively with `shlex` | No third-party shell parser (e.g. `bashlex`). See H1/H8. |
| Q8 | Unclassified Bash commands | **Option A:** guard exits 0; deny rules and plan-mode approval decide | Guard blocks only classified violations and fail-closed cases (H2). |
| D1 | Delivery model | One feature at a time, delivered in small increments, each with matching tests. Operator commits every change personally, pulls on the Pi (`git pull`) and deploys manually (`sudo ./deploy.sh`). | Section 10.1; rule `incremental-delivery.md`; skill `increment-plan` |
| D2 | Roadmap | R0 transition → R1 review → R2 backup → R3 core stack (Traefik + Let's Encrypt) → R4 app stacks (Stirling PDF, AdGuard Home, Home Assistant) | Section 10.3; transition Phase 8 moves into R0 because R1 fixes and R2 need writes outside `.claude/` |
| Q9 | Git flow per increment | **Option A:** short-lived feature branch per feature; increments are commits on it; push → CI on pull request → operator merges to `main` → Pi pulls `main` | IN11–IN13 (10.1); Phase 0 branch `chore/claude-transition`; Pi only ever pulls `main` |
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

These go into `.claude/reports/repo-findings.md` in Phase 6 as proposals. Items marked [I] need
verification in WSL or on the Pi by the operator.

| ID | Finding | Evidence |
|---|---|---|
| F1 | Config hash only includes `vmagent.yml`, `vmalert.yml`, `alertmanager/alertmanager.yml`, `victoriametrics.yml`. Changes to `vmalert/rules/*`, `vector/vector.yaml`, `alertmanager.yml.tmpl`, Grafana provisioning do not change the hash → no recreate. | `deploy.sh` `compute_monitoring_config_hash` [V] |
| F2 | Hash list contains `alertmanager/alertmanager.yml` (only `.tmpl` exists in repo); `vmalert.yml` and `victoriametrics.yml` are in the repo but not mounted by compose. | compose + file list [V] |
| F3 | Images pinned by tag, not digest (hint says prefer digests). | compose [V] |
| F4 | Renovate manages only `docker-compose`; GitHub Actions (`@v4`/`@v5` tags), pre-commit hook revs, pip ranges and the Grafana plugin pin are unmanaged. | `renovate.json5`, `ci.yml` [V] |
| F5 | `README.md` is stale: mentions Prometheus, Loki, Promtail, a different env path, broken relative links. | `README.md` [V] |
| F6 | ADR numbering inconsistent (file ADR-0001 titled ADR-0004, ADR-0008 titled ADR-000X, ADR-009 three digits). | ADR files [V] |
| F7 | `victorialogs` has no `restart` policy and no healthcheck; node-exporter/cadvisor have no healthcheck. | compose [V] |
| F8 | Renderer installs `gettext` via `apk add` at every run → network dependency, non-deterministic package version. | compose [V] |
| F9 | ADR-009 DD-012 requires tests before accepting backup scripts; no backup tests exist. | `tests/` listing [V] |
| F10 | pre-commit pytest hook pins `pytest<9`, local `__pycache__` shows pytest 9.0.2 was used → toolchain drift. | `.pre-commit-config.yaml`, pyc names [I] |
| F11 | `.gitattributes` enforces LF for sh/yml/yaml/json/toml but not `*.md`, `*.py`, `Makefile`, `*.json5`. | `.gitattributes` [V] |
| F12 | `.env.example` lists `DOCKER_GID`/`SYSTEMD_JOURNAL_GID` twice and contains host-derived values, contradicting ADR-0007 §4. | `.env.example` [V] |
| F13 | compose mounts `../alertmanager/templates`, which does not exist in the repo; Docker may create it on the Pi as root. | compose + listing [I] |
| F14 | `docs/DevWorkflow.md` §4 commits before `make ci`; `ChatGPTHint.txt` §5 says only validated commits. | DevWorkflow [V] |
| F15 | UFW is not reconciled on deploy; `cleanup-ufw.sh` is manual and has no make target (`Todo.txt` notes "Aktivieren in make"). Hint §7 expects UFW bootstrap in `deploy.sh`. | `deploy.sh`, `Makefile` [V] |
| F16 | `bootstrap-networks.sh` runs without subnet/bridge env in deploy; on a fresh host `monitoring` would be created without `br-monitoring`/`172.20.0.0/16`, while `cleanup-ufw.sh`, `daemon.json` (`metrics-addr 172.20.0.1:9323`) and `test_35` depend on exactly these values. | `deploy.sh`, scripts [V]; fresh-host effect [I] |
| F17 | Order in `deploy.sh`: `daemon.json` (with `metrics-addr` on the monitoring gateway IP) is applied and Docker restarted **before** networks are bootstrapped; on a fresh host the metrics address may not exist yet. | `deploy.sh` main [V]; Docker behaviour [I] |
| F18 | `ensure-docker-daemon-json.sh` restarts Docker on any content change during deploy → full stack restart without a separate maintenance window or backup step. | script [V] |
| F19 | Host-specific literals in reconciliation scripts: `cleanup-ufw.sh` usage path `/home/admin/iac/...`, stale bridge names `br-abe` and `br-bd2` in a regex; fixed temp file `/tmp/bootstrap-networks.overlap`. | scripts [V] |
| F21 | Toolchain version drift between local tools and pre-commit/CI: pre-commit pins `shellcheck-py v0.10.0.1`, `ruff-pre-commit v0.14.11`, `yamllint v1.35.1`, while `requirements-dev.txt` uses ranges (`ruff>=0.9,<1.0`, `yamllint>=1.35,<2.0`) and the system ShellCheck in WSL is 0.9.0. `make venv` also upgrades pip unpinned. Results of the read-only gate and of pre-commit can differ. | `.pre-commit-config.yaml`, `requirements-dev.txt`, operator output [V] |
| F22 | Second, diverging source of dev dependencies: `pyproject.toml` `[project.optional-dependencies].dev` (`ruff>=0.14.11`, `pytest>=8`, `typeguard>=4`, …) and the `pytest-precommit` hook's `additional_dependencies` duplicate `requirements-dev.txt`. `make venv` uses `requirements-dev.txt` only. | `pyproject.toml`, `Makefile`, `.pre-commit-config.yaml` [V] |
| F23 | `tests/precommit/test_15_json_valid.py` is marked `lint`, not `precommit`; `make precommit` runs `pytest tests/precommit -m precommit`, so this test is likely deselected in precommit, and `make test` ignores `tests/precommit`. Other files not yet checked. | test file + `Makefile` [V]; effect [I] |
| F20 | `ensure-journald-read.sh` defaults to `TARGET_USER=vector` (no such host user expected) while `deploy.sh` passes `admin`; the container runs as uid 65532 and gets the GID via `group_add`, so group membership of `admin` is likely irrelevant for Vector. | scripts + compose [V]; relevance [I] |

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
│   └── tests/test_guard.py    # pytest matrix for the guard (run from .venv, no repo side effects)
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
      "Edit(./.github/**)", "Edit(./docs/**)", "Edit(./scripts/**)", "Edit(./stacks/**)",
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
- The exact semantics of `./` vs `/` anchors in project settings must be confirmed against the
  permissions docs and by negative test V1.3 before the file is considered final.

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
5. **Heredocs and stdin scripts**: `bash <<…`, `sh -s`, `python3 -`, `| bash`, `| sh` → block
   during transition (code body is not reliably inspectable).
6. **Inline interpreter code**: `python3 -c`, `perl -e/-i`, `ruby -e`, `node -e` → block during
   transition. `python -m pytest` and `.venv/bin/python -m pytest` stay allowed.
7. **Raw scan** of the full original string (after un-escaping) for Pi identifiers
   (`rpi-hub`, `rpi-hub.fritz.box`, `192.168.178.29`) → block. Catches quoting tricks that the
   parser resolves differently.

**Block list per segment (transition mode):**

| Category | Heads / patterns |
|---|---|
| C4 Git | `git` with `commit`, `push`, `tag`, `merge`, `rebase`, `reset`, `checkout`, `switch`, `stash`, `add`, `rm`, `am`, `cherry-pick`, `revert`, `clean`, `config`, `gh` (all) |
| C5 Remote / Pi | `ssh`, `scp`, `sftp`, `rsync`, `ansible*`, `mosh`, `nc`, `ncat`, `socat`, `telnet`; `curl`, `wget`, `ping`, `nmap` with any Pi identifier; `./deploy.sh`, `deploy.sh`, `sudo`, `su`, `doas`; any execution of `scripts/host/*`, `scripts/host-runtime/*`, `scripts/network/*`, `init-permissions.sh` (also via `bash <script>`); `ufw`, `systemctl`, `usermod`, `groupadd`, `docker network create`/`rm` |
| C2 Mutating tools | `make` targets except `doctor`, `doctor-strict`, `help`; `pre-commit`; `pip`/`pip3 install`, `uninstall`; `ruff` without `--check`/`check --no-fix`; `ruff format` without `--check`; `gpg`; `docker` except `compose config`, `version`, `info`, `ps`, `images` |
| C1 File writes | `rm`, `mv`, `cp`, `ln`, `touch`, `mkdir`, `rmdir`, `chmod`, `chown`, `truncate`, `install`, `dd`, `tee`, `patch`, `sed -i`, `git apply` → allowed only if **all** path operands resolve inside `<root>/.claude/` or an allowed temp dir (`/tmp/claude-*`) |
| C1 Redirections | `>`, `>>`, `>` with clobber, `&>`, `2>` targets outside `.claude/`, `/tmp/claude-*`, or `/dev/null` |
| C3 Secret reads | `cat`, `less`, `more`, `head`, `tail`, `grep`, `rg`, `awk`, `sed`, `source`, `.`, `base64`, `xxd`, `strings` on secret patterns (5.4.4) |

Anything the parser cannot classify is **not** blocked by the guard (exit 0, decision Q8) and falls through to
the deny rules and the plan-mode approval prompt. This keeps normal read-only work usable; the
operator remains the final gate.

#### 5.4.6 Test matrix (`.claude/hooks/tests/test_guard.py`)

Run: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider -q .claude/hooks/tests`
The tests invoke `guard.py` as a subprocess with crafted stdin JSON and `CLAUDE_PROJECT_DIR`
pointing to a temporary fixture repo (`tmp_path`), so no real repo file is touched.

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

---

## 6. Implementation phases

Each phase ends with: verification output → operator review of `git diff -- .claude` → operator
commits manually. Claude never commits.

### Phase 0 – Preparation (operator)

- [ ] Work in the WSL checkout, not the Windows copy.
- [ ] Copy this file into `<wsl-repo>/.claude/ClaudeTransition.md` (LF line endings).
- [ ] Create the feature branch from current `main` (Q9/IN11): `git switch main && git pull --ff-only && git switch -c chore/claude-transition`.
- [ ] Optional but recommended: enable branch protection on `main` in GitHub (require status checks `doctor (strict)`, `precommit (hooks + tests/precommit)`, `tests (unit/integration, no postdeploy)` and a pull request before merge).
- [x] Record `claude --version` here: `2.1.273`.
- [x] Record WSL checkout path here: `/home/micro/src/raspberry-pi-homelab`.
- [x] Record Pi FQDN here: `rpi-hub.fritz.box`.
- [ ] **R0.0 toolchain parity merged and deployed (10.6) – prerequisite for Phase 1a.**
- [x] Ensure `.venv` exists: operator ran `make ci` successfully (creates/updates `.venv`, upgrades pip, installs `requirements-dev.txt`).
- [ ] Record `.venv` tool versions after R0.0 (commands in 10.5): python `3.12.3`, ruff `0.14.11` expected, shellcheck `0.10.0` expected, yamllint `1.35.1` expected, pytest `____`, pre-commit `____`.
- [ ] Re-run `.venv/bin/python -m pip check` explicitly with the venv interpreter (first run was probably the system pip: no `(.venv)` prompt); `git status --porcelain` was clean [V, operator output].
- [ ] Confirm `git status --porcelain` is clean after `make ci` (pre-commit fixers may have modified files).
- [x] Answer open questions Q1–Q6 (section 9).
- [x] Answer Q7 and Q8 (section 9).
- [x] Confirm toolchain in WSL: `python3` 3.12.3 (matches CI `python-version: "3.12"`; guard needs >= 3.10); system `shellcheck` 0.9.0 (differs from pre-commit pin, see F21).

Acceptance: branch exists, Claude Code version recorded, questions answered.

### Phase 1a – Safety foundation: build and test (hook not yet active)

Deliverables: `.claude/.gitignore`, `.claude/hooks/guard.py`, `.claude/hooks/guard-config.json`,
`.claude/hooks/tests/test_guard.py`, draft `.claude/settings.json` **without** the `hooks` block.

- [ ] Re-read hooks docs (5.4) and record doc date and any contract differences here.
- [ ] Write `.claude/.gitignore`: `settings.local.json`, `scratch/`, `logs/`.
- [ ] Write `settings.json` from 5.2 (strict JSON), `self_protect: false` in guard config.
- [ ] Write `guard.py`, `guard-config.json`, tests T01–T35.
- [ ] Restart Claude Code; run `/status`, `/permissions`.

Verification:
- V1.1 `git check-ignore -v .claude/settings.local.json .claude/logs/guard.log .claude/scratch/x` → all matched by `.claude/.gitignore`.
- V1.2 `/status` lists "Shared project settings"; mode shows plan.
- V1.3 Negative test: ask Claude to append a line to `README.md` → denied without prompt. If not,
  switch the anchor form per the permissions docs and re-test. Working form: `__________`.
- V1.4 Negative tests: `git commit --allow-empty -m test`, `ssh rpi-hub true`, `make precommit`,
  reading a file under `secrets/` → all denied.
- V1.5 Positive test: edit a file under `.claude/scratch/` → allowed after approval.
- V1.6 `claude doctor` reports no rejected permission or hook entries.
- V1.7 `make doctor` runs without prompt; `git status --porcelain --ignored` identical before/after.
- V1.8 Negative tests for Q2/Q5: `curl -fsS http://192.168.178.29:3000/api/health`,
  `ping -c1 rpi-hub.fritz.box`, WebFetch `http://rpi-hub:3000` → all denied.
- V1.9 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider -q .claude/hooks/tests` → 35 passed;
  `.venv/bin/ruff check --no-fix --no-cache .claude/hooks` and `ruff format --check` clean.

### Phase 1b – Activate the hook (operator applies, Claude verifies)

- [ ] Operator reviews `guard.py` line by line (it is the enforcement boundary).
- [ ] Operator adds the `hooks` block (5.4.1) and self-protection denies (5.2) to `settings.json`
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
- V2.2 Every C1–C8 constraint present (manual check against section 1).
- V2.3 New session: ask "What may you not do in this repo?" → answer lists C1–C5 correctly.

### Phase 3 – Rules

- [ ] Verify current rules mechanism and `paths` frontmatter in official docs before writing;
      record the doc URL and date here.
- [ ] Write the ten rule files from section 5. Each: purpose, MUST/SHOULD list, source references
      (ADR/doc path), examples of violations.

Verification:
- V3.1 Each rule cites at least one repo source file.
- V3.2 In a new session, open `stacks/monitoring/compose/docker-compose.yml` and ask for a
  compliance review → answer references `compose-stacks.md` content (naming, pinning, bind mounts).
- V3.3 No rule contradicts an accepted ADR (manual review by operator).

### Phase 4 – Skills

- [ ] Verify SKILL.md frontmatter fields against current docs; record URL/date.
- [ ] Write the eight skills. Skills that would produce repo changes output **proposals** into
      `.claude/scratch/` or into chat, never into other paths (C1).
- [ ] `readonly-gate` embeds 5.3 including the before/after comparison.

Verification:
- V4.1 `/skills` lists all eight.
- V4.5 Run `increment-plan` for a sample feature → output follows the template in 10.2.
- V4.2 Run `readonly-gate` → completes; before/after diff empty.
- V4.3 Run `image-pin-audit` → table matches section 3.3 image list.
- V4.4 Run `backup-progress` → reports at least F9 and GPG step 6.

### Phase 5 – Subagents

- [ ] Write four agent files with minimal tool sets (read-only: Read, Grep, Glob; no Edit/Write/Bash
      unless justified and listed).

Verification:
- V5.1 `/agents` lists all four.
- V5.2 `security-reviewer` on the compose file flags cadvisor `privileged: true` and LAN ports
  3000/9428 with the documented justification.
- V5.3 Agent definitions contain no Edit/Write tools.

### Phase 6 – Human documentation and findings report

- [ ] `readme_claude.md`: purpose of each artefact, how to start a session, what Claude will refuse
      and why, how to verify the safety set-up (V1.x), how to update artefacts.
- [ ] `reports/repo-findings.md`: F1–F23 with evidence, impact, proposed fix, suggested test.

Verification:
- V6.1 Operator can follow `readme_claude.md` from a fresh shell without extra knowledge.
- V6.2 Each finding has evidence path and a testable acceptance criterion.

### Phase 7 – Handover and CI parity

- [ ] Operator runs full `make ci` (operator, not Claude).
- [ ] Operator verifies no secrets: `git status --ignored -- .claude`, `git ls-files .claude`.
- [ ] Operator commits and pushes the branch, opens the PR; GitHub CI green; operator merges to `main`.
- [ ] Pi: `git pull --ff-only` and `sudo ./deploy.sh`; postdeploy green (regression check – `.claude/` has no runtime effect).
- [ ] Update this document status to "IMPLEMENTED" and record commit hash.

Verification:
- V7.1 `git ls-files .claude | grep -c settings.local.json` → `0`.
- V7.2 CI green on the branch (pre-commit hygiene covers `.claude/**` markdown/JSON/YAML).

### Phase 8 – Retire transition constraints (after Phase 7 is committed; Q1)

Goal: Claude edits repository files; C3 (secrets), C4 (no commit), C5 (no direct Pi access, with
selective service allowances), and C6 (versioned, idempotent, test-first) remain in force.

- [ ] Operator confirms the edit scope (default proposal: whole repository except `secrets/**`,
      `logs/**`, `.vscode/**`, `ChatGPTHint.txt`).
- [ ] Remove the transition block from `CLAUDE.md` (C1, C2) and from `settings.json`
      (Edit denies, `make`/`pre-commit` mutating-target denies).
- [ ] Decide which make targets become allowed (`make precommit`, `make test`, `make ci`) now that
      side effects on repo files are acceptable. Pi-only and Renovate targets stay denied.
- [ ] Update skills/agents that were read-only by design (`test-author`, `new-stack-proposal`,
      `adr-draft`) to write to their real target paths.
- [ ] Replace broad Pi denies with narrow ones before adding any allowance. Example: to allow a
      Grafana health check, remove `Bash(*192.168.178.29*)`, keep `Bash(ssh *)`/`scp`/`rsync`
      denies, and add `Bash(curl -fsS http://192.168.178.29:3000/api/health)` as a single allow.
      Deny rules always win, so a broad deny would silently block every selective allow.
- [ ] Operator switches guard mode to `operate` (H7) and updates tests for C1/C2 cases.
- [ ] Selective Pi allowances are added to both layers: narrow allow rule in `settings.json` and
      an exact allowlist entry in `guard-config.json` (host, port, path, method GET only).
- [ ] Record each allowance in this document with reason and date.

Verification:
- V8.1 Negative tests V1.4 (commit, ssh) and V1.8 (non-allowed Pi calls) still denied.
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
- Findings F1–F23 handed over as proposals.
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
| **R1** | Review of the existing implementation, including host/runtime/network reconciliation (3.8) | R0 done | Findings F1–F23 re-verified and extended; decision (ADR) on which host state `deploy.sh` reconciles vs. which stays manual (UFW, network attributes, daemon.json restart policy); prioritised backlog; each accepted finding scheduled as its own increment |
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
| R0.0 toolchain parity | | | | | |
| R0.1 (Phase 1a) | | | | | |

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
- **Branch:** `chore/toolchain-parity`
- **Scope:**
  - `requirements-dev.txt`: `ruff==0.14.11`, `shellcheck-py==0.10.0.1`, `yamllint==1.35.1` (exact pins, values taken from existing hook `rev`s; no version upgrade)
  - `tests/precommit/test_50_toolchain_version_parity.py` (new, marker `precommit`)
- **Out of scope:** upgrading any tool; `pyproject.toml` dev extras (F22); pip pinning in `make venv`; Renovate coverage for pre-commit/pip (F4); `ci.yml`.
- **Tests first:** `test_50_toolchain_version_parity.py`
  - `test_parity_map_repos_exist_in_pre_commit_config`: every mapped hook repo still exists
  - `test_requirements_dev_pins_match_pre_commit_rev[...]`: exact `==` pin equals hook `rev` without leading `v`, per tool
- **Implementation steps (operator, WSL):**
  1. `git switch main && git pull --ff-only && git switch -c chore/toolchain-parity`
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
