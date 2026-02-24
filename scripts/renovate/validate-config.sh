#!/usr/bin/env bash
set -euo pipefail

IMAGE="${RENOVATE_IMAGE:-renovate/renovate:43}"

test -f renovate.json5 || { echo "FAIL: renovate.json5 missing"; exit 2; }

docker run --rm \
  -v "$PWD:/repo" -w /repo \
  "$IMAGE" \
  renovate-config-validator --strict --no-global renovate.json5
