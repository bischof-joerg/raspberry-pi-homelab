---
paths:
  - "tests/**"
---

# Tests

Four layers, each with its own marker and its own moment of truth. Tests are written **before or
with** the implementation, never afterwards.

| Directory | Marker | Runs where | Asserts |
|---|---|---|---|
| `tests/precommit` | `precommit` | WSL + CI, static | repo-level contracts: no tracked secrets, valid JSON/YAML, compose config parses, toolchain parity |
| `tests/guards` | *(none)* | WSL + CI, static | invariants that must never regress, e.g. no Prometheus artefacts, compose contract |
| `tests/doctor` | `doctor` | WSL + CI | tooling and config sanity |
| `tests/postdeploy` | `postdeploy` | **Pi only**, after deploy | runtime truth: containers healthy, ports reachable, UFW effective, targets UP, alerts flowing |

## MUST

- **Register the marker in `pyproject.toml` before using it.** `addopts` carries
  `--strict-markers`, so an unregistered marker is an error, not a warning.
- **Put the test in the layer that matches when it can fail.** A check that needs a running
  container is `postdeploy`, never `precommit`.
- **Never let a test write into the repository.** Use `tmp_path`. A test that leaves a file behind
  breaks the read-only gate's side-effect check and pollutes every later run.
- **Make the failure message actionable**: what was expected, what was found, and the fix. The
  existing suite uses a `❌` prefix plus a `Fix:` line — follow it.
- **Reuse the helpers** instead of re-implementing them: `tests/_helpers.py` (`REPO_ROOT`, `run`),
  `tests/_lib/compose.py`, `tests/_lib/http.py`, `tests/_lib/paths.py`, and `tests/conftest.py`.
- **Name files `test_<NN>_<topic>.py`** with a two-digit ordering prefix, matching the existing
  numbering in each directory.

## SHOULD

- Prefer one assertion per behaviour with a clear name over a long test with many asserts.
- Skip with a message that says *why* on a platform where the test cannot apply, rather than
  passing vacuously.
- When a rule in this repo is worth enforcing, enforce it with a test — that is how F21 became
  `tests/precommit/test_50_toolchain_version_parity.py`.

## Traps in this repo

- `addopts` contains `--maxfail=1`, so a run stops at the first failure. A green tail does not mean
  the rest passed — check the count.
- `addopts` also contains `-m "not postdeploy"` and `testpaths = ["tests"]`. Passing an explicit
  path overrides `testpaths` but **not** the marker filter.
- `make precommit` runs `pytest tests/precommit -m precommit`, so a test in that directory marked
  `lint` is silently deselected — that is F23, and it is currently hiding a real failure in
  `test_15_json_valid.py` (F25). Check the marker before assuming a test runs.
- `make test` ignores `tests/precommit` entirely.

## Backup has no tests yet

ADR-009 DD-012 requires tests before backup scripts are accepted; none exist (F9). Any work in
`scripts/backup/` must close this gap in the same increment — see `backup-restore.md`.

## Sources

`pyproject.toml` `[tool.pytest.ini_options]`, `Makefile`, `tests/`,
`docs/architecture/adr/ADR-009-backup-verify-restore.md`.
