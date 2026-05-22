# Renovate (Self-hosted, On-demand via Docker Desktop + WSL)

This document describes how this repository uses **Renovate** in a **self-hosted, on-demand** mode:

- Renovate runs as a **Docker container** on **Docker Desktop (WSL2 backend)**.
- It is triggered explicitly from **WSL / VS Code** via `make` targets.
- No Renovate service runs continuously.
- Secrets are kept **out of Git**.

> Scope: This repo currently manages only `stacks/monitoring/compose/docker-compose.yml`. Additional stacks (core/apps) can be enabled later by extending the Renovate config.

---

## Goals and operating model

- **Determinism**: Renovate tooling is pinned (image tag, optionally digest).
- **GitOps**: Renovate only proposes changes via PRs; merges are governed by CI + review.
- **No secrets in Git**: GitHub token is stored on the developer machine only.
- **On-demand**: run Renovate only when you want (maintenance window).

---

## Prerequisites

### Docker Desktop with WSL integration

- Install Docker Desktop on Windows and enable WSL integration for your distro.
- Verify from WSL:

```bash
docker version
docker info
```

In `docker info`, the server should show `Operating System: Docker Desktop` and a WSL2 kernel.

### Repository Makefile targets

The repo Makefile provides:

- `make renovate` (check mode, local scan) and logs result into directory `logs` on wsl
- `make renovate-apply` (apply mode, create/update PRs) - if logs are wanted `LOG=1 make renovate-apply`
- `make renovate-validate` (validate Renovate config using the Renovate container) - if logs are wanted `LOG=1 make renovate-validate`

If you re-bootstrap the repo, ensure your Makefile includes those targets.

#### Note: Makefile calls immutable docker version

The version is pinned via line
`RENOVATE_IMAGE ?= renovate/renovate:43@sha256:...`

The sha value can be determined via commands (check whether another docker version is used and adapt accordingly):

```bash
docker pull renovate/renovate:43
docker inspect --format='{{index .RepoDigests 0}}' renovate/renovate:43
```

---

## Renovate container image

Renovate is executed as a container:

- Default: `renovate/renovate:43` (pinned)
- Optional: pin by digest for maximal determinism.

Pull once (optional but recommended):

```bash
docker pull renovate/renovate:43
docker run --rm renovate/renovate:43 --version
```

---

## GitHub token setup (RENOVATE_TOKEN)

Renovate needs a GitHub token with permission to:

- push branches (**Contents: read/write**)
- create PRs (**Pull requests: read/write**)
- optionally create issues (**Issues: read/write**) if Dependency Dashboard is enabled
- optionally update workflows (**Workflows: read/write**) only if you want Renovate to touch `.github/workflows/**`

Recommended: **Fine-grained PAT** limited to this repository.

Regenerate PAT token on [https://github.com/settings/personal-access-tokens](https://github.com/settings/personal-access-tokens)

Create a local env file:

```bash
mkdir -p ~/.config/renovate
chmod 700 ~/.config/renovate

cat > ~/.config/renovate/renovate.env <<'EOF'
RENOVATE_TOKEN=github_pat_XXXXXXXXXXXXXXXXXXXXXXXXXXXX
LOG_LEVEL=info
EOF

chmod 600 ~/.config/renovate/renovate.env
```

This file must never be committed.

---

## Renovate repository configuration

### Preferred: `renovate.json5` in repo root

We use `renovate.json5` so we can document future rules using comments.

Minimal example (monitoring only):

```json5
{
  $schema: "https://docs.renovatebot.com/renovate-schema.json",
  extends: ["config:recommended", ":dependencyDashboard"],
  enabledManagers: ["docker-compose"],
  packageRules: [
    {
      matchManagers: ["docker-compose"],
      matchFileNames: ["stacks/monitoring/compose/docker-compose.yml"],
      groupName: "monitoring",
    },
  ],
}
```

### Onboarding PR behavior

The first time Renovate runs against a repo without Renovate config, it will create an **Onboarding PR** (typically `renovate/configure`).

- Review the PR carefully.
- Adjust the proposed config to match this repo’s policy (e.g. **docker-compose only**).
- Merge the Onboarding PR to “enable” Renovate for regular update PRs.

If you already have `renovate.json5` in the default branch, Renovate will not need onboarding.

---

## Commands / workflows

### Check mode (local scan, no PRs)

Runs Renovate in **platform=local** mode against your working tree.

```bash
make renovate
```

Expected:

- Logs show dependency extraction.
- No branches or PRs are created.

### Validate Renovate config (Docker-based, no Node required)

```bash
make renovate-validate
```

This runs:

```bash
docker run --rm -v "$PWD:/repo" -w /repo renovate/renovate:43 renovate-config-validator --strict
```

### Apply mode (create/update PRs on GitHub)

Runs Renovate against GitHub using your token.

```bash
make renovate-apply
```

Expected:

- Renovate creates/updates branches `renovate/...`
- Renovate creates/updates PRs in GitHub

---

## Notes on commit author / signatures

Renovate may warn about the default `gitAuthor` email.

- If you don’t care about “Unverified” commit labels, you can ignore it.
- If you want to set your own author identity, add to `~/.config/renovate/renovate.env`:

```bash
RENOVATE_GIT_AUTHOR=Your Name <123456+youruser@users.noreply.github.com>
```

Signing commits (“Verified”) is possible but is intentionally not required for this homelab workflow.

---

## Future extension (core / apps)

When additional stacks exist, extend `packageRules` to scope and group PRs:

```json5
// Core stack (uncomment when stacks/core exists)
/*
{
  matchManagers: ["docker-compose"],
  matchFileNames: ["stacks/core/compose/docker-compose.yml"],
  groupName: "core",
}
*/

// Apps stack (uncomment when stacks/apps exists)
/*
{
  matchManagers: ["docker-compose"],
  matchFileNames: ["stacks/apps/**/compose/docker-compose.yml"],
  groupName: "apps",
}
*/
```

---

## Troubleshooting

### `docker: Cannot connect to the Docker daemon`

- Docker Desktop not running, or WSL integration disabled.
- Start Docker Desktop and enable WSL integration.

### Apply mode returns 401/403 / “insufficient permissions”

- Token is missing, expired, or lacks required permissions.
- Re-generate a fine-grained PAT and ensure:
  - Contents: read/write
  - Pull requests: read/write
  - (optional) Issues: read/write if dependency dashboard is enabled
  - (optional) Workflows: read/write if workflow updates are desired

### Renovate creates an onboarding PR and stops

- That is expected until you merge the onboarding PR (or add `renovate.json5` to default branch).

---

## Files involved

Repository:

- `renovate.json5` (repo policy/config)
- `Makefile` targets: `renovate`, `apply`, `renovate-validate`

Developer machine (NOT in Git):

- `~/.config/renovate/renovate.env` (contains `RENOVATE_TOKEN`)
