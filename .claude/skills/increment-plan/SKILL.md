---
name: increment-plan
description: Turn one feature into small, deployable increments with tests, acceptance criteria and rollback. Use when starting a feature or when a change is getting too big for one commit.
---

# Increment plan

Delivery model D1: one feature at a time, split into increments, each with its own tests. The rules
live in `CLAUDE.md` §8; this skill turns them into a concrete plan.

## Before splitting, check the entry condition

A new feature starts only after the previous one is deployed **and** its postdeploy tests are green
(IN1). If the last increment failed to deploy, the answer is not a new plan — it is fix-forward
within the same scope, or `git revert` via a branch and PR (IN8).

## How to split

- One increment changes **one concern** and is small enough to review in one sitting.
- Every increment leaves the system **deployable**. A split that produces an undeployable
  intermediate state is not a split, it is a broken commit sequence (IN2).
- Tests come **before or with** the implementation, never after (IN3): static contracts in
  `tests/precommit` or `tests/guards`, runtime behaviour in `tests/postdeploy`.
- Prefer a first increment that makes the contract **enforceable** (a failing test, marked `xfail`)
  over one that fixes the symptom. Then remove one marker per increment.

## Output — one block per increment, template from 10.2

```markdown
## R<stage>.<n> – <title>
- Feature: <feature this increment belongs to>
- Goal (one sentence):
- Scope: files expected to change
- Out of scope:
- Tests first: <new/changed test files and what each asserts>
- Implementation steps:
- Local gate: Claude read-only gate result / operator `make ci` result
- Proposed commit message:
- Branch: <feat|fix|chore|docs>/<short-name>
- Proposed PR title/description:
- Pi steps (after merge to main): git pull --ff-only; sudo ./deploy.sh
- Acceptance: <observable postdeploy criteria>
- Rollback: git revert <merge-or-commit> on a fix branch → PR → merge → Pi: git pull --ff-only; sudo ./deploy.sh
- Backup/docs/Renovate impact (IN9):
```

## The IN9 question is not optional

If the increment touches persistent data, host secrets, ports, UFW rules, Docker networks or host
configuration, it must **also** update: the backup inventory (ADR-009 §4/§5), `.env.example`, the
reconciliation scripts and their postdeploy checks, the network/firewall docs, and the Renovate
rules. Write "none" only after checking each, not by default.

## Acceptance must be observable

"Works correctly" is not acceptance. Name the postdeploy check that proves it — an endpoint that
returns data, a container that reports healthy, a UFW rule that exists. If no check can prove it,
the increment is not finished being designed.

## What Claude does not do

Propose the commit message and the PR text. The operator commits, pushes, opens the PR, merges and
deploys (C4, C5, IN5).
