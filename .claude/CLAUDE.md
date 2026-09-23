# CLAUDE.md — raspberry-pi-homelab

Project memory, loaded into every session. Keep it lean; details live in the files named in §9.
Language: English only (decision E6). Source of the original German bootstrap rules: §2.

## 1. Mission and scope

- A Raspberry Pi homelab run as Infrastructure as Code with GitOps and tests.
- The Pi is a **deploy target only**. No development, no manual fixes, no experiments on it.
- Everything that defines the system — host config, networks, services — exists in this repository.

## 2. Constraints

### 2.1 Transition-only — removed in Phase 8

These apply while the Claude artefacts are being built. Phase 8 deletes this subsection, the
matching deny rules in `settings.json`, and switches the guard to `mode: "operate"`.

| ID | Constraint |
|----|------------|
| C1 | Write access **only** inside `.claude/`. Everything else in the repository is read-only. |
| C2 | No command may modify files outside `.claude/` as a side effect — formatters, `--fix`, pre-commit fixers, venv creation, caches, logs, `__pycache__`. |
| C7 | Transform both the implemented repository approach and `ChatGPTHint.txt` into Claude artefacts. |
| C8 | Extend and restructure `.claude/CLAUDE.md` (this file). |

### 2.2 Permanent — these stay after Phase 8

| ID | Constraint |
|----|------------|
| C3 | No secrets in Git. `.claude/settings.local.json` must never be committed. Never read `secrets/**`, `*.env`, `*.kdbx`, `*.keyx`, `*.pem`, `*.key`, `~/.ssh/**`, `~/.gnupg/**`, `~/.config/renovate/**`, `/etc/raspberry-pi-homelab/**`. `.env.example` is fine. |
| C4 | No automatic `git commit` — and by extension no `push`, `tag`, `rebase`, `merge`, `reset`, `gh`. Claude proposes commit messages; the operator commits. |
| C5 | No direct access to the Raspberry Pi: no SSH/SCP/rsync, no remote `git pull`, no `deploy.sh`, no HTTP calls against Pi services, no restore streaming. Host `rpi-hub`, FQDN `rpi-hub.fritz.box`, IP `192.168.178.29`. |
| C6 | Preserve the version-pinned, idempotency-driven, test-first approach. Artefacts must reinforce it, never weaken it. |

Enforcement is two independent layers, and they cover **different** surfaces:
`.claude/settings.json` deny rules (they do not see arbitrary Bash operands) and the PreToolUse
guard `.claude/hooks/guard.py` (fail-closed; blocks, never approves). Neither alone is sufficient.
Both files plus `.claude/.gitignore` are self-protected: **only the operator changes them.**

## 3. Environment

- Pi 5, 16 GB RAM, active cooling, NVMe SSD (Samsung 980, 1 TB), Raspberry Pi OS Lite 64-bit.
- Laptop: Windows ARM64 (Snapdragon X). Development happens in **WSL2 Ubuntu only**.
- Repo checkout: `/home/micro/src/raspberry-pi-homelab`. Python 3.12, tooling in `.venv`.
- Tool versions in `.venv` must equal the pins in `.pre-commit-config.yaml` (enforced by
  `tests/precommit/test_50_toolchain_version_parity.py`).

## 4. Operating model

- **IaC** — host config, networks and services are defined in code; no manual drift on the Pi.
- **GitOps** — the GitHub repo is the source of truth. The Pi only does `git pull --ff-only` and
  `sudo ./deploy.sh`. Only `main` is ever deployed. Rollback is `git revert` via a branch and PR.
- **Idempotency** — a rerun must never break a working system.
- **Test-first** — no service or job is accepted without tests, static and post-deploy.
- **Determinism** — pinned image versions, never `latest`; digests preferred over tags (not yet
  done, finding F3). Renovate proposes controlled updates; no automerge.
- **Explicit runtime** — Docker Compose only, explicit networks, bind mounts only (no named
  volumes, ADR-0008), explicit port exposure, least privilege.
- **Hardening** — non-root, `cap_drop`, read-only filesystems where possible, healthchecks.
  Documented exception: cadvisor runs privileged (Pi 5 necessity).
- **Secrets** — host-only `/etc/raspberry-pi-homelab/monitoring.env` (`root:root 600`), loaded via
  `docker compose --env-file` in `deploy.sh`. A repo-root `.env` is refused (ADR-0007).
- **Naming** — compose project `<org>-<site>-<env>-<stack>`, e.g. `homelab-home-prod-mon`;
  short service names without prefixes; host data under `/srv/data/stacks/<stack>/<service>/`.
- **Docs** — English only, Markdown, ADRs for decisions that constrain later work.

## 5. Repository map

```text
.github/workflows/ci.yml   jobs doctor / precommit / tests, Python 3.12
.pre-commit-config.yaml    hygiene fixers, yamllint, shellcheck, pytest, ruff, renovate validator
Makefile                   single orchestration entrypoint, platform guards (_guard-wsl, _guard-pi)
deploy.sh                  Pi-only, root, idempotent GitOps deploy
renovate.json5             self-hosted Renovate via Docker in WSL, docker-compose manager only
stacks/monitoring/         the implemented stack (compose + configs + Grafana provisioning)
stacks/core/docker/        daemon.json, GitOps-managed (no core compose stack yet)
scripts/                   backup, grafana, host, host-runtime, network, renovate, tests
tests/                     precommit, guards, doctor, postdeploy, _lib
docs/                      architecture/adr/, operations/, services/, monitoring.md
Todo.txt                   German working backlog        ChatGPTHint.txt  original operating model
```

