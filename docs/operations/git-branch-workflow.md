# Git Branch Workflow

Conventions and commands for branch handling in `raspberry-pi-homelab`: create a branch, commit
increments, open a pull request, merge into `main`, deploy on the Pi, and roll back.

Scope: Git and GitHub mechanics only. The operating model, change lifecycle, quality gates, CI
jobs, deployment, and roles are defined in [DevWorkflow.md](DevWorkflow.md) and are not repeated
here.

---

## 1. Git rules

| # | Rule |
|---|---|
| 1 | One short-lived branch per feature, created from the current `main`. |
| 2 | One commit per increment (lifecycle: [DevWorkflow.md](DevWorkflow.md) section 2). |
| 3 | Commit only after `make ci` is green ([DevWorkflow.md](DevWorkflow.md) section 4.3). |
| 4 | `main` changes only via pull request with green CI; no direct commits or force pushes to `main`. |
| 5 | History on `main` is never rewritten; rollback uses `git revert`. |
| 6 | No Git write operations on the Pi. |

---

## 2. Branch naming

Format: `<type>/<stage>-<short-description>`

- `<type>`: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `ci`, `revert`
- `<stage>`: roadmap stage in lower case (`r0` … `r4`); omit for work outside the roadmap
- `<short-description>`: lower-case kebab-case, 2–5 words, ASCII only

Examples:

| Branch | Purpose |
|---|---|
| `chore/r0-toolchain-parity` | Pin tool versions to pre-commit revs |
| `chore/r0-claude-transition` | Claude Code artefacts under `.claude/` |
| `fix/r1-config-hash-coverage` | Finding F1 |
| `feat/r2-backup-restore-tests` | Backup tests (ADR-009) |
| `feat/r3-traefik-core-stack` | Traefik core stack |
| `feat/r4-stirling-pdf` | Stirling PDF app stack |
| `revert/r2-backup-timer` | Roll back a merged feature |

---

## 3. Commit messages

Based on Conventional Commits 1.0.0: https://www.conventionalcommits.org/en/v1.0.0/

```text
<type>(<scope>): <subject>

<body: why, not how; wrap at 72 chars>

Refs: <increment id, finding id, ADR>
```

| Element | Convention |
|---|---|
| `type` | `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `ci`, `build`, `revert` |
| `scope` | area of change: `monitoring`, `backup`, `core`, `traefik`, `apps`, `stirling-pdf`, `adguard`, `homeassistant`, `host`, `network`, `deploy`, `tooling`, `tests`, `claude`, `docs`, `renovate` |
| `subject` | imperative mood, lower case, no trailing period, max. 72 characters |
| `body` | optional; reason and impact (runtime, backup, firewall, secrets) |
| footer | `Refs: R2.3, F9, ADR-009`; `BREAKING CHANGE: …` if host state or data layout changes incompatibly |

Examples:

```text
chore(tooling): pin ruff, shellcheck-py and yamllint to pre-commit revs

Local .venv tools and pre-commit hooks used different versions, so lint
results could differ between the read-only gate and make ci. A precommit
test now fails on future drift.

Refs: R0.0, F21
```

```text
fix(deploy): include vmalert rules and vector config in config hash

Refs: R1.2, F1
```

---

## 4. Workflow at a glance

```text
main ──●─────────────────────────────●──(merge commit)──► deploy: DevWorkflow.md section 6.1
        \                           /
         feat/r2-backup-...  ●──●──●   (one commit per increment, make ci before each commit)
```

---

## 5. Commands (WSL, repo root `/home/micro/src/raspberry-pi-homelab`)

### 5.1 Start a feature branch

```bash
git switch main
git pull --ff-only
git status --porcelain                  # must be empty
git switch -c feat/r2-backup-restore-tests
```

### 5.2 Implement and commit one increment

```bash
git status
git diff                                # review all changes
make ci                                 # must pass before committing (DevWorkflow.md 4.3)
git status --porcelain                  # pre-commit fixers may have changed files: review again
git add -p                              # stage deliberately, hunk by hunk
git diff --staged                       # final review of what goes into the commit
git commit                              # message per section 3
```

Check whether the pre-commit Git hook is installed (it then also runs on `git commit`):

```bash
test -x .git/hooks/pre-commit && echo "pre-commit hook installed" || echo "not installed"
```

### 5.3 Push and open the pull request

```bash
git push -u origin feat/r2-backup-restore-tests
```

Open the PR on GitHub (base `main`), or with the GitHub CLI:

```bash
gh pr create --base main --head feat/r2-backup-restore-tests \
  --title "feat(backup): add restore fixture tests" \
  --body-file /tmp/pr-body.md
