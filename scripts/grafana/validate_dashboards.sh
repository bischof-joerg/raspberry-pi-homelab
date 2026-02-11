#!/usr/bin/env bash
set -euo pipefail

ROOT="stacks/monitoring/grafana/dashboards"
if [[ ! -d "$ROOT" ]]; then
  ROOT="monitoring/grafana/dashboards"
fi

echo "Starting validation... (ROOT=$ROOT)"

command -v jq >/dev/null 2>&1 || { echo "ERROR: jq missing" >&2; exit 2; }
command -v rg >/dev/null 2>&1 || { echo "ERROR: rg (ripgrep) missing" >&2; exit 2; }

# 1) JSON Syntax
find "$ROOT" -name '*.json' -not -name 'manifest.json' -not -name '.*' -print0 \
  | xargs -0 -n1 jq -e . >/dev/null
echo "✅ JSON syntax is valid."

# 2) UID Uniqueness
uids="$(
  find "$ROOT" -name '*.json' -not -name 'manifest.json' -not -name '.*' -print0 \
    | xargs -0 -n1 jq -r '.uid // empty'
)"
dupes="$(printf "%s\n" "$uids" | sort | uniq -d || true)"
if [[ -n "${dupes:-}" ]]; then
  echo "❌ ERROR: Duplicate UIDs detected:"
  printf "%s\n" "$dupes"
  exit 1
fi

# 3) Title Uniqueness per folder
bad_titles=0
while IFS= read -r -d '' dir; do
  titles="$(
    find "$dir" -maxdepth 1 -name '*.json' -print0 \
      | xargs -0 -n1 jq -r '.title // empty'
  )"
  t_dupes="$(printf "%s\n" "$titles" | sort | uniq -d || true)"
  if [[ -n "${t_dupes:-}" ]]; then
    echo "❌ ERROR: Duplicate titles in [$dir]:"
    printf "%s\n" "$t_dupes"
    bad_titles=1
  fi
done < <(find "$ROOT" -type d -print0)
[[ "$bad_titles" -eq 0 ]] || exit 1

# 4) Datasource Normalization
# 4a) Prometheus Datasource Normalization (ensure pinned DS uid)
bad_ds=0
while IFS= read -r -d '' f; do
  invalid="$(
    jq -r '
      [ .. | objects | select(has("datasource")) | .datasource
        | select(type=="object" and .type=="prometheus" and .uid != "DS_PROMETHEUS") | .uid
      ] | unique | .[]
    ' "$f" 2>/dev/null || true
  )"

  if rg -n '"datasource":\s*"\$\{?DS_PROMETHEUS\}?"' "$f" >/dev/null 2>&1 || [[ -n "${invalid:-}" ]]; then
    echo "❌ ERROR: $f has un-normalized datasource: ${invalid:-"Placeholder string found"}"
    bad_ds=1
  fi
done < <(find "$ROOT" -name '*.json' -not -name 'manifest.json' -not -name '.*' -print0)
[[ "$bad_ds" -eq 0 ]] || exit 1

# 4b) VictoriaLogs Datasource Normalization (ensure pinned DS uid)
bad_vlogs=0
while IFS= read -r -d '' f; do
  invalid_vlogs="$(
    jq -r '
      [ .. | objects | select(has("datasource")) | .datasource
        | select(type=="object" and .type=="victoriametrics-logs-datasource" and .uid != "victorialogs") | .uid
      ] | unique | .[]
    ' "$f" 2>/dev/null || true
  )"

  if rg -n '"datasource":\s*"\$\{?DS_VICTORIALOGS\}?"' "$f" >/dev/null 2>&1 || [[ -n "${invalid_vlogs:-}" ]]; then
    echo "❌ ERROR: $f has un-normalized VictoriaLogs datasource: ${invalid_vlogs:-"Placeholder string found"}"
    bad_vlogs=1
  fi
done < <(find "$ROOT" -name '*.json' -not -name 'manifest.json' -not -name '.*' -print0)
[[ "$bad_vlogs" -eq 0 ]] || exit 1

# 4c) Enforce environment-normalized VictoriaLogs Explorer (gnetId 22759)
# Upstream is Kubernetes-oriented; we normalize it to docker/journald fields and remove broken optional query clause.
bad_22759=0
while IFS= read -r -d '' f; do
  gnet="$(jq -r '.gnetId // empty' "$f" 2>/dev/null || true)"
  [[ "$gnet" == "22759" ]] || continue

  if rg -n 'kubernetes\.' "$f" >/dev/null 2>&1; then
    echo "❌ ERROR: $f (gnetId=22759) still contains kubernetes.* fields after normalization"
    rg -n 'kubernetes\.' "$f" || true
    bad_22759=1
  fi

  if rg -n '\(\$query != "" or 1==1\)' "$f" >/dev/null 2>&1; then
    echo "❌ ERROR: $f (gnetId=22759) still contains broken optional query clause: (\$query != \"\" or 1==1)"
    rg -n '\(\$query != "" or 1==1\)' "$f" || true
    bad_22759=1
  fi
done < <(find "$ROOT" -name '*.json' -not -name 'manifest.json' -not -name '.*' -print0)
[[ "$bad_22759" -eq 0 ]] || exit 1

# 5) Disallow hardcoded instance hostname matchers (GitOps determinism)
if rg -n "instance=~'rpi-hub'|instance=~\"rpi-hub\"" "$ROOT" >/dev/null 2>&1; then
  echo "❌ ERROR: hardcoded instance matcher 'rpi-hub' found in dashboards. Normalize dashboards or patch expressions."
  rg -n "instance=~'rpi-hub'|instance=~\"rpi-hub\"" "$ROOT" || true
  exit 1
fi

echo "✅ All dashboards are valid and normalized."
