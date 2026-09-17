# Development Workflow

End-to-end operating model: environments, change lifecycle, quality gates, CI, deployment,
failure handling.

Git mechanics (branch names, commit messages, pull requests, merge method, rollback commands,
Git troubleshooting) are defined **only** in [git-branch-workflow.md](git-branch-workflow.md).

------------------------------------------------------------------------

## 1. Operating Model Overview

This project follows a strict GitOps + IaC model:

1. All changes are developed and validated on **WSL**.
2. All quality gates pass locally (`make ci`) **before** a commit is created.
3. Changes reach `main` only through a pull request with green GitHub CI.
4. The Raspberry Pi only:
    - pulls `main` from Git (`git pull --ff-only`)
    - runs `sudo ./deploy.sh`
5. No manual drift is allowed on the Pi.

The Raspberry Pi is a **deploy target only** --- never a development environment.

------------------------------------------------------------------------

## 2. Change Lifecycle

| # | Rule |
|---|---|
| 1 | Exactly one feature is in progress at a time. |
| 2 | A feature is split into small increments; each increment is one commit. |
| 3 | Every increment leaves the system deployable and ships with matching tests (static tests in `tests/precommit` or `tests/guards`, runtime tests in `tests/postdeploy`). |
| 4 | `make ci` passes before each commit. |
| 5 | A feature is done only when CI is green, the change is merged into `main`, deployed on the Pi, and postdeploy tests are green. |
| 6 | If deploy or postdeploy fails, no new increment starts until the failure is fixed or rolled back. |

Flow:

```text
WSL: branch → implement increment + tests → make ci → commit → push
GitHub: pull request → CI green → merge into main
Pi: git pull --ff-only → sudo ./deploy.sh (runs postdeploy)
```

Commands for each Git step: [git-branch-workflow.md](git-branch-workflow.md) section 5.

------------------------------------------------------------------------

## 3. Local Development (WSL)

All development happens inside WSL (Ubuntu).

### 3.1 Tooling Model

- Python virtual environment: `.venv`
- Dev dependencies: `requirements-dev.txt` (lint tools pinned to the revisions in
  `.pre-commit-config.yaml`, enforced by `tests/precommit/test_50_toolchain_version_parity.py`)
- No production Python dependencies exist
- Makefile is the **single orchestration entrypoint**

### 3.2 Bootstrap

First-time setup:

``` bash
make venv
```

This:

- creates `.venv` if missing
- upgrades pip
- installs `requirements-dev.txt` (pytest, ruff, shellcheck-py, yamllint, pre-commit, ...)

Note: every quality-gate target (`make precommit`, `make test`, `make ci`, `make ci-*`) depends on
`make venv`, so the venv is refreshed implicitly.

------------------------------------------------------------------------

## 4. Local Quality Gates

There are three logical test layers. `make ci` combines them and is **mandatory before every
commit**.

### 4.1 Precommit Gate

``` bash
make precommit
```

This executes:

1. `pre-commit run --all-files --show-diff-on-failure`
    - hygiene fixers (trailing whitespace, end of file) and checks (YAML, JSON, merge conflicts, large files)
    - yamllint
    - shellcheck
    - pytest `-m precommit` hook
    - ruff (`--fix`) and ruff-format
    - Renovate config validation (runs a Renovate container via Docker)
2. `pytest tests/precommit -m precommit`

Properties:

- fast, no Pi runtime required
- **may modify files** (fixers, `ruff --fix`, `ruff format`): review `git status` afterwards
- requires Docker for the Renovate validator and Compose-related tests

### 4.2 Unit / Integration Tests (No Postdeploy)

``` bash
make test
```

Runs all pytest tests excluding:

- `tests/postdeploy`
- `tests/precommit`

These tests may validate compose configuration, repo policies, static validation logic, and
config structure.

### 4.3 Full Local Gate

``` bash
make ci
```

This runs in order:

1. `make ci-doctor`
2. `make ci-precommit`
3. `make ci-tests`

Equivalent to `make doctor` (strict), `make precommit`, `make test`.

If this passes locally, GitHub CI should pass.

------------------------------------------------------------------------

## 5. GitHub CI (Single Workflow: ci.yml)

GitHub runs **one workflow only**: `.github/workflows/ci.yml`

Triggers: every pull request and every push to `main`.

It contains three parallel jobs:

| Job (display name)                        | Make target       | Purpose                          |
|-------------------------------------------|-------------------|----------------------------------|
| `doctor (strict)`                         | `make ci-doctor`  | Repository & config integrity    |
| `precommit (hooks + tests/precommit)`     | `make ci-precommit` | Lint + policy + tests/precommit |
| `tests (unit/integration, no postdeploy)` | `make ci-tests`   | Unit/integration (no postdeploy) |

All jobs:

