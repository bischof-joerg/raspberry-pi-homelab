---
paths:
  - "docs/**"
---

# Documentation and ADRs

## Language and form

- **English only** for docs, comments and config descriptions — including files whose surrounding
  material is German. `Todo.txt` is the deliberate exception and stays German.
- Markdown, LF line endings, final newline, no trailing whitespace. The pre-commit hygiene hooks
  fix these during `make precommit`/`make ci`, but a fixer rewrite is an unreviewed diff, so
  author the file correctly the first time.
- Write what the system *is*, not what it was planned to be. Where the two differ, say so and name
  the gap — that is more useful than a tidy fiction.

## Layout

| Directory | Contents |
|---|---|
| `docs/architecture/adr/` | one file per decision |
| `docs/operations/` | `DevWorkflow.md`, `git-branch-workflow.md`, `runtime-updates.md`, `BackupVerifyRestore.md`, `GPG_config_for_backup_encryption.md`, `renovate.md` |
| `docs/services/` | per-service documentation |
| `docs/monitoring.md` | monitoring overview |

`ChatGPTHint.txt` §10.1 describes a richer target layout (bootstrap, incident playbook,
threat-model, per-service pages). It is a target, not the current state.

## ADRs

Write an ADR when a decision **constrains later work** — a boundary, a protocol, a data model, an
exception to a rule. Not for choices a future increment can reverse freely.

- **MUST** use a consistent filename and title. The existing numbering is inconsistent (F6):
  `ADR-0001-networking-and-firewall.md` is titled ADR-0004, `ADR-0008` is titled ADR-000X, and
  `ADR-009` uses three digits where the others use four. **Follow the four-digit
  `ADR-NNNN-kebab-title.md` form and make the title match the filename.** Do not copy the drift.
- **MUST** state the decision, the context that forced it, and the consequences — including what it
  makes harder. An ADR without a cost section is a sales pitch.
- **MUST** record explicit exceptions where they exist, e.g. cadvisor running privileged.
- **SHOULD** reference the enforcing test. A decision nobody checks is a preference.

Existing ADRs worth knowing: ADR-0001 networking and firewall, ADR-0007 secrets and env files,
ADR-0008 bind mounts only, ADR-009 backup/verify/restore.

## Keeping docs honest

`README.md` is stale — it still mentions Prometheus, Loki and Promtail, a different env path, and
has broken relative links (F5). When touching a document, check that what it claims still matches
the repository, and fix or flag what does not.

## Sources

`docs/`, `docs/architecture/adr/`, `ChatGPTHint.txt` §10, `README.md`. Findings F5, F6.
