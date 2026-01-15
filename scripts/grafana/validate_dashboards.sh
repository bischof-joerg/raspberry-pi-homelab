#!/usr/bin/env bash

# Validates Grafana dashboards in the monitoring/grafana/dashboards/ directory.
# Checks include JSON validity, UID uniqueness, and best-effort heuristics for deprecated panels and
# datasource placeholders.
# Usage: ./validate_dashboards.sh

set -euo pipefail

ROOT="monitoring/grafana/dashboards"

# 1) JSON validity
find "$ROOT" -name '*.json' -print0 | xargs -0 -n1 jq -e . >/dev/null

# 2) UID uniqueness check
uids="$(find "$ROOT" -name '*.json' -print0 | xargs -0 -n1 jq -r '.uid // empty')"
dupes="$(printf "%s\n" "$uids" | sort | uniq -d || true)"
if [[ -n "${dupes:-}" ]]; then
  echo "ERROR: duplicate dashboard uids detected:"
  printf "%s\n" "$dupes"
  exit 1
fi

# 3) Angular panels check (best-effort heuristic)
if grep -RIn '"type"[[:space:]]*:[[:space:]]*"angular"' "$ROOT" >/dev/null; then
  echo "WARNING: Angular panels detected (should be replaced):"
  grep -RIn '"type"[[:space:]]*:[[:space:]]*"angular"' "$ROOT" || true
fi

# 4) Prometheus datasource placeholder check (robust)
bad_found=0
find "$ROOT" -name '*.json' -print0 | while IFS= read -r -d '' f; do
  bad="$(jq -r '
    [ .. | objects
      | select(has("datasource"))
      | .datasource
      | select(type=="object" and .type=="prometheus")
      | .uid // "MISSING_UID"
      | select(. != "${DS_PROMETHEUS}")
    ] | unique | .[]
  ' "$f" 2>/dev/null || true)"

  if [[ -n "${bad:-}" ]]; then
    echo "WARNING: $f has prometheus datasource uid not using \${DS_PROMETHEUS}: $bad"
    bad_found=1
  fi
done

# Optional: fail hard if you want strictness
# [[ "$bad_found" -eq 0 ]] || exit 1

echo "OK: dashboards validated"
