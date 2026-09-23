# Working with Claude Code in this repository

For the **operator**. Covers what lives under `.claude/`, how to start a session, what Claude
refuses and why, how to prove the safety set-up still works, and how to change the artefacts
without breaking them silently.

Three files, three audiences (decision D2-b):

| File | Answers | Loaded into Claude's context |
|---|---|---|
| `.claude/CLAUDE.md` | "What do I do now?" — rules, commands, repo map | every session |
| `.claude/readme_claude.md` (this file) | "How do I operate and verify Claude here?" | never, human only |
| `.claude/ClaudeTransition.md` | "Why is it like this?" — decisions, evidence, test records | only when read |

State at writing: roadmap stage **R0**, transition Phase 6, guard mode `transition`,
Claude Code **2.1.280** installed (live hook tests last run on 2.1.276 — see §5.4).

---

## 1. Artefact inventory

| Path | Purpose | Loads | Who changes it | Check |
|---|---|---|---|---|
| `CLAUDE.md` | Project memory: constraints C1–C8, environment, commands, delivery model | every session | Claude (C8), operator reviews | `wc -l` ≤ ~200 |
| `settings.json` | Permission deny/allow, `defaultMode: plan`, hook registration | at startup, live-reloaded | **operator only** (self-protected) | `/status`, `/permissions`, `/hooks` |
| `settings.local.json` | Machine-local permissions | at startup | operator; **never committed** (C3) | `git check-ignore -v` |
| `.gitignore` | Ignores `settings.local.json`, `scratch/`, `logs/` | – | **operator only** (self-protected) | §5.1 |
| `hooks/guard.py` | PreToolUse guard: blocks, never approves; fail-closed | every matched tool call | **operator only** (self-protected) | §5.2 |
| `hooks/guard-config.json` | Guard policy data: mode, Pi identifiers, secret patterns, head lists | every matched tool call | **operator only** (self-protected) | §5.2 |
| `hooks/tests/` | Guard test matrix T01–T46 (77 cases) | – | **operator only** (self-protected) | §5.2 |
| `rules/*.md` (8) | Topic rules, each path-scoped via `paths` | when Claude **reads** a matching file | Claude, operator reviews | `tools/check_rules.py` |
| `skills/*/SKILL.md` (8) | Invokable procedures | description every turn, body on invocation | Claude, operator reviews | `tools/check_skills.py` |
| `agents/*.md` (4) | Read-only subagents (`tools: Read, Grep, Glob`) | registry read **at startup** | Claude, operator reviews | `tools/check_agents.py` |
| `tools/*.py` (4) | Verifiers for rules, skills, agents, findings | run by hand | Claude, operator reviews | `ruff check` |
| `reports/repo-findings.md` | Findings F1–F46 (+F26b) with evidence, fix, test, acceptance | only when read | Claude, operator reviews | `tools/check_findings.py` |
| `ClaudeTransition.md` | Transition plan, decision log, verification records | only when read | Claude, operator reviews | – |
| `scratch/` | Drafts (ADR drafts, patch proposals) — **git-ignored** | – | Claude | not in a fresh clone |
| `logs/guard.log`, `logs/instructions.log` | Guard decisions (JSON lines), instruction-load events — **git-ignored** | – | written by hooks | grow unbounded; truncate by hand |

Skills: `readonly-gate`, `change-review`, `increment-plan`, `image-pin-audit`, `backup-progress`,
`new-stack-proposal`, `postdeploy-test-design`, `adr-draft`.
Agents: `compose-reviewer`, `security-reviewer`, `test-author`, `docs-steward`.
Rules: `compose-stacks`, `testing`, `shell-scripts`, `host-runtime`, `backup-restore`, `secrets`,
`ci-renovate`, `docs-adr`.

---

## 2. Starting a session

From a fresh WSL shell:

```bash
cd /home/micro/src/raspberry-pi-homelab
git status                       # know what is already modified before Claude starts
test -x .venv/bin/python && echo "venv ok"   # Claude never creates the venv; `make venv` is yours
claude
```

Inside Claude Code, check once per session (or after any change to `settings.json` or `agents/`):

