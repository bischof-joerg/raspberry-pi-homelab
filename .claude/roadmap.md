# Roadmap – raspberry-pi-homelab

The living plan for roadmap stages R1–R5: where the work stands, the rules every increment follows,
the open findings by group, and the increment log. `.claude/CLAUDE.md` is always loaded; this file
is read at the start of any work session. The Claude transition (R0) is complete and archived in
`.claude/ClaudeTransition.md` — historical record only, no longer maintained.

## 1. Status

- **Stage:** R1 — review of the implementation and the findings in `.claude/reports/repo-findings.md`.
- **Done in R1:** group a except F26b (its restore test belongs to R3/F9); F48 and F49; F28, the
  first step of group b. See §6 and §7.
- **Next increment:** F46 steps (2) and (3) — make `docs/monitoring.md` stop contradicting the
  compose file, write the ADR for cadvisor's privileged exception (four-digit form per
  `.claude/rules/docs-adr.md`), and a guard with an allowlist of privileged services that cites it.
  Step (4), dropping `privileged`, is a separate, later increment.
- **Then:** F21 and F22 (group h, pulled forward on 2026-09-26): a reproducible toolchain — pinned
  pip, idempotent `make venv`, one source of dev dependencies. Every later increment relies on
  `make ci` as evidence, and today each gate run may upgrade tools within version ranges.
- **Stages re-planned on 2026-09-26:** a new R2 (quality and lifecycle, §9) sits between R1 and
  backup; backup, core and apps moved to R3, R4 and R5.
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
| IN7 | An increment is **done** only when: CI green, deploy succeeded, postdeploy green, increment log updated (§7). |
| IN8 | If deploy or postdeploy fails: no new increment. Either fix forward within the same increment scope or roll back with `git revert` (via branch + PR per IN11/IN12) + pull + deploy. |
| IN9 | Every increment that adds or changes persistent data, host secrets, ports, UFW rules, Docker networks, or host configuration also updates: backup inventory (ADR-009 §4/§5), `.env.example`, reconciliation scripts (`.claude/rules/host-runtime.md`) and their postdeploy checks, network/firewall docs, and Renovate package rules. |
| IN10 | Version pins only (no `latest`); new images go through the pinning rule and Renovate coverage in the same increment. |
| IN11 | One feature = one short-lived branch from current `main` (`feat/…`, `fix/…`, `chore/…`, `docs/…`). Increments are commits on that branch. Branch is deleted after merge. |
| IN12 | Operator pushes the branch and opens a pull request; CI (`ci.yml`, trigger `pull_request`) must be green before merge. Claude proposes PR title and description but does not create the PR (`gh` denied). |
| IN13 | Only `main` is deployed. On the Pi: `git pull --ff-only`, `sudo ./deploy.sh`. Feature branches are never checked out on the Pi. Every merged state must pass IN7. |

