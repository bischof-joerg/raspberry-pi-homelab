# Roadmap – raspberry-pi-homelab

The living plan for roadmap stages R1–R4: where the work stands, the rules every increment follows,
the open findings by group, and the increment log. `.claude/CLAUDE.md` is always loaded; this file
is read at the start of any work session. The Claude transition (R0) is complete and archived in
`.claude/ClaudeTransition.md` — historical record only, no longer maintained.

## 1. Status

- **Stage:** R1 — review of the implementation and the findings in `.claude/reports/repo-findings.md`.
- **Done in R1:** group a except F26b (its restore test belongs to R2/F9); F48 and F49; F28, the
  first step of group b. See §6 and §7.
- **Next increment:** F46 steps (2) and (3) — make `docs/monitoring.md` stop contradicting the
  compose file, write the ADR for cadvisor's privileged exception (four-digit form per
  `.claude/rules/docs-adr.md`), and a guard with an allowlist of privileged services that cites it.
  Step (4), dropping `privileged`, is a separate, later increment.
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
| **R2** | Backup: finish implementation and tests (ADR-009) | R1 done, or at least the R1 findings affecting backup fixed | `make backup`, `make backup_verify` on the Pi green; fixture tests from ADR-009 §14.2 green in CI; restore dry-run and one non-critical live restore proven (§14.3); open GPG steps (doc step 6 ff.) completed |
| **R3** | Core stack: Traefik with automated Let's Encrypt | R2 done (backup covers new state) | `stacks/core/compose/` deployed; valid LE certificates with automatic renewal; existing LAN UIs routed via Traefik; postdeploy tests for routing, TLS, redirects, and cert expiry; backup inventory extended |
| **R4.1** | App stack: Stirling PDF | R3 done | Per-app stack under `stacks/apps/stirling-pdf/`, behind Traefik, tests, docs, Renovate rule enabled |
| **R4.2** | App stack: AdGuard Home | R4.1 done | Same as R4.1 plus DNS-specific tests |
| **R4.3** | App stack: Home Assistant | R4.2 done | Same as R4.1 plus backup of HA data verified by restore test |

Prerequisites to clarify at the start of the respective stage:

- **R3 – Let's Encrypt with a LAN-only Pi:** `rpi-hub.fritz.box` is not a publicly registered domain, so no public CA can validate it. HTTP-01 needs public reachability; DNS-01 proves control via a TXT record and only makes sense for automation if the DNS provider offers an API (https://letsencrypt.org/docs/challenge-types/). For a LAN-only Pi, DNS-01 with a public domain is the likely path. Open: which domain (`Todo.txt` mentions an existing domain at WebHostOne), whether that provider is supported by Traefik's ACME DNS providers (not yet verified), and how local name resolution for the public names is done (AdGuard rewrites in R4.2, or FritzBox DNS).
- **R3 – Firewall:** Traefik adds inbound 80/443 (and possibly removes direct LAN exposure of 3000/9428). This depends on the R1 decision on UFW reconciliation (F15, F45).
- **R3 – deploy.sh:** currently deploys only the monitoring stack. Multi-stack deployment (order, per-stack env files, per-stack config hash) is an ADR decision at the start of R3.
- **R4.2 – AdGuard Home:** needs port 53 on the Pi and a decision on how clients use it (FritzBox DNS setting); conflicts with any existing local DNS listener must be checked on the Pi.
- **R4.3 – Home Assistant:** device discovery commonly relies on host networking, which conflicts with the explicit-network rule. Needs an ADR exception or an alternative before implementation.

## 5. Decisions in force

Full text in `.claude/ClaudeTransition.md` §2 (archive).

| ID | Decision |
|---|---|
| E6 | Artefacts and docs in English (`Todo.txt` stays German). |
| E2 | Claude Code in WSL, plan mode, confirmation per write step. |
| Q1 | C1/C2 (write only in `.claude/`) were transition-only and retired in Phase 8; C3–C6 are permanent. |
| Q7, Q8 | Guard: Python stdlib, `shlex` tokenising; unclassified Bash commands pass to deny rules and plan-mode approval. |
| D1 | One feature at a time in small, tested increments; the operator commits, pulls on the Pi and deploys. |
| D2 | Roadmap R0 → R1 → R2 → R3 → R4 (§4). |
| Q9 | Short-lived branch per feature, CI on the pull request, only `main` is deployed. |

## 6. R1 plan — findings by group

The report `.claude/reports/repo-findings.md` holds the entries and their status. This table
assigns every finding that is not `addressed` to exactly one group; `.claude/tools/check_findings.py`
enforces that, and that each group here matches the R1 column of the report index. Order: security
first, then the mechanisms other fixes depend on.

| Group | Scope | Open | Done | Why this order / state |
|---|---|---|---|---|
| a | Alertmanager renderer: modes, errors, escaping, determinism | F26b | F26, F35, F36, F8, F39, F48 | Done except F26b's restore fixture test, which needs the R2 harness (F9) |
| b | Docker socket and privilege | F46, F30, F34 | F28 | Host-root equivalence. Next: F46 (2)+(3) docs/ADR/allowlist, then F46 (4) drop `privileged` |
| c | LAN exposure and firewall contract | F45, F31, F42, F15 | — | F45 needs a Pi-side measurement first; decides F15 |
| d | Config hash that works | F1, F2, F29, F13 | — | Makes every later config change actually deploy; candidate: `up --renew-anon-volumes` (F48) |
| f | Compose contract guard test | F41, F7, F33, F27, F32, F38 | — | One test file becomes the home of all hardening checks |
| e | Host reconciliation ADR | F16, F17, F18, F43, F19, F20 | — | Needs an ADR decision before code (R1 exit criterion) |
| g | Supply chain | F3, F4, F24, F44 | F37 | Digest pins + Renovate coverage together; F37 went with F8 |
| h | Toolchain and dead tests | F21, F22, F23, F25, F47, F11 | F49 | Low risk, quick |
| i | Docs | F5, F6, F12 | — | Last, so they describe the fixed state |
| R2 | Backup tests | F9 | — | Roadmap stage R2 |

Closed without a group: F10, F14, F40.

## 7. Increment log

R1 onwards, newest first. R0 rows stay in `.claude/ClaudeTransition.md` §10.4 (archive).

| Increment | Date | Commit | CI | Deploy + postdeploy | Notes |
|---|---|---|---|---|---|
| Roadmap document | 2026-09-26 | pending | pending | no runtime effect | `.claude/roadmap.md` created; `ClaudeTransition.md` archived; §3.6 index duplicate dropped, `check_findings.py` checks the §6 group table instead. |
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
