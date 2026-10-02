#!/usr/bin/env bash
#
# Print the counts of pytest's final summary line, read from stdin (F56):
#   "======= 98 passed, 4 skipped in 18.23s =======" -> "98 passed, 4 skipped"
# Exit 1 and print nothing when the input holds no summary line.
#
# Pure: stdin to stdout, no side effects. deploy.sh's run_postdeploy_tests feeds it the output of
# `make postdeploy` and logs the result (tests/guards/test_64_postdeploy_summary.py).

set -euo pipefail

# Section headers (`=== PASSES ===`, `=== short test summary info ===`) share the form; only a
# line that starts with a count and ends with the duration is a summary.
line="$(grep -E '^=+ [0-9]+ [a-z]+.* in [0-9.]+s( \([0-9:]+\))? =+$' | tail -n 1 || true)"
[[ -n "$line" ]] || exit 1

line="${line#"${line%%[0-9]*}"}" # drop the leading "=== "
echo "${line% in *}"             # drop " in <n>s ... ==="
