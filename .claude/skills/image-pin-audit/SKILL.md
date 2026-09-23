---
name: image-pin-audit
description: Audit every container image reference for pinning quality (tag vs digest, floating minor tags) and Renovate coverage. Use before adding an image or when reviewing update drift.
---

# Image pin audit

Determinism is a core principle (`CLAUDE.md` §4): pinned versions, never `latest`, digests preferred
over tags. This skill reports where the repository actually stands.

## Collect

```bash
grep -rn "image:" stacks/ | sed 's/ *#.*//'
grep -rn "GF_PLUGINS_PREINSTALL" -A 2 stacks/
grep -nE "uses:|rev:" .github/workflows/ci.yml .pre-commit-config.yaml
grep -nE "renovate/renovate|image" renovate.json5 scripts/renovate/validate-config.sh
```

## Report as a table

| Service / artefact | Reference | Pin quality | Renovate |
|---|---|---|---|

Pin quality, strongest first:

1. **digest** — `image@sha256:…`, immutable.
2. **full version tag** — `v1.152.0`, `11.6.16`, `0.53.0-debian`. Immutable by convention only:
   a publisher can move a tag.
3. **floating minor or major tag** — `alpine:3.24`, `renovate/renovate:43`. The patch level moves
   silently. This is a weaker pin than the rest of the stack and should be called out, not listed
   as merely "pinned" (F37).
4. **unpinned / `latest`** — a defect. Never accept one.

## Coverage is the second half

A pin without a Renovate rule does not get updated; a Renovate rule without a pin has nothing to
update. Report both. Known gaps to verify rather than assume:

- Renovate manages the `docker-compose` manager **only**. Unmanaged: GitHub Actions tags, pre-commit
  hook `rev`s, pip ranges, and the Grafana plugin pin `victoriametrics-logs-datasource@0.24.1` (F4).
- `scripts/renovate/validate-config.sh` runs `renovate/renovate:43` by **tag** while the Makefile
  pins the same image by **digest** (F24) — the same artefact, two different pin qualities.

## Verdict

State the count of each pin quality, name every item in category 3 or 4 explicitly, and list images
with no Renovate coverage. If a new image is being added, say in one line what its Renovate rule
must be — that rule belongs in the **same increment** (IN10), not a later one.