- use Python 3.12
- run `make venv` (with `.venv` cached by `requirements-dev.txt` hash)
- precommit job additionally caches `~/.cache/pre-commit`

This keeps WSL and GitHub CI on the same Make targets. These job checks are the required status
checks for `main` ([git-branch-workflow.md](git-branch-workflow.md) section 7).

------------------------------------------------------------------------

## 6. Raspberry Pi Deployment Workflow

The Pi is not a development machine. Only `main` is deployed.

### 6.1 Standard Deploy

``` bash
cd ~/iac/raspberry-pi-homelab
git status --porcelain      # must be empty
git switch main             # the Pi always stays on main
git pull --ff-only
git log -1 --oneline        # confirm the expected merge commit
sudo ./deploy.sh
```

The deploy script (in order):

- verifies root, repository ownership, and host secrets (`/etc/raspberry-pi-homelab/monitoring.env`)
- reconciles host prerequisites: Docker `daemon.json` (restarts Docker on change), journald read
  access, external Docker networks, data directory permissions
- computes the config hash (section 7)
- pulls images and runs `docker compose up -d`
- runs postdeploy tests (`make postdeploy`)

Not part of deploy: UFW rule reconciliation (`scripts/network/cleanup-ufw.sh`, manual) and host
runtime updates (`make host-*`, see `docs/operations/runtime-updates.md`). UFW state is checked by
postdeploy tests.

### 6.2 Postdeploy Tests (Manual Invocation)

``` bash
make postdeploy
```

Only valid on the Pi.

These tests validate:

- running containers and health checks
- reachable endpoints
- metrics ingestion
- alert pipeline functionality
- Docker networks and UFW effectiveness

------------------------------------------------------------------------

## 7. Deterministic Config Deploy (Config Hash Mechanism)

Certain services mount configuration directly from Git. Because Docker does not detect file
content changes of bind-mounted configs, a hash mechanism is used.

During deploy:

- a SHA-256 hash over a defined list of config files is computed
- exported as `MONITORING_CONFIG_HASH`
- injected as container label:

``` yaml
labels:
  - "homelab.config-hash=${MONITORING_CONFIG_HASH:-unset}"
```

If a hashed file changes, the label changes and Compose recreates the services that carry the
label, without a global `--force-recreate`.

Known limitation (tracked for review): the hashed file list does not yet cover all mounted
configuration files, and not all config-mounting services carry the label. Changes outside the
hashed set may require a manual recreate until this is fixed.

------------------------------------------------------------------------

## 8. Failure Handling

### 8.1 If `make ci` fails locally

- fix the issue on the feature branch
- re-run `make ci`
- commit only when green

### 8.2 If CI fails on the pull request

- fix on the same feature branch as a new commit
- `make ci`, push; do not merge until green

### 8.3 If deploy or postdeploy fails on the Pi

Diagnose on the Pi (read-only):

``` bash
docker compose -f stacks/monitoring/compose/docker-compose.yml ps -a
docker compose -f stacks/monitoring/compose/docker-compose.yml logs --tail=200
```

Then either:

- **fix forward**: new increment on a branch → PR → merge → deploy, or
- **roll back**: create the revert in WSL, never on the Pi
  ([git-branch-workflow.md](git-branch-workflow.md) section 8), then pull and deploy on the Pi.

Never commit, revert, rebase or edit files on the Pi.

------------------------------------------------------------------------

## 9. Roles

| Step | Claude (Claude Code in WSL) | Operator |
|---|---|---|
| Plan increment, write tests and code | proposes; edits files within its permitted scope | reviews |
| Local gate | runs non-mutating checks only | runs `make ci` |
| Branch name, commit message, PR text | proposes | creates branch, commits, pushes, opens PR |
| Merge, deploy, rollback | never | performs |
| Access to the Pi | never (no SSH, no deploy, no remote calls) | performs |

Claude's permitted scope and safety rules: `.claude/CLAUDE.md`.

------------------------------------------------------------------------

## 10. Guardrails (Non-Negotiable)

- No secrets in Git (no `.env`, keys, tokens, `.claude/settings.local.json`)
- No manual changes on the Pi
- No manual container modifications
- No runtime drift
- All config defined in Git
- No direct commits or force pushes to `main`

------------------------------------------------------------------------

## 11. Environment Summary

| Environment      | Purpose                                         |
|------------------|-------------------------------------------------|
| WSL              | Development, local CI equivalent, Git commits   |
| GitHub           | Pull requests, CI gate, merge into `main`       |
| Raspberry Pi     | Deploy target only (`main`)                     |

------------------------------------------------------------------------

## 12. Philosophy

- Failing fast > partial success
- Deterministic deploys > implicit behavior
- Git is source of truth
- CI parity with local environment
- Idempotency is mandatory
- Small, tested increments > large changes
