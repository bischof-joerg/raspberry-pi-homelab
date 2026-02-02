#!/usr/bin/env bash
set -euo pipefail

# Postdeploy checks for VictoriaMetrics stack.
# Runs on the host (Pi) to avoid relying on tools inside minimal containers.

fail() { echo "FAIL: $*" >&2; exit 1; }
info() { echo "INFO: $*" >&2; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "missing required command: $1"
}

require_cmd curl
require_cmd jq

VM_URL="${VM_URL:-http://127.0.0.1:8428}"
VMALERT_URL="${VMALERT_URL:-http://127.0.0.1:8880}"

# Timeouts: keep fast and actionable
CURL=(curl -fsS --connect-timeout 2 --max-time 8)

info "Checking VictoriaMetrics health endpoint: ${VM_URL}/health"
"${CURL[@]}" "${VM_URL}/health" >/dev/null || fail "victoriametrics /health not reachable on ${VM_URL}"

info "Checking vmalert health endpoint: ${VMALERT_URL}/health"
"${CURL[@]}" "${VMALERT_URL}/health" >/dev/null || fail "vmalert /health not reachable on ${VMALERT_URL}"

query_vm() {
  local q="$1"
  "${CURL[@]}" "${VM_URL}/api/v1/query" --data-urlencode "query=${q}"
}

expect_vm_success() {
  local q="$1"
  local out
  out="$(query_vm "$q")" || fail "query failed: ${q}"
  echo "$out" | jq -e '.status=="success"' >/dev/null || fail "query not successful: ${q}"
  echo "$out"
}

expect_series_nonempty() {
  local q="$1"
  local out
  out="$(expect_vm_success "$q")"
  # result can be vector/matrix; here we use instant query -> vector
  echo "$out" | jq -e '.data.result | length > 0' >/dev/null || fail "no series returned for: ${q}"
}

# 1) Core presence
info "Checking that VM returns data for 'up'"
expect_series_nonempty 'up'

# 2) Key targets scraped (these job names must match your vmagent.yml)
info "Checking scrape targets (job labels) exist in VM"
expect_series_nonempty 'up{job="victoriametrics"}'
expect_series_nonempty 'up{job="vmagent"}'
expect_series_nonempty 'up{job="vmalert"}'
expect_series_nonempty 'up{job="alertmanager"}'
expect_series_nonempty 'up{job="node-exporter"}'
expect_series_nonempty 'up{job="cadvisor"}'

# 3) Optional: ensure at least some cAdvisor CPU metric exists (common pain point)
info "Checking basic cAdvisor metric exists (docker_container_cpu_usage_seconds_total)"
# Allow either of these (varies by cadvisor version/config)
if ! query_vm 'docker_container_cpu_usage_seconds_total' | jq -e '.data.result | length > 0' >/dev/null 2>&1; then
  if ! query_vm 'container_cpu_usage_seconds_total' | jq -e '.data.result | length > 0' >/dev/null 2>&1; then
    fail "no expected cAdvisor CPU metric found (docker_container_cpu_usage_seconds_total or container_cpu_usage_seconds_total)"
  fi
fi

info "OK: VictoriaMetrics postdeploy checks passed"
