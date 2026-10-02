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
- `make precommit` runs `pytest tests/precommit -m precommit`, so a test in that directory with
  any other marker is deselected. Four `lint`-marked files sat there unrun until R1.25 (F23, F25).
  `tests/guards/test_63_every_test_runs_in_a_gate.py` now fails on any test that no gate's
  selection collects, and on a registered marker that no test uses.
- `make test` ignores `tests/precommit` entirely.
- A test in `tests/postdeploy` without the `postdeploy` marker is deselected on the Pi, and
  `make ci` never runs that directory — the seven checks of `test_26_docker_socket_proxy.py`
  were lost this way on the first R1.10 deploy. `tests/guards/test_43_postdeploy_markers.py` now
  fails on any unmarked postdeploy test; mark the module with `pytestmark`.
- `make ci`'s pytest pre-commit hook **imports** every module under `tests/postdeploy` before the
  marker filter deselects it. In a tests-first commit, a postdeploy test must therefore not import
  a module the fix commit creates at module level — import it inside the test function, and move
  the import up in the fix commit (R1.18: `ModuleNotFoundError: No module named
  'tests._lib.journald'`).

## Backup has no tests yet

ADR-009 DD-012 requires tests before backup scripts are accepted; none exist (F9). Any work in
`scripts/backup/` must close this gap in the same increment — see `backup-restore.md`.

## Sources

`pyproject.toml` `[tool.pytest.ini_options]`, `Makefile`, `tests/`,
`docs/architecture/adr/ADR-009-backup-verify-restore.md`.