Practice established in R1: tests first as a separate commit with `xfail(strict=True)`, verified
with `--runxfail` to fail for the intended reason; the fix commit removes the markers. The log row
of an increment is recorded on a short `docs/` branch after its deploy.

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
```

## 4. Roadmap

| Stage | Feature | Entry criteria | Exit criteria |
|---|---|---|---|
| **R0** | Claude transition (Phases 0–8) | — | **Complete** 2026-09-24; record in `.claude/ClaudeTransition.md` |
| **R1** | Review of the existing implementation, including host/runtime/network reconciliation | R0 done | Every finding re-verified against `main`; decision (ADR) on which host state `deploy.sh` reconciles vs. which stays manual (UFW, network attributes, daemon.json restart policy); each accepted finding fixed or scheduled as its own increment |
| **R2** | Quality and lifecycle: ADRs ↔ rules, dev-environment lifecycle, stack review against the rules, Grafana dashboard lifecycle, documentation (§9) | R1 done | Exit criteria of R2.1, R2d, R2a, R2c and R2b in §9 met |
| **R3** | Backup: finish implementation and tests (ADR-009); then the Pi runtime lifecycle (R3b, §9) | R2 done, or at least the findings affecting backup fixed | `make backup`, `make backup_verify` on the Pi green; fixture tests from ADR-009 §14.2 green in CI; restore dry-run and one non-critical live restore proven (§14.3); open GPG steps (doc step 6 ff.) completed; first increment after that: the Grafana major upgrade (R2c.6); exit criteria of R3b in §9 met |
| **R4** | Core stack: Traefik with automated Let's Encrypt | R3 done (backup covers new state) | `stacks/core/compose/` deployed; valid LE certificates with automatic renewal; existing LAN UIs routed via Traefik; postdeploy tests for routing, TLS, redirects, and cert expiry; backup inventory extended |
| **R5.1** | App stack: Stirling PDF | R4 done | Per-app stack under `stacks/apps/stirling-pdf/`, behind Traefik, tests, docs, Renovate rule enabled |
| **R5.2** | App stack: AdGuard Home | R5.1 done | Same as R5.1 plus DNS-specific tests |
| **R5.3** | App stack: Home Assistant | R5.2 done | Same as R5.1 plus backup of HA data verified by restore test |

Prerequisites to clarify at the start of the respective stage:

- **R4 – Let's Encrypt with a LAN-only Pi:** `rpi-hub.fritz.box` is not a publicly registered domain, so no public CA can validate it. HTTP-01 needs public reachability; DNS-01 proves control via a TXT record and only makes sense for automation if the DNS provider offers an API (https://letsencrypt.org/docs/challenge-types/). For a LAN-only Pi, DNS-01 with a public domain is the likely path. Open: which domain (`Todo.txt` mentions an existing domain at WebHostOne), whether that provider is supported by Traefik's ACME DNS providers (not yet verified), and how local name resolution for the public names is done (AdGuard rewrites in R5.2, or FritzBox DNS).
- **R4 – Firewall:** Traefik adds inbound 80/443 (and possibly removes direct LAN exposure of 3000/9428). This depends on the R1 decision on UFW reconciliation (F15, F45).
- **R4 – deploy.sh:** currently deploys only the monitoring stack. Multi-stack deployment (order, per-stack env files, per-stack config hash) is an ADR decision at the start of R4.
- **R5.2 – AdGuard Home:** needs port 53 on the Pi and a decision on how clients use it (FritzBox DNS setting); conflicts with any existing local DNS listener must be checked on the Pi.
- **R5.3 – Home Assistant:** device discovery commonly relies on host networking, which conflicts with the explicit-network rule. Needs an ADR exception or an alternative before implementation.

## 5. Decisions in force

Full text in `.claude/ClaudeTransition.md` §2 (archive).

| ID | Decision |
|---|---|
| E6 | Artefacts and docs in English (`Todo.txt` stays German). |
| E2 | Claude Code in WSL, plan mode, confirmation per write step. |
| Q1 | C1/C2 (write only in `.claude/`) were transition-only and retired in Phase 8; C3–C6 are permanent. |
| Q7, Q8 | Guard: Python stdlib, `shlex` tokenising; unclassified Bash commands pass to deny rules and plan-mode approval. |
| D1 | One feature at a time in small, tested increments; the operator commits, pulls on the Pi and deploys. |
| D2 | Roadmap R0 → R1 → R2 → R3 → R4 → R5 (§4); the original R2–R4 became R3–R5 when R2 was inserted (operator, 2026-09-26). |
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
| b | Docker socket and privilege | F46, F30, F34 | F28 | Host-root equivalence. Next: F46 (2)+(3) docs/ADR/allowlist, then F46 (4) drop `privileged` |
| c | LAN exposure and firewall contract | F45, F31, F42, F15 | — | F45 needs a Pi-side measurement first; decides F15 |
| d | Config hash that works | F1, F2, F29, F13 | — | Makes every later config change actually deploy; candidate: `up --renew-anon-volumes` (F48) |
| f | Compose contract guard test | F41, F7, F33, F27, F32, F38 | — | One test file becomes the home of all hardening checks |
| e | Host reconciliation ADR | F16, F17, F18, F43, F19, F20 | — | Needs an ADR decision before code (R1 exit criterion) |
| g | Supply chain | F3, F24, F44 | F37 | Digest pins together; F37 went with F8; F4 moved to R2d |
| h | Toolchain and dead tests | F21, F22, F23, F25, F47, F11 | F49 | F21 + F22 pulled forward (next after F46 (2)+(3)); rest low risk, quick |
| R2d | Dev-environment lifecycle | F4, F50 | — | Stage R2, directly after R2.1 (§9) |
| R2b | Documentation | F5, F6, F12 | — | Stage R2, §9 — the former R1 group i, moved 2026-09-26 |
| R3 | Backup tests | F9 | — | Stage R3 (was R2 before 2026-09-26) |
| R3b | Pi runtime lifecycle | F51, F52, F53, F54, F55 | — | Stage R3, after backup, §9 |

Closed without a group: F10, F14, F40. Groups a–h belong to R1; the others name their stage.

## 7. Increment log

R1 onwards, newest first. R0 rows stay in `.claude/ClaudeTransition.md` §10.4 (archive).

| Increment | Date | Commit | CI | Deploy + postdeploy | Notes |
|---|---|---|---|---|---|
| Roadmap document | 2026-09-26 | pending | pending | no runtime effect | `.claude/roadmap.md` created; `ClaudeTransition.md` archived; §3.6 index duplicate dropped, `check_findings.py` checks the §6 group table instead. Same branch: stage R2 inserted (§9), R2–R4 renumbered to R3–R5, group i → R2b, F4 → R2d, F21/F22 pulled forward, findings F50–F55 added. |
| F28 cadvisor socket :ro | 2026-09-25 | `1a2f26c` (tests), `b447602` (fix); merge `f2a3172` (PR #24) | green | deploy: done twice, postdeploy green (62 passed, 4 skipped) | cadvisor recreated with the socket `:ro`; named container metrics read live from the fresh cadvisor, mount `RW=false`. Near-zero security gain alone (privileged stays; `:ro` does not restrict the API) — F46 step (1) done. Same deploy proved F49: its pull changed `tests/postdeploy/test_25`, `find ! -user admin` empty right after, next deploy `repo-ownership: OK` → F49 addressed. |
| F49 no-bytecode | 2026-09-25 | `dca1145` (tests), `05eee19` (fix); merge `19c76ab` (PR #22) | green | deploy: done twice, postdeploy green, both `repo-ownership: OK`; `find ! -user admin` empty | Fix in `scripts/tests/run-tests.sh` (export + explicit in the sudo env call). **Not yet proof:** this pull changed no module that postdeploy imports, so nothing would have been recompiled anyway. F49 stays partly until a pull changes `tests/postdeploy`. |
| F48 guard (host-wide no-volume check) | 2026-09-25 | `785dee5` (tests), `133b615` (helper); merge `acdd38b` (PR #20) | green | deploy: done, postdeploy: green (60 passed, 4 skipped) incl. `test_host_has_no_docker_volumes` | Variant a (operator): any Docker volume on the Pi fails; parsing proven by guards `test_40` (strict xfail first). ADR-0008 gained an Enforcement section. F48 addressed. The same deploy confirmed F49: two root-owned `.pyc` files for the changed test modules; the next deploy (14:27) logged `repo-ownership: mismatch`. |
| R1.2-fix renderer anon volume | 2026-09-25 | `39c9e8c`; merge `44f09b0` (PR #18) | green | deploy: done, postdeploy: green (59 passed, 4 skipped) after a one-time operator cleanup | `tmpfs: [/alertmanager]` on the renderer. The first redeploy still failed `test_56`: compose carries anonymous volumes over to a recreated container; fixed once with `docker compose rm -s -f -v alertmanager-config-render`, then deploy. Measured: `HostConfig.Tmpfs {"/alertmanager":""}`, bind mounts only. Afterwards three legacy named volumes removed, one held an old SMTP password (F48); `docker volume ls` empty. `repo-ownership` OK at 13:50 — likely cause of the earlier mismatches recorded as F49. R1.2 complete. |
| R1.2 Alertmanager renderer (F36, F8, F37) | 2026-09-25 | `bc37ada` (tests), `bdb6a80` (fix); merge `07b4448` (PR #17) | green | deploy: containers up, **postdeploy failed** — `test_56`: anonymous volume on the renderer from the image's `VOLUME /alertmanager`; 58 other checks passed incl. `test_22` (exit 0, network none) | IN8 fix-forward on `fix/r1-2-renderer-anon-volume`: `tmpfs: [/alertmanager]`, plus an image-VOLUME coverage test. The dangling volume `de74cbca…` is removed by the operator after that deploy. Deploy also logged `repo-ownership: mismatch detected` (cause unknown). |
| R1.1-fix renderer group | 2026-09-25 | `99fcdd7`; merge `2657096` (PR #15) | green | deploy: done, postdeploy: green (58 passed, 4 skipped) | Renderer `0:0` + `group_add 65534`. Measured on the Pi: dir `750 root:nogroup`, file `640 root:nogroup`; second run `init-permissions: skipped (already correct)`. F26, F35, F39 accepted; F26b partly (restore fixture → R2/F9). |
| R1.1 Alertmanager secret mode (F26, F26b, F35, F39) | 2026-09-25 | `5993245` (tests), `bf1693a` (fix); merge `2fdfb10` | green | **deploy failed** — renderer exit 10 (`apk add` cannot chown with primary group 65534 and no `CAP_CHOWN`); alertmanager left `Created`; postdeploy not reached | IN8 fix-forward on `fix/r1-alertmanager-render-group`: renderer `user: "0:0"` + `group_add: ["65534"]`. The fix row follows after its deploy. |

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

## 9. Stage plans R2 and R3b

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
- **Exceptions:** anything a rule tolerates needs an ADR (known: cadvisor `privileged` → F46;
  LAN exposure of 3000/9428 → F42).
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
| R2d.1 | Renovate managers `pip_requirements`, `pre-commit`, `github-actions`; pins in `requirements-dev.txt` and `.pre-commit-config.yaml` move in one PR (the parity test enforces it); no automerge (F4) |
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
| R2b.3 | `docs/monitoring.md`, `docs/services/` | F42, rest of F46 |
| R2b.4 | `docs/architecture/networking-and-firewall-model.md` | outcome of R1 groups c/e |
| R2b.5 | `docs/operations/`: DevWorkflow, git-branch-workflow, runtime-updates (path `~/iac/…`, "Last verified", plan vs script — F55), renovate | F44, F55 |
| R2b.6 | Backup docs and ADR-009, consistency only (content follows in R3) | — |

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
