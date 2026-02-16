#!/usr/bin/env bash
set -euo pipefail

ROOT="stacks/monitoring/grafana/dashboards"
if [[ ! -d "$ROOT" ]]; then
  ROOT="monitoring/grafana/dashboards"
fi

echo "Starting validation... (ROOT=$ROOT)"

command -v jq >/dev/null 2>&1 || { echo "ERROR: jq missing" >&2; exit 2; }
command -v rg >/dev/null 2>&1 || { echo "ERROR: rg (ripgrep) missing" >&2; exit 2; }

slugify_uid() {
  # Mirrors normalize_dashboards.py::slugify_uid
  # input: arbitrary string -> output: [a-z0-9_-]{1,40} (best-effort)
  local s="${1:-}"

  # trim + lowercase
  s="$(printf "%s" "$s" | sed -e 's/^[[:space:]]\+//' -e 's/[[:space:]]\+$//' | tr '[:upper:]' '[:lower:]')"

  # '.' -> '-'
  s="${s//./-}"

  # non [a-z0-9_-] -> '-'
  s="$(printf "%s" "$s" | sed -E 's/[^a-z0-9_-]+/-/g')"

  # collapse multiple '-'
  s="$(printf "%s" "$s" | sed -E 's/-{2,}/-/g')"

  # trim '-' at ends
  s="$(printf "%s" "$s" | sed -E 's/^-+//' | sed -E 's/-+$//')"

  # limit 40 chars
  s="${s:0:40}"

  if [[ -z "$s" ]]; then
    s="dashboard"
  fi

  printf "%s" "$s"
}

expected_uid_for_file() {
  # expected uid = slugify(relpath_without_suffix, "/" -> "-")
  local f="$1"
  local rel
  rel="${f#"$ROOT"/}"
  rel="${rel%.json}"
  rel="${rel//\//-}"
  slugify_uid "$rel"
}

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

# 2b) UID must match deterministic policy (folder + filename)
bad_uid=0
while IFS= read -r -d '' f; do
  uid="$(jq -r '.uid // empty' "$f")"
  if [[ -z "$uid" ]]; then
    echo "❌ ERROR: $f has empty/missing .uid"
    bad_uid=1
    continue
  fi

  exp="$(expected_uid_for_file "$f")"

  # enforce same allowed-regex as python ensure_uid would accept for already-good uids
  if ! [[ "$uid" =~ ^[a-zA-Z0-9_-]{1,40}$ ]]; then
    echo "❌ ERROR: $f has invalid uid (must match ^[a-zA-Z0-9_-]{1,40}$): uid=$uid"
    echo "   Expected (policy): $exp"
    bad_uid=1
    continue
  fi

  if [[ "$uid" != "$exp" ]]; then
    echo "❌ ERROR: UID drift detected in $f"
    echo "   uid      = $uid"
    echo "   expected = $exp"
    bad_uid=1
  fi
done < <(find "$ROOT" -name '*.json' -not -name 'manifest.json' -not -name '.*' -print0)
[[ "$bad_uid" -eq 0 ]] || exit 1

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
