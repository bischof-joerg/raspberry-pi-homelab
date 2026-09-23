---
name: readonly-gate
description: Run the non-mutating validation gate (ruff, yamllint, ShellCheck, static tests) and prove it changed nothing. Use before proposing a commit.
allowed-tools:
  - Bash(.venv/bin/ruff check --no-fix --no-cache .)
  - Bash(.venv/bin/ruff format --check --no-cache .)
  - Bash(.venv/bin/yamllint -s .)
  - Bash(.venv/bin/python -m pytest *)
  - Bash(xargs -r .venv/bin/shellcheck *)
  - Bash(git ls-files *)
  - Bash(git status --porcelain --ignored*)
  - Bash(diff /tmp/claude-gate-*)
---

# Read-only validation gate

The local gate from IN4: Claude runs this, the operator runs `make ci`. **Validate first, commit
afterwards.** Every mutating equivalent (`make precommit`, `check`, `ci`, `format`, `ruff-fix`) is
operator-only because it writes files — see `CLAUDE.md` §7.

Precondition: `.venv` exists. Never create or update it.

## Run

```bash
export PYTHONDONTWRITEBYTECODE=1
git status --porcelain --ignored > /tmp/claude-gate-before.txt

.venv/bin/ruff check --no-fix --no-cache .
.venv/bin/ruff format --check --no-cache .
.venv/bin/yamllint -s .
git ls-files '*.sh' | xargs -r .venv/bin/shellcheck -x
.venv/bin/python -m pytest -p no:cacheprovider --strict-markers -q tests/precommit -m precommit
.venv/bin/python -m pytest -p no:cacheprovider --strict-markers -q tests \
  -m "not postdeploy" --ignore=tests/postdeploy --ignore=tests/precommit

git status --porcelain --ignored > /tmp/claude-gate-after.txt
diff /tmp/claude-gate-before.txt /tmp/claude-gate-after.txt && echo "OK: no side effects"
```

## Acceptance

The final `diff` must be empty. **Any difference is a C2 violation and must be reported**, not
worked around — it means a supposedly read-only command wrote to the tree.

## Reading the output honestly

- `pyproject.toml` sets `--maxfail=1`, so a run **stops at the first failure**. A short green tail
  does not mean the rest passed. Quote the counts.
- `addopts` also carries `-m "not postdeploy"`. Postdeploy tests never run here; they need the Pi.
- Tests marked `lint` are deselected by `-m precommit`. `tests/precommit/test_15_json_valid.py` is
  currently failing on `.vscode/settings.json` and nobody sees it (F23/F25). If you want the full
  picture, run `-m lint` separately and say that you did.
- ShellCheck must come from `.venv` (0.10.0.1, matching the pre-commit pin). The system ShellCheck
  is 0.9.0 and disagrees (F21).

## Report

State per step: pass/fail with counts, the verbatim first failure if any, and the side-effect diff
result. Do not summarise a failure as "mostly green".
