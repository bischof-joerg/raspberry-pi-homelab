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

# 4) Prometheus datasource placeholder check (best-effort)
# This is intentionally not "fail hard" because some dashboards rely on default datasource,
# but it gives signal if hardcoded UIDs slip in.
if grep -RIn '"type"[[:space:]]*:[[:space:]]*"prometheus"' "$ROOT" | grep -v '\${DS_PROMETHEUS}' >/dev/null; then
  echo "WARNING: Some prometheus datasource blocks do not use \${DS_PROMETHEUS}."
  grep -RIn '"type"[[:space:]]*:[[:space:]]*"prometheus"' "$ROOT" | head -n 40
fi

echo "OK: dashboards validated"
