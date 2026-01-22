#!/usr/bin/env bash
# Validates dashboards against normalization rules.
set -euo pipefail

ROOT="monitoring/grafana/dashboards"

echo "Starting validation..."

# 1) JSON Syntax
find "$ROOT" -name '*.json' -not -name 'manifest.json' -not -name '.*' -print0 | xargs -0 -n1 jq -e . >/dev/null
echo "✅ JSON syntax is valid."

# 2) UID Uniqueness
uids="$(find "$ROOT" -name '*.json' -not -name 'manifest.json' -not -name '.*' -print0 | xargs -0 -n1 jq -r '.uid // empty')"
dupes="$(printf "%s\n" "$uids" | sort | uniq -d || true)"
if [[ -n "${dupes:-}" ]]; then
  echo "❌ ERROR: Duplicate UIDs detected: $dupes"
  exit 1
fi

# 3) Title Uniqueness per folder
bad_titles=0
while IFS= read -r -d '' dir; do
  titles="$(find "$dir" -maxdepth 1 -name '*.json' -print0 | xargs -0 -n1 jq -r '.title // empty')"
  t_dupes="$(printf "%s\n" "$titles" | sort | uniq -d || true)"
  if [[ -n "${t_dupes:-}" ]]; then
    echo "❌ ERROR: Duplicate titles in [$dir]: $t_dupes"
    bad_titles=1
  fi
done < <(find "$ROOT" -type d -print0)
[[ "$bad_titles" -eq 0 ]] || exit 1

# 4) Datasource Normalization
bad_ds=0
while IFS= read -r -d '' f; do
  invalid="$(jq -r '
    [ .. | objects | select(has("datasource")) | .datasource
      | select(type=="object" and .type=="prometheus" and .uid != "DS_PROMETHEUS") | .uid
    ] | unique | .[]
  ' "$f" 2>/dev/null || true)"

  if grep -E '"datasource":\s*"\$\{?DS_PROMETHEUS\}?"' "$f" >/dev/null || [[ -n "${invalid:-}" ]]; then
    echo "❌ ERROR: $f has un-normalized datasource: ${invalid:-"Placeholder string found"}"
    bad_ds=1
  fi
done < <(find "$ROOT" -name '*.json' -not -name 'manifest.json' -not -name '.*' -print0)
[[ "$bad_ds" -eq 0 ]] || exit 1

echo "✅ All dashboards are valid and normalized."
