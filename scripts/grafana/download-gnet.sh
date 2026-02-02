#!/usr/bin/env bash
set -euo pipefail

require() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: missing tool: $1" >&2; exit 2; }; }
require jq
require curl

# Prefer target layout
DASH_ROOT_DEFAULT="stacks/monitoring/grafana/dashboards"
if [[ ! -d "$DASH_ROOT_DEFAULT" ]]; then
  DASH_ROOT_DEFAULT="monitoring/grafana/dashboards"
fi

MANIFEST="${1:-${DASH_ROOT_DEFAULT}/manifest.json}"
BASE_URL="https://grafana.com/api/dashboards"
STATE_FILE="${DASH_ROOT_DEFAULT}/.gnet-revisions.json"

if [[ ! -f "$MANIFEST" ]]; then
  echo "ERROR: manifest not found: $MANIFEST" >&2
  exit 2
fi

mkdir -p "$(dirname "$STATE_FILE")"
if [[ ! -f "$STATE_FILE" ]]; then
  echo '{}' > "$STATE_FILE"
fi

latest_revision() {
  local id="$1"
  local rev
  rev="$(
    curl -fsSL "${BASE_URL}/${id}/revisions" | jq -r '
      (.[0].revision // .items[0].revision // .revisions[0].revision // empty)
    ' 2>/dev/null || true
  )"
  [[ -n "${rev:-}" && "$rev" != "null" ]] || rev="1"
  echo "$rev"
}

get_state_rev() {
  local id="$1"
  jq -r --arg id "$id" '.[$id] // empty' "$STATE_FILE"
}

set_state_rev() {
  local id="$1" rev="$2"
  local tmp
  tmp="$(mktemp)"
  jq --arg id "$id" --argjson rev "$rev" '.[$id] = $rev' "$STATE_FILE" > "$tmp"
  mv "$tmp" "$STATE_FILE"
}

count="$(jq -r '.dashboards | length' "$MANIFEST")"
if [[ "$count" -eq 0 ]]; then
  echo "Nothing to download (manifest dashboards empty)."
  exit 0
fi

jq -c '.dashboards[]' "$MANIFEST" | while read -r item; do
  folder="$(jq -r '.folder' <<<"$item")"
  id="$(jq -r '.gnet_id' <<<"$item")"
  filename="$(jq -r '.filename' <<<"$item")"

  out_dir="${DASH_ROOT_DEFAULT}/${folder}"
  mkdir -p "$out_dir"

  remote_rev="$(latest_revision "$id")"
  local_rev="$(get_state_rev "$id" || true)"

  if [[ -n "${local_rev:-}" && "$local_rev" == "$remote_rev" ]]; then
    echo "Skip: gnet=${id} already at rev=${remote_rev}"
    continue
  fi

  echo "Download: gnet=${id} rev=${remote_rev} -> ${out_dir}/${filename}"
  tmp="$(mktemp)"
  curl -fsSL "${BASE_URL}/${id}/revisions/${remote_rev}/download" -o "$tmp"

  jq -e . "$tmp" >/dev/null
  mv "$tmp" "${out_dir}/${filename}"
  set_state_rev "$id" "$remote_rev"
done

echo "Done. State saved to ${STATE_FILE}"
