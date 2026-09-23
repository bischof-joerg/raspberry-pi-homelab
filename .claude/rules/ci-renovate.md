---
paths:
  - ".github/**"
  - "renovate.json5"
  - ".pre-commit-config.yaml"
---

# CI and Renovate

## CI mirrors `make`, it does not reimplement it

`.github/workflows/ci.yml` has three jobs — `doctor`, `precommit`, `tests` — each on
`ubuntu-latest` with `python-version: "3.12"`, each running `make venv` and then `make ci-doctor`,
`make ci-precommit` or `make ci-tests`.

- **MUST** keep every check reachable through a `make` target. A step that only exists in the
  workflow cannot be run locally, so it will drift.
- **MUST** keep `permissions: contents: read` at workflow level. Widen it only for a specific job
  that provably needs it, never globally.
- **MUST** keep the Python version in step with `pyproject.toml` `requires-python = ">=3.12"`.
- **MUST NOT** add a step that needs a Pi, a secret, or network access to the LAN. CI runs on a
  GitHub runner with no route to `rpi-hub`.
- Postdeploy tests never run in CI — they need the deployed stack. CI runs `-m "not postdeploy"`.

## Toolchain pins must stay in lockstep

`.pre-commit-config.yaml` pins `shellcheck-py` 0.10.0.1, `ruff-pre-commit` 0.14.11,
`yamllint` 1.35.1, and `requirements-dev.txt` pins the same versions exactly. This is enforced by
`tests/precommit/test_50_toolchain_version_parity.py`.

- **MUST** bump `.pre-commit-config.yaml` and `requirements-dev.txt` in the **same commit**.
  The parity test exists precisely to make a one-sided bump fail.
- Known second source of truth: `pyproject.toml` `[project.optional-dependencies].dev` duplicates
  these ranges and is **not** used by `make venv` (F22). Do not treat it as authoritative.

## Renovate

Self-hosted, run via Docker from WSL (`make renovate-check`, `renovate-apply`) — operator only.

- **MUST** pin new images by tag and bring them under a Renovate rule in the same increment.
- **MUST NOT** enable automerge. Updates are proposed, reviewed, tested, then merged by a human.
- Current coverage is the `docker-compose` manager **only**. Unmanaged and therefore drifting:
  GitHub Actions tags (`@v4`/`@v5`), pre-commit hook `rev`s, pip ranges, and the pinned Grafana
  plugin `victoriametrics-logs-datasource@0.24.1` (F4). Adding a manager is an increment of its own.
- `scripts/renovate/validate-config.sh` runs `renovate/renovate:43` by **tag**, while the Makefile
  pins the same image by digest (F24) — inconsistent, and it makes the pre-commit hook need Docker
  and a registry pull.

## Sources

`.github/workflows/ci.yml`, `Makefile`, `.pre-commit-config.yaml`, `requirements-dev.txt`,
`renovate.json5`, `scripts/renovate/validate-config.sh`, `docs/operations/renovate.md`,
`tests/precommit/test_50_toolchain_version_parity.py`. Findings F4, F22, F24.