| Command | Expected |
|---|---|
| `/status` | Settings sources include the shared project settings; permission mode **plan** |
| `/hooks` | `PreToolUse` → `python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/guard.py"`; `InstructionsLoaded` → append to `logs/instructions.log` |
| `/skills` | the eight skills above |
| `/agents` | the four agents, each listed with `Tools: Read, Grep, Glob` |

`auto` and `bypassPermissions` modes are disabled by `settings.json`; the session starts in plan
mode. Plan mode writes its plan to `~/.claude/plans/` — the guard allows exactly that directory
(patch P6) and nothing else outside the project's `.claude/`.

**Using the artefacts**

- Skills: `/readonly-gate`, `/increment-plan <feature>`, `/change-review`, … or let Claude pick one
  from its description.
- Agents: `@agent-security-reviewer review stacks/monitoring/compose/docker-compose.yml`. The
  `@`-mention guarantees that agent runs; otherwise Claude may delegate automatically.
- Rules are never invoked. They load by themselves when Claude reads a file in their scope.

**Working loop** (`CLAUDE.md` §8): one feature per branch, which you create. Claude:

1. proposes a plan;
2. writes after you approve it;
3. runs `/readonly-gate`;
4. proposes a Conventional Commit message and a PR text.

You run `make ci`, commit, push, open the PR, merge after CI is green, and deploy on the Pi.

---

## 3. What Claude will refuse, and why

| ID | Constraint | Lifetime | Typical refusal |
|---|---|---|---|
| C1 | Writes only inside `.claude/` | until Phase 8 | `guard: C1: redirection would write outside .claude/: README.md` |
| C2 | No side-effect writes (fixers, `--fix`, venv, caches) | until Phase 8 | `make precommit`, `ruff check --fix`, `pip install` blocked |
| C3 | Never read secrets | permanent | `guard: C3: \`grep\` would read secret material: …` |
| C4 | No commit, push, tag, merge, rebase, reset, `gh` | permanent | `guard: C4: git commit is reserved for the operator` |
| C5 | No Pi access — SSH, HTTP, `deploy.sh`, host scripts | permanent | `guard: C5: command references the Raspberry Pi (rpi-hub)` |
| C6 | Pinned, idempotent, test-first | permanent | Claude declines to propose `latest` or a change without tests |
| – | Self-protection of guard and settings | permanent | `guard: self-protection: only the operator edits …/.claude/hooks/guard.py` |
| – | Fail-closed | permanent | `guard: unbalanced quotes in command`, `guard: fail-closed: …` |

The reasons above are verbatim from the recorded live tests (`ClaudeTransition.md` Phase 1b).

**Known false positives — accepted by design.** The guard prefers blocking to guessing:

- inline interpreter code: `python3 -c …`, `perl -e …`, and also `pytest -c <ini>`
  (`C1: inline interpreter code is not inspectable`);
- any command that merely *mentions* `rpi-hub`, `rpi-hub.fritz.box` or `192.168.178.29` — including
  `grep -rn rpi-hub docs/`;
- a search pattern that looks like a secret path, e.g. `grep -E '…|\.env'` (observed 2026-09-23);
- bare `make` (only `make doctor`, `make doctor-strict`, `make help` pass);
- heredocs and `| bash` (the executed body cannot be inspected).

**When something is blocked**

1. Treat it as a result. Claude reports it, it does not route around it (`CLAUDE.md` §10).
2. If the command is legitimate, **you** run it — e.g. `! make ci` in the prompt runs it in your
   shell and puts the output into the conversation.
3. If a guard or settings change is really needed, use the self-protect window in §6.5. Never
   loosen a check just to get one task through.

---

## 4. The two enforcement layers

They cover **different** surfaces; neither alone is sufficient.

| Layer | Sees | Misses |
|---|---|---|
| `settings.json` deny rules | Tool names and paths for `Edit`/`Read`; Bash command prefixes, including in subshells and after wrappers such as `timeout` | Programs called by absolute path, code inside `sh -c '…'`, `git -C . push`, and **arbitrary operands**: a Bash `mv` into `.claude/hooks/` passes this layer |
| `hooks/guard.py` | Parsed Bash (nested `$(…)`, `bash -c`, `xargs`, `find -exec`), resolved write targets, redirections, symlinks, secret paths | Code run inside allowed programs (a test or Makefile recipe that writes files), strings built at runtime (K3) |

