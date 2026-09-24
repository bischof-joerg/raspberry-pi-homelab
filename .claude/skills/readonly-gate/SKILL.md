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

The local gate from IN4 in its non-mutating form. **Validate first, commit afterwards.** Since
Phase 8 Claude may also run `make ci` (`CLAUDE.md` §7). Use this skill instead when nothing may be
rewritten: in plan mode, before `make ci` to see the pristine state, or when a fixer rewrite would
blur what the increment changed.

Precondition: `.venv` exists. Never create or update it.

## Run

Two equivalent forms. Choose by permission mode and say which one you used.

**Form A — plan mode (the default here, E2).** Plan mode forbids writing files, `/tmp` included,
so the snapshots stay in shell variables. Variables do not survive between Bash calls, so this
must be **one single Bash call** from `before=` to the comparison:

```bash
export PYTHONDONTWRITEBYTECODE=1
before=$(git status --porcelain --ignored)

.venv/bin/ruff check --no-fix --no-cache .
.venv/bin/ruff format --check --no-cache .
.venv/bin/yamllint -s .
git ls-files '*.sh' | xargs -r .venv/bin/shellcheck -x
.venv/bin/python -m pytest -p no:cacheprovider --strict-markers -q tests/precommit -m precommit
.venv/bin/python -m pytest -p no:cacheprovider --strict-markers -q tests \
  -m "not postdeploy" --ignore=tests/postdeploy --ignore=tests/precommit

after=$(git status --porcelain --ignored)
if [ "$before" = "$after" ]; then echo "OK: no side effects"
else diff <(printf '%s\n' "$before") <(printf '%s\n' "$after"); fi
```

**Form B — outside plan mode.** The snapshots go to `/tmp/claude-gate-*` (the only temp prefix the
guard allows), so the steps may be separate calls:

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

Form A must print `OK: no side effects`; in Form B the final `diff` must be empty. **Any difference
must be reported**, not worked around — it means a supposedly read-only command wrote to the tree. An extra run such as `-m lint` belongs **inside** the before/after
window, otherwise its side effects go unchecked.

`allowed-tools` pre-approves the individual commands. Whether the single compound call of Form A
is covered by those patterns, or triggers a permission prompt, has not been measured. A prompt
there is acceptable; do not widen `allowed-tools` to avoid it (D4-b).

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

State which form (A or B) ran, then per step: pass/fail with counts, the verbatim first failure if
any, and the side-effect result. Do not summarise a failure as "mostly green".
