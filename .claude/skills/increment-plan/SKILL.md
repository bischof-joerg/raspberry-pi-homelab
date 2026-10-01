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

## Then check what is due

Read the Due column of the index in `.claude/reports/repo-findings.md` (IN15). An open **Critical**
finding (`next`) *is* the next increment; a **High** finding due at the increment number you are
about to plan comes before anything else. Run `python3 .claude/tools/check_findings.py`: an
overdue finding is a failure, not a hint. Only the operator moves a Due (IN16).

## How to split

- One increment changes **one concern** and is small enough to review in one sitting.
- Every increment leaves the system **deployable**. A split that produces an undeployable
  intermediate state is not a split, it is a broken commit sequence (IN2).
- Tests come **before or with** the implementation, never after (IN3): static contracts in
  `tests/precommit` or `tests/guards`, runtime behaviour in `tests/postdeploy`.
- Prefer a first increment that makes the contract **enforceable** (a failing test, marked `xfail`)
  over one that fixes the symptom. Then remove one marker per increment.
- **Run every planned test against today's code before classifying it.** Only a test that fails
  now, for the intended reason (`--runxfail`), is a strict xfail; one that already passes is a
  guard without a marker. Do not promise "fails today" without having run it (IN17, B1 of the
  findings lifecycle: three tests promised as failing passed).
- **Measure on the Pi with one script.** When an increment needs an operator measurement, give it
  as one script that enforces the order (no "meanwhile, in a second terminal") and prints evidence
  that the measured window covers what matters — for example a container's `StartedAt` after the
  trace began. Check every decision rule fixed in advance against a known value before applying
  it; a capability trace counts only checks the process passed with its own credentials, so every
  granted capability must also be in its `CapEff` (R1.19, roadmap §8). The script is saved as a
  file and run with `sudo bash <file>`, never pasted into a login shell; it checks root, the
  checkout path on the Pi (not the WSL path) and every tool **before** it changes anything such as
  a restart. Read what you filter on instead of assuming it — print a container's entrypoint
  before seeding a trace on it. A tracing probe proves itself first: wait for a `BEGIN` marker,
  then catch a known event (`/bin/true`) through the **same probe and predicate** the measurement
  uses, and stop if it does not appear (R1.20, roadmap §8).
- **Fill the Prevention line (IN17)** for whatever finding or failure the increment fixes: the
  earliest rung that could have caught it and the mechanism, preferring a test or guard over a
  rule, skill or lesson.

## Output — one block per increment, template from `.claude/roadmap.md` §3

```markdown
## R<stage>.<n> – <title>
- Feature: <feature this increment belongs to>
- Goal (one sentence):
- Scope: files expected to change
- Out of scope:
- Tests first: <new/changed test files and what each asserts>
- Implementation steps:
- Local gate: `make ci` result (run by Claude) plus the resulting `git diff` if fixers rewrote files
- Proposed commit message:
- Branch: <feat|fix|chore|docs>/<short-name>
- Proposed PR title/description:
- Pi steps (after merge to main): git pull --ff-only; sudo ./deploy.sh
- Acceptance: <observable postdeploy criteria>
- Rollback: git revert <merge-or-commit> on a fix branch → PR → merge → Pi: git pull --ff-only; sudo ./deploy.sh
- Backup/docs/Renovate impact (IN9):
- Prevention (IN17): how recurrence of what this increment fixes is caught earlier, and by which mechanism
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
