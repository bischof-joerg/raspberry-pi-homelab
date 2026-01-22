#!/usr/bin/env bash

# Downloads Grafana dashboards from Grafana.net based on a manifest file.
# The manifest file specifies dashboard IDs, target folders, and filenames.
# Checks whether dashboards need to be updated based on their latest revision by using a state file .gnet-revisions.json.
# Usage: ./download-gnet.sh [manifest.json]

set -euo pipefail

MANIFEST="${1:-monitoring/grafana/dashboards/manifest.json}"
BASE_URL="https://grafana.com/api/dashboards"
STATE_FILE="monitoring/grafana/dashboards/.gnet-revisions.json"

require() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: missing tool: $1" >&2; exit 2; }; }
require jq
require curl

# Initialize state file if missing
if [[ ! -f "$STATE_FILE" ]]; then
  mkdir -p "$(dirname "$STATE_FILE")"
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

  out_dir="monitoring/grafana/dashboards/${folder}"
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

  # JSON sanity
  jq -e . "$tmp" >/dev/null

  mv "$tmp" "${out_dir}/${filename}"
  set_state_rev "$id" "$remote_rev"
done

echo "Done. State saved to ${STATE_FILE}"