Deviations from `ChatGPTHint.txt` §8.1: `_shared/` and `victorialogs/victorialogs.yml` do not
exist; `vector/` was added. The map above is the reality.

## 6. Stack status

| Stack | State |
|---|---|
| monitoring | **implemented** — VictoriaMetrics, vmagent, vmalert, VictoriaLogs, Vector, Alertmanager, Grafana, node-exporter, cAdvisor |
| backup | **in progress** — ADR-009, public-key GPG model, scripts exist, **no tests yet** (F9) |
| core (Traefik + Let's Encrypt) | planned, roadmap stage R3 |
| apps (Stirling PDF, AdGuard Home, Home Assistant) | planned, roadmap stage R4 |

## 7. Commands

**Claude may run** — read-only, no side effects. Verify with `git status --porcelain --ignored`
before and after; any difference is a C2 violation and must be reported.

```bash
export PYTHONDONTWRITEBYTECODE=1
.venv/bin/ruff check --no-fix --no-cache .
.venv/bin/ruff format --check --no-cache .
.venv/bin/yamllint -s .
git ls-files '*.sh' | xargs -r .venv/bin/shellcheck -x
.venv/bin/python -m pytest -p no:cacheprovider --strict-markers -q tests/precommit -m precommit
.venv/bin/python -m pytest -p no:cacheprovider --strict-markers -q tests \
  -m "not postdeploy" --ignore=tests/postdeploy --ignore=tests/precommit
make doctor        # also make doctor-strict
git status | diff | log | show | ls-files | check-ignore | rev-parse
```

**Operator only** — these write files, touch the Pi, or change history:
`make precommit`, `test`, `check`, `ci`, `ci-*`, `venv`, `hooks`, `format`, `ruff-fix`,
`postdeploy`, `host-*`, `backup*`, `restore`, `renovate*`; `pre-commit`; `deploy.sh`; `sudo`;
every script under `scripts/host/`, `scripts/host-runtime/`, `scripts/network/`; `git commit`,
`push`, `tag`, `merge`, `rebase`, `reset`; `gh`; `gpg`; `docker` beyond `compose config`,
`version`, `info`, `ps`, `images`.

`.venv` must already exist. Never create or update it — `make venv` runs `pip install -U pip`.

## 8. Delivery model

One feature at a time, delivered in small increments, each with its own tests (D1).

- One feature = one short-lived branch off `main` (`feat/`, `fix/`, `chore/`, `docs/`).
  Increments are commits on it. The branch is deleted after merge.
- Tests are written **before or with** the implementation, never after: static tests in
  `tests/precommit` or `tests/guards`, runtime behaviour in `tests/postdeploy`.
- Every increment leaves the system deployable. A split that creates an undeployable
  intermediate state is not allowed.
- Gate before commit: Claude runs the read-only set in §7, the operator runs `make ci`.
  **Validate first, commit afterwards.**
- Claude proposes a Conventional Commit message and a PR title/description. The operator reviews
  the diff, commits, pushes, opens the PR, merges after CI is green, and deploys on the Pi.
- An increment is **done** only when: CI green, deploy succeeded, postdeploy green, increment log
  updated. If deploy or postdeploy fails, no new increment starts.
- An increment that changes persistent data, host secrets, ports, UFW rules, Docker networks or
  host configuration must also update the backup inventory, `.env.example`, the reconciliation
  scripts and their postdeploy checks, the network/firewall docs, and the Renovate rules.

Current roadmap stage: **R0** (this transition). Then R1 review → R2 backup → R3 core stack →
R4 app stacks.

## 9. Where to look things up

| Topic | File |
|---|---|
| Transition plan, decisions, findings F1–F25, guard design, test matrix | `.claude/ClaudeTransition.md` |
| How to work with Claude here, how to verify the safety set-up | `.claude/readme_claude.md` |
| Topic rules, skills, subagents | `.claude/rules/`, `.claude/skills/`, `.claude/agents/` *(from Phase 3)* |
| Architecture decisions | `docs/architecture/adr/` — ADR-0007 secrets, ADR-0008 bind mounts, ADR-009 backup |
| Operations | `docs/operations/` — `DevWorkflow.md`, `git-branch-workflow.md`, `runtime-updates.md`, `BackupVerifyRestore.md`, `GPG_config_for_backup_encryption.md`, `renovate.md` |
| Monitoring | `docs/monitoring.md`, `docs/services/` |
| Open work | `Todo.txt` (German) |
| Original operating model | `ChatGPTHint.txt` — historical, superseded by this file where they differ |

## 10. Working agreements

- **Plan first.** Propose the approach, wait for approval, then write. One phase or increment at a
  time.
- **Cite file paths** for every claim about the repository. If it is not in a file, say so.
- **Never guess versions, names or paths.** Read them. An unverified version pin is a defect.
- **Ask when ambiguous** rather than assuming — but do everything that does not depend on the
  answer first.
- **Report failures verbatim.** Quote the actual output. Never report a step as done when it was
  skipped or blocked.
- **Distinguish measured from assumed.** Say which one a statement is.
- If a guard or deny rule blocks something, that is a result to report, not an obstacle to route
  around. Never weaken the guard to get work done.