```

PR description template:

```markdown
## What
<one paragraph>

## Why
<finding / ADR / roadmap increment>

## Tests
- precommit/guards: <files>
- postdeploy: <files>

## Pi impact
<runtime change? restart? UFW? secrets? backup inventory?>

## Rollback
git revert -m 1 <merge-commit> via revert branch + PR
```

### 5.4 Further increments on the same branch

```bash
# after review feedback or next increment
make ci
git add -p
git commit
git push
```

### 5.5 Update the branch when `main` has moved

Only for your own feature branch; never for `main`.

```bash
git fetch origin
git rebase origin/main
make ci
git push --force-with-lease
```

`--force-with-lease` refuses to overwrite remote commits you have not fetched.

### 5.6 Merge into `main`

Preconditions: CI green, branch up to date with `main`, PR description complete.

Merge method: **Create a merge commit** (see section 6). On GitHub: *Merge pull request* →
*Create a merge commit* → *Confirm merge* → *Delete branch*. Or:

```bash
gh pr merge <pr-number> --merge --delete-branch
```

### 5.7 Clean up locally

```bash
git switch main
git pull --ff-only
git branch -d feat/r2-backup-restore-tests   # -d refuses if not merged
git fetch --prune                             # drop deleted remote-tracking branches
```

### 5.8 Deploy

Deploy the merged `main` on the Pi as described in [DevWorkflow.md](DevWorkflow.md) section 6.1.
Record the merge commit SHA with the deploy result.

---

## 6. Merge method decision

| Method | History on `main` | Increment commits preserved | Commit SHAs stable | Rollback of a whole feature |
|---|---|---|---|---|
| **Create a merge commit** (chosen) | merge point per feature | yes | yes | `git revert -m 1 <merge-sha>` |
| Squash and merge | one commit per feature | no | new SHA | `git revert <sha>` |
| Rebase and merge | linear | yes | new SHAs | revert each commit |

Rationale: increments are the unit of review, testing and rollback, so they stay individually
visible. SHAs recorded in the increment log stay valid after merge. GitHub documents that a merge
commit keeps the full branch history with an explicit merge point, squash combines all commits
into one, and rebase-and-merge rewrites commits with new SHAs:
https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/about-pull-request-merges

Repository settings that enforce this choice: section 7.1.

---

## 7. Protection of `main` (ruleset `protect-main`)

`main` is protected by a repository ruleset. Rulesets are available for public repositories on
GitHub Free and for private repositories on GitHub Pro, Team, and Enterprise Cloud:
https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/managing-rulesets-for-a-repository

### 7.1 Repository merge settings

GitHub → Settings → General → Pull Requests:

| Setting | Value | Reason |
|---|---|---|
| Allow merge commits | on | Chosen merge method (section 6) |
| Allow squash merging | off | Enforce section 6 |
| Allow rebase merging | off | Enforce section 6 |
| Automatically delete head branches | on | Feature branches are short-lived |

### 7.2 Ruleset settings

GitHub → Settings → Rules → Rulesets → `protect-main`:

| Setting | Value | Reason |
|---|---|---|
| Ruleset name | `protect-main` | |
| Enforcement status | **Active** | `Evaluate` only reports and does not block |
| Bypass list | **empty** | Nobody, including repository admins, can bypass the rules; the operator follows the same path as every change |
| Target branches | Include default branch (`main`) | |
| Restrict deletions | on | `main` cannot be deleted |
| Block force pushes | on | History on `main` is never rewritten (section 1, rule 5) |
| Require a pull request before merging | on | No direct pushes to `main` |
| → Required approvals | **0** | Single maintainer: GitHub does not accept approvals from the pull request author, so any value above 0 would block every merge. CI is the gate. |
| → Dismiss stale approvals, require review from code owners, require approval of the most recent push | off | Not applicable with 0 approvals |
| → Require conversation resolution before merging | optional | Useful if review comments are used as a checklist |
| → Allowed merge methods (if offered) | Merge only | Consistent with 7.1 and section 6 |
| Require status checks to pass | on | CI must be green before merge |
| → Require branches to be up to date before merging | on | CI result must reflect the latest `main` |
| → Status checks (source: GitHub Actions) | `doctor (strict)`, `precommit (hooks + tests/precommit)`, `tests (unit/integration, no postdeploy)` | Job names from `.github/workflows/ci.yml` ([DevWorkflow.md](DevWorkflow.md) section 5) |
| Require linear history | **off** | Incompatible with merge commits (section 6) |
| Require signed commits, require deployments, code scanning, merge queue | off | Not used in this repository |

Notes:

- If a status check does not appear in the search, CI has not reported it yet. Open a pull request
  so CI runs once, then add the check.
- Renaming a CI job changes its check name. Update the ruleset in the same pull request that
  renames the job, otherwise merges are blocked by a check that never reports.
- An empty bypass list also blocks emergency fixes directly on `main`. Emergencies use the normal
  path: branch → pull request → CI → merge (rollback: section 8).

### 7.3 Verification

Run after creating or changing the ruleset. The commands do not touch the current working tree or
branch (a temporary worktree is used).

Read the active rules for `main` (read-only):

```bash
gh api repos/{owner}/{repo}/rules/branches/main --jq '.[].type'
# expected to include: deletion, non_fast_forward, pull_request, required_status_checks
```

Verify that a direct push to `main` is rejected:

```bash
git fetch origin
git worktree add --detach /tmp/protect-main-test origin/main
cd /tmp/protect-main-test
git commit --allow-empty --no-verify -m "test: verify protect-main ruleset"
git push origin HEAD:main            # expected: rejected with a repository rule violation
cd -
git worktree remove --force /tmp/protect-main-test
git worktree list                    # only the main worktree remains
```

If the push is accepted, the ruleset is not effective: check enforcement status, bypass list, and
target branch. Remove the empty commit through a revert branch and pull request (section 8.2).

Do not test force pushes or deletion of `main` directly; rely on the rule list above.

Verify with the next real pull request:

| Check | Expected |
|---|---|
| Merge while CI is running or red | Merge button blocked |
| `main` moved after the branch was pushed | GitHub requires the branch to be updated (section 5.5) |
| Merge options | Only "Create a merge commit" |
| After merge | Head branch deleted automatically |

---

## 8. Rollback

### 8.1 Whole feature

```bash
git switch main && git pull --ff-only
git switch -c revert/r2-backup-restore-tests
git revert -m 1 <merge-commit-sha>
make ci
git push -u origin revert/r2-backup-restore-tests
# PR → CI green → merge commit → deploy (DevWorkflow.md 6.1)
```

### 8.2 Single increment

```bash
git switch main && git pull --ff-only
git switch -c revert/r2-single-increment
git revert <increment-commit-sha>
make ci
git push -u origin revert/r2-single-increment
# PR → CI green → merge commit → deploy (DevWorkflow.md 6.1)
```

Never use `git reset --hard` or force pushes on `main` for rollback; history must stay intact for GitOps.

### 8.3 Background knowledge on sha values

In general the short sha value with 8 characters is sufficient. In huge repositories it might be not unique. However, git would tell. And only in these rare cases the long, 40 character sha is needed.

There are multiple ways to retrieve the sha value of a commit:
- Command `git log --oneline --graph --all` displays the tree structures of commits
- Command `git log --merges --oneline` logs only merge commits of the current branch
- For easily retrieving a long sha: In Visual Studio in the Source Control tree, right click on any commit and choose 'Copy Commit Hash' for getting the hash into the clipboard.

---

## 9. Troubleshooting

| Situation | Action |
|---|---|
| `git pull --ff-only` fails on the Pi | Local changes or commits exist on the Pi (violates the guardrails). Inspect with `git status` and `git log origin/main..main`; do not merge or rebase on the Pi. Move any needed change into a WSL branch, then reset the Pi checkout to `origin/main` and deploy. |
| `git pull --ff-only` fails in WSL on `main` | You committed on `main` by mistake: `git branch feat/r?-rescue` to keep the work, then `git reset --hard origin/main` on local `main` only (never pushed). |
| Committed to the wrong branch (not pushed) | `git switch -c <right-branch>`, then on the wrong branch `git reset --hard HEAD~1`. |
| `make ci` modified files | Review with `git diff`, stage the fixes into the same increment. |
| Rebase conflict | Resolve, `git add <files>`, `git rebase --continue`; abort with `git rebase --abort`. |
| CI fails on the PR | Fix on the same branch as a new commit, `make ci`, push. |
| Forgot a file in the last, **unpushed** commit | `git add <file>` and `git commit --amend --no-edit`. After pushing, prefer a new commit. |

---

## 10. References

- Operating model, gates, CI, deploy, roles: [DevWorkflow.md](DevWorkflow.md)
- Conventional Commits 1.0.0: https://www.conventionalcommits.org/en/v1.0.0/
- GitHub merge methods: https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/about-pull-request-merges
