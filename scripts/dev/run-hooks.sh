#!/usr/bin/env bash
# scripts/dev/run-hooks.sh - run the pre-commit hooks on tracked AND new, untracked files (WSL/CI).
#
# `pre-commit run --all-files` selects files from `git ls-files`, so a new file met the hooks
# only at commit time (F59). A second run passes the untracked, not-ignored files explicitly.
# That run is skipped when there are none: an empty `--files` makes pre-commit fall back to the
# staged files and stash unstaged changes (pre-commit 3.8.0, commands/run.py:343).
#
# Environment (default in brackets; overridden by tests/guards/test_44_run_hooks.py):
#   PRE_COMMIT [pre-commit]
#
# Runs in the current git working tree. Exit codes: 0 ok, otherwise the failing run's code.
set -euo pipefail

PRE_COMMIT="${PRE_COMMIT:-pre-commit}"

"$PRE_COMMIT" run --all-files --show-diff-on-failure

if [[ -n "$(git ls-files --others --exclude-standard)" ]]; then
  echo "== pre-commit hooks on untracked files (F59) =="
  git ls-files -z --others --exclude-standard |
    xargs -0 -r "$PRE_COMMIT" run --show-diff-on-failure --files
fi
