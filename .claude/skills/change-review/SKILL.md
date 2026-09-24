---
name: change-review
description: Review a diff or branch against the project rules and produce a checklist plus a clear verdict. Use before proposing a commit or a PR description.
---

# Change review

The rules in `.claude/rules/` state what must hold; this skill is the procedure for checking a
change against them and arriving at a verdict someone can act on.

## Collect the change

```bash
git status --porcelain
git diff                     # unstaged
git diff --stat main...HEAD  # whole branch
git log --oneline main..HEAD
```

Read the **changed files themselves**, not only the diff hunks — a hunk hides the context that
decides whether a rule applies.

## Checklist

Walk the rules that the changed paths actually trigger, and say which ones you skipped and why:

| Changed path | Rule to apply |
|---|---|
| `stacks/**` | `compose-stacks.md` — pinning, project name, external networks, bind mounts, port binding, hardening, config-hash coverage |
| `tests/**` | `testing.md` — right layer, registered marker, no writes into the repo, actionable message |
| `**/*.sh` | `shell-scripts.md` — `set -euo pipefail`, ShellCheck from `.venv`, idempotency, platform guard, quoting |
| `scripts/host*/`, `scripts/network/`, `deploy.sh`, `stacks/core/docker/**` | `host-runtime.md` — ordering, the coupled subnet/bridge/metrics values, postdeploy coverage |
| `scripts/backup/**`, backup docs | `backup-restore.md` — exit codes, locking, dry-run default, GPG boundary, DD-012 tests |
| `.github/**`, `renovate.json5`, `.pre-commit-config.yaml` | `ci-renovate.md` — make parity, pin lockstep, no automerge |
| `docs/**` | `docs-adr.md` — English, ADR form and numbering, cost section |
| `*.env.example`, `stacks/**/compose/**` | `secrets.md` — no values, variable documented, no secret in a log or commit message |

Then the cross-cutting ones, which apply to almost every change:

- **Tests first (IN3)** — does the change ship with tests, or does it silently rely on a later increment?
- **Deployable (IN2)** — would `main` still deploy with only this commit applied?
- **IN9** — persistent data, secrets, ports, UFW, networks or host config touched? Then backup
  inventory, `.env.example`, reconciliation scripts, docs and Renovate rules must move too.
- **Determinism (C6)** — any new version reference pinned, any new image covered by Renovate?

## Verdict

One of three, stated plainly:

- **Ready** — with the proposed Conventional Commit message and PR text.
- **Ready with follow-ups** — list them as increments, not as vague intentions.
- **Not ready** — name the blocking items. Do not soften this into "mostly fine".

Cite `file:line` for every objection. An objection without a location is an opinion.