The `mv` example is measured, not theoretical. During V1.14 the settings layer let
`mv .claude/hooks/guard-config.json …` through, and the guard caught it.

### 4.1 The deny list, grouped (JSON has no comments, so the grouping lives here)

**Self-protection — permanent**

`Edit(/.claude/.gitignore)`, `Edit(/.claude/settings.json)`, `Edit(/.claude/hooks/**)`.

**Transition block — Phase 8 removes or narrows these (C1/C2)**

- Edit denies: `/.github/**`, `/docs/**`, `/scripts/**`, `/stacks/**`, `/tests/**`, `/config/**`,
  `/Makefile`, `/deploy.sh`, `/README.md`, `/Todo.txt`, `/pyproject.toml`,
  `/requirements-dev.txt`, `/renovate.json5`, `/.gitignore`, `/.gitattributes`,
  `/.pre-commit-config.yaml`, `/.yamllint.yml`.
- Mutating tools: `make venv*`, `make hooks*`, `make precommit*`, `make format*`, `make ruff*`,
  `make check*`, `make ci*`, `make test*`, `pre-commit *`, `pip install *`.

**Permanent block — stays after Phase 8**

- C1 residue (the proposed Phase 8 edit scope keeps these out): `Edit(/secrets/**)`,
  `Edit(/logs/**)`, `Edit(/.vscode/**)`, `Edit(/ChatGPTHint.txt)`.
- C3 secrets: `Read(/secrets/**)`, `Read(**/.env)`, `Read(**/*.env)`, `Read(**/*.kdbx)`,
  `Read(**/*.keyx)`, `Read(**/*.pem)`, `Read(**/*.key)`, `Read(**/*.p12)`, `Read(**/*.pfx)`,
  `Read(~/.config/renovate/**)`, `Read(~/.ssh/**)`, `Read(~/.gnupg/**)`,
  `Read(//etc/raspberry-pi-homelab/**)`, `Bash(gpg *)`.
- C4 git: `git commit|push|tag|merge|rebase|reset|checkout|switch|stash|add|rm *`, `gh *`.
- C5 Pi and host: `ssh`, `scp`, `sftp`, `rsync`, `ansible`, `*rpi-hub*`, `*192.168.178.29*`,
  `*rpi-hub.fritz.box*`, the three `WebFetch(domain:…)` entries, `./deploy.sh *`, `sudo *`,
  `*scripts/host/*`, `*scripts/host-runtime/*`, `*scripts/network/*`, `*init-permissions.sh*`,
  `ufw`, `systemctl`, `usermod`, `groupadd`, `docker network create*|rm*`, `make postdeploy*`,
  `make host-*`, `make backup*`, `make restore*`, `make renovate*`, `docker compose up*|down*|pull*`,
  `docker run *`, `docker login *`.

**Allow list**: `git status|diff|log|show|ls-files|check-ignore|rev-parse`, `make doctor`,
`make doctor-strict`. The skill `readonly-gate` pre-approves its eight exact commands for one turn
(decision D4-b). It is the only skill with a tool grant.

Phase 8 has to replace the broad Pi denies before it adds any selective allow, because deny always
wins (`ClaudeTransition.md` Phase 8).

---

## 5. Verifying the safety set-up

Run this after cloning, after any change to `.claude/`, and **after every Claude Code update**. The
hook behaviour is version-specific; issues #37210 and #43407 reported ignored hook denies on
earlier versions. All commands are read-only. Run them from the repo root.

### 5.1 Git hygiene (V1.1, V7.1)

```bash
git check-ignore -v .claude/settings.local.json .claude/logs/guard.log .claude/scratch/x
# expect three lines, each matched by .claude/.gitignore
git ls-files .claude | grep -c settings.local.json          # expect 0
grep -rl $'\r' .claude                                       # expect no output (LF only, K9)
```

