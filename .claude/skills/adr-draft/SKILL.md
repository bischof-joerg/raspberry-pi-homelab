---
name: adr-draft
description: Draft an architecture decision record into .claude/scratch/ for operator review. Use when a decision constrains later work.
---

# ADR draft

Writes to `.claude/scratch/ADR-NNNN-<kebab-title>.md`. The operator moves it into
`docs/architecture/adr/` once accepted — an ADR is accepted by a person, not by a file being saved.

## When an ADR is warranted

Write one when the decision **constrains later work**: a boundary, a protocol, a data model, an
exception to a standing rule. Not for a choice a future increment can reverse freely — that belongs
in the commit message.

Current examples of the right altitude: bind mounts only (ADR-0008), secrets live host-only
(ADR-0007), public-key GPG as the backup encryption boundary (ADR-009 DD-016).

## Numbering and naming — do not copy the existing drift

Use `ADR-NNNN-kebab-title.md` with **four digits**, and make the title inside the file match the
filename. The existing set is inconsistent (F6): `ADR-0001-networking-and-firewall.md` is titled
"ADR-0004", `ADR-0008` is titled "ADR-000X", and `ADR-009` uses three digits. Check the highest
existing number before picking one.

## Structure

```markdown
# ADR-NNNN: <title matching the filename>

- **Status:** Proposed
- **Date:** <YYYY-MM-DD>
- **Scope:** <what this governs>

## Context
What forces the decision. Include the constraint that makes the easy option unavailable.

## Decision
Numbered, testable statements. "All X MUST live under Y" beats "we prefer Y".

## Alternatives considered
Each with the reason it was rejected. An ADR with no rejected alternative was not a decision.

## Consequences
### Positive
### Negative / Tradeoffs
What this makes harder, slower or more expensive. **An ADR without a cost section is a sales pitch.**

## Enforcement
The test or check that proves the decision holds. A decision nobody checks is a preference.
```

## Two rules the existing ADRs have broken

- **State only what is implemented, or say plainly that it is not yet.** ADR-0001 promises subnet
  overlap validation that the deploy path does not perform (F43). An aspirational sentence in an
  accepted ADR is worse than an honest "not yet implemented".
- **Record the decision where the rule points.** The LAN exposure of ports 3000 and 9428 is treated
  as deliberate, but no ADR mentions either port (F42).

## Output

Draft to `.claude/scratch/`, then summarise in chat: the decision in one sentence, the main cost,
and the open questions the operator must resolve before status moves to Accepted.
