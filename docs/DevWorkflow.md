# Development Workflow

## 1. Operating Model Overview

This project follows a strict GitOps + IaC model:

1. All changes are developed and validated on **WSL**
2. All quality gates must pass locally (`make ci`)
3. Code is pushed to GitHub
4. GitHub Actions runs the `ci` workflow
5. The Raspberry Pi only:
    - pulls from Git
    - runs `sudo ./deploy.sh`
6. No manual drift is allowed on the Pi

The Raspberry Pi is a **deploy target only** --- never a development
environment.

------------------------------------------------------------------------

## 2. Local Development (WSL)

All development happens inside WSL (Ubuntu).

### 2.1 Tooling Model

- Python virtual environment: `.venv`
- Dev dependencies: `requirements-dev.txt`
- No production Python dependencies exist
- Makefile is the **single orchestration entrypoint**

------------------------------------------------------------------------

### 2.2 Bootstrap

First-time setup:

``` bash
make venv
```

This:

- creates `.venv`
- installs `requirements-dev.txt`
- installs pytest, ruff, yamllint, pre-commit etc.

------------------------------------------------------------------------

## 3. Local Quality Gates

There are three logical test layers.

------------------------------------------------------------------------

### 3.1 Precommit Gate (Fast Developer Feedback)

``` bash
make precommit
```

This executes:

1. `pre-commit run --all-files`
    - ruff
    - ruff-format
    - yamllint
    - shellcheck
    - repo policy hooks
2. `pytest tests/precommit -m precommit`

Purpose:

- Fast
- Deterministic
- No Docker runtime
- No network dependency

This should be run before every push.

------------------------------------------------------------------------

### 3.2 Unit / Integration Tests (No Postdeploy)

``` bash
make test
```

Runs:

- All pytest tests
- Excludes:
  - `tests/postdeploy`
  - `tests/precommit`

These tests may validate:

- Compose configuration
- Repo policies
- Static validation logic
- Config structure correctness

They must pass before pushing.

------------------------------------------------------------------------

### 3.3 Full Local Gate (Recommended Before Push)

``` bash
make ci
```

This runs in order:

1. `make ci-doctor`
2. `make ci-precommit`
3. `make ci-tests`

Equivalent to:

``` bash
make doctor
make precommit
make test
```

If this passes locally, GitHub CI should pass.

------------------------------------------------------------------------

## 4. Git Workflow on WSL

Typical developer flow:

``` bash
git status
git add .
git commit -m "feat: ..."
make ci
git push
```

If `make ci` fails:

- fix issues locally
- re-run `make ci`
- only push when green

------------------------------------------------------------------------

## 5. GitHub CI (Single Workflow: ci.yml)

GitHub runs **one workflow only**:

`.github/workflows/ci.yml`

It contains three parallel jobs:

| Job        | Purpose                          |
|------------|----------------------------------|
| doctor     | Repository & config integrity    |
| precommit  | Lint + policy + tests/precommit  |
| tests      | Unit/integration (no postdeploy) |


All jobs:

- use Python 3.12
- create `.venv`
- cache `.venv`
- cache `~/.cache/pre-commit`

The workflow runs:

``` bash
make ci-doctor
make ci-precommit
make ci-tests
```

This guarantees parity between:

- WSL
- GitHub CI

------------------------------------------------------------------------

## 6. Raspberry Pi Deployment Workflow

The Pi is not a development machine.

### 6.1 Standard Deploy

``` bash
cd ~/iac/raspberry-pi-homelab
git pull
sudo ./deploy.sh
```

The deploy script:

- pulls images
- applies config-hash mechanism
- recreates affected services
- runs postdeploy tests

------------------------------------------------------------------------

### 6.2 Postdeploy Tests (Manual Invocation)

``` bash
make postdeploy
```

Only valid on the Pi.

These tests validate:

- Running containers
- Health checks
- Endpoints reachable
- Metrics ingestion
- Alert pipeline functionality
- UFW effectiveness

------------------------------------------------------------------------

## 7. Deterministic Config Deploy (Config Hash Mechanism)

Certain services mount configuration directly from Git.

Because Docker does not detect file content changes reliably, a hash
mechanism is used.

During deploy:

- A SHA-256 hash over relevant config files is computed
- Exported as `MONITORING_CONFIG_HASH`
- Injected as container label:

``` yaml
labels:
  - "homelab.config-hash=${MONITORING_CONFIG_HASH:-unset}"
```

If configuration changes:

- label changes
- only affected services are recreated
- no global `--force-recreate` needed

This guarantees:

- deterministic deploys
- scoped restarts
- idempotency

------------------------------------------------------------------------

## 8. Failure Handling

### If CI fails

- Fix locally
- Re-run `make ci`
- Push again

### If Deploy fails

On Pi:

``` bash
docker compose -f stacks/monitoring/compose/docker-compose.yml ps -a
docker compose -f stacks/monitoring/compose/docker-compose.yml logs --tail=200
```

Rollback:

``` bash
git log --oneline
git revert <commit>
git pull --rebase
sudo ./deploy.sh
```

------------------------------------------------------------------------

## 9. Guardrails (Non-Negotiable)

- No secrets in Git
- No `.env` committed
- No manual changes on Pi
- No manual container modifications
- No runtime drift
- All config defined in Git

------------------------------------------------------------------------

## 10. Environment Summary

| Environment      | Purpose                           |
|------------------|-----------------------------------|
| WSL              | Development + local CI equivalent |
| GitHub Actions   | Automated CI gate                 |
| Raspberry Pi     | Deploy target only                |

------------------------------------------------------------------------

## 11. Philosophy

- Failing fast \> partial success
- Deterministic deploys \> implicit behavior
- Git is source of truth
- CI parity with local environment
- Idempotency is mandatory