### 5.2 Guard matrix (V1.9)

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider -q .claude/hooks/tests
# expect: 77 passed (measured 2026-09-23)
.venv/bin/ruff check --no-fix --no-cache .claude/hooks .claude/tools
.venv/bin/ruff format --check --no-cache .claude/hooks .claude/tools
```

### 5.3 Direct guard probes (V1.10–V1.15, your shell only)

The guard only **evaluates** the JSON; nothing is executed. Do not type the quoted commands
themselves into your shell. A hook fires only on Claude's tool calls, so `bash -c "git commit …"`
typed by you simply commits. Claude cannot run this block either: the raw Pi-identifier scan
blocks it as a whole, by design.

```bash
R=$(git rev-parse --show-toplevel)
probe() { printf '%s' "$1" | python3 .claude/hooks/guard.py; echo "$2 exit=$?"; }
probe '{"tool_name":"Bash","tool_input":{"command":"bash -c \"git commit --allow-empty -m test\""},"cwd":"'"$R"'"}' V1.10   # 2, C4
probe '{"tool_name":"Bash","tool_input":{"command":"sh -c \"true && ssh rpi-hub.fritz.box true\""},"cwd":"'"$R"'"}' V1.11  # 2, C5
probe '{"tool_name":"Bash","tool_input":{"command":"echo test > README.md"},"cwd":"'"$R"'"}' V1.12                          # 2, C1
probe '{"tool_name":"Edit","tool_input":{"file_path":".claude/hooks/guard.py"},"cwd":"'"$R"'"}' V1.13                      # 2, self-protection
probe '{"tool_name":"Bash","tool_input":{"command":"git status"},"cwd":"'"$R"'"}' control                                    # 0
tail -5 .claude/logs/guard.log      # V1.15: one JSON line per decision above
```

V1.14 (fail-closed) — rename the config, probe, restore:

```bash
mv .claude/hooks/guard-config.json .claude/hooks/guard-config.json.bak
probe '{"tool_name":"Bash","tool_input":{"command":"ls"},"cwd":"'"$R"'"}' V1.14   # 2, fail-closed
mv .claude/hooks/guard-config.json.bak .claude/hooks/guard-config.json
```

### 5.4 Live hook checks (needs a Claude session)

The probes in 5.3 test the guard; only a real tool call tests the **hook wiring**. In a session,
ask Claude to run each of the following and check that it is refused with the reason shown:

| Ask Claude to… | Expected |
|---|---|
| run `bash -c "git commit --allow-empty -m test"` | `guard: C4: …`; afterwards `git log -1` is unchanged |
| run `echo test > README.md` | `guard: C1: …`; `git diff README.md` is empty |
| edit `.claude/hooks/guard.py` | denied by settings or `guard: self-protection: …` |
| read a file under `secrets/` | denied |
| run `make doctor` | runs without a prompt; `git status --porcelain --ignored` is the same before and after (V1.7) |

If any of the refusals does **not** happen: stop. Record the Claude Code version and the case, treat
the hook as non-enforcing, and do not continue feature work (V1.16).

Last full run: 2026-09-23 on **2.1.276**, all passed. The installed version is now **2.1.280**.
Incidental evidence that the guard still enforces on 2.1.280: during Phase 6 it blocked a
`python3 -c` call and a `grep` with a secret-looking pattern. The full table above has **not** been
re-run on 2.1.280 yet.

### 5.5 Path-scoped rules load on demand (V3.2)

```bash
grep -c path_glob_match .claude/logs/instructions.log      # > 0 once Claude has read a scoped file
```

For a clean proof, open a fresh session and ask for a compose review (`ClaudeTransition.md` §3.2).
Then check that `compose-stacks.md` appears with reason `path_glob_match`, and that rules for
untouched areas do **not** appear.

### 5.6 Artefact checkers and the read-only gate

```bash
.venv/bin/python .claude/tools/check_rules.py      # 8 rules, all with `paths`, cited files exist
.venv/bin/python .claude/tools/check_skills.py     # 8 skills, description budget ~1,236 chars
.venv/bin/python .claude/tools/check_agents.py     # 4 agents, `tools` present and read-only
python3 .claude/tools/check_findings.py            # 47 findings, all fields, index in sync
```

Each prints `0 failure(s)` and exits 0 when healthy. Finally, run the read-only gate from
`CLAUDE.md` §7 (or ask for `/readonly-gate`). It ends with `OK: no side effects`.

---

## 6. Updating the artefacts

Each artefact type has its own **silent** failure: Claude Code ignores the mistake instead of
reporting it. Every checker in `tools/` exists because of one of these.

### 6.1 `CLAUDE.md`

- Keep it at or under ~200 lines. It costs context in every session.
- "What to do now" belongs here; "why" belongs in `ClaudeTransition.md` (D2-b).
- Every path it cites must exist, and must say what `CLAUDE.md` claims it says. Three past errors
  were citations of documents that do not contain the claim (F40, F42, F46).
- Test: fresh session, ask "What may you not do in this repo?" The answer should come without any
  file access (V2.3).

### 6.2 Rules (`rules/*.md`)

- `paths` frontmatter is **mandatory**. A rule without it, or with YAML that does not parse, loads
  **unconditionally** — no error, just permanent context cost.
- `paths` is the only key read; any other key is ignored silently. No `[` in globs.
- Do not restate `CLAUDE.md`. Contradicting rules are resolved arbitrarily.
- Run `tools/check_rules.py`.

### 6.3 Skills (`skills/<name>/SKILL.md`)

- The `description` loads on **every turn**; keep it to one line. The body is free until invoked.
- `name` must equal the directory name. Unknown frontmatter keys are ignored silently.
- `allowed-tools` only on `readonly-gate`. Skills are **not** self-protected, so a grant in any
  other skill would be the first place Claude could widen its own rights.
- New or changed skills are picked up in the **same** session.
- Run `tools/check_skills.py`.

### 6.4 Agents (`agents/*.md`)

- `tools` must be **present**. An absent `tools` does not mean "no tools", it means **every** tool,
  including Edit, Write and Bash (D5-a).
- Bodies carry procedure and report format only. Agents inherit `CLAUDE.md` and `rules/` (D5-b).
- The agent registry is read **at startup**: restart Claude Code after any change, then check
  `/agents`.
- Run `tools/check_agents.py`.

### 6.5 Self-protected files (guard, config, tests, `settings.json`, `.gitignore`)

Only you change these. Both layers protect them: the `self_protect` flag in the guard, and since
patch P5 the settings denies `Edit(/.claude/hooks/**)`, `Edit(/.claude/settings.json)` and
`Edit(/.claude/.gitignore)`. Turning off one layer is **not** enough for Claude's Edit tool.

**Default: you apply the change.**

1. Claude writes the proposed patch and its test rows into `ClaudeTransition.md`. It does not use
   `scratch/`, which is not committed.
2. You apply the patch in your editor.
3. Claude runs §5.2 and re-probes the affected case.

**Only if Claude must apply it** — the P1–P6 procedure from 2026-09-23, which predates the P5 deny:

1. You remove `Edit(/.claude/hooks/**)` from `settings.json`.
2. You set `"self_protect": false`.
3. Claude applies the patch and runs §5.2.
4. You re-add the deny, then set `"self_protect": true` — in that order, so the files are never
   left unprotected.
5. Claude re-probes one self-protection case; it must return `exit 2`.

`settings.json` itself stays yours in both paths.

`settings.json` changes take effect without a restart. Hook registration changes should be checked
with `/hooks`.

### 6.6 Findings (`reports/repo-findings.md`)

- The report is the source of truth. `ClaudeTransition.md` §3.6 is an index, and must list the
  same IDs.
- New finding: add an entry with all five fields, a row in the report index, and a row in §3.6. Then
  run `tools/check_findings.py`.
- Mark a missing file as `` `path` (absent) ``. The checker verifies that it really is absent.

### 6.7 After a Claude Code update

1. `claude --version`, and record it in `ClaudeTransition.md`.
2. Run §5 completely, including the live checks in §5.4.
3. Skim the version notes of the settings, hooks, memory, skills and sub-agents docs. The URLs are
   in `ClaudeTransition.md` §11.

---

## 7. What changes in Phase 8

Phase 8 starts after this transition is committed and merged. It retires C1 and C2:

- `CLAUDE.md` §2.1 is deleted;
- the transition block in §4.1 is removed from `settings.json`;
- the guard switches to `mode: "operate"`.

C3–C6 and self-protection stay. You confirm the edit scope first; the default proposal is the
whole repo except `secrets/**`, `logs/**`, `.vscode/**` and `ChatGPTHint.txt`. Any selective Pi
access (for example one Grafana health URL) is added to **both** layers as an exact match, after
the broad Pi denies have been narrowed. Details are in `ClaudeTransition.md`, Phase 8.
