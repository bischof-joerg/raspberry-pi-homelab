---
name: new-stack-proposal
description: Draft a complete new Compose stack (compose file, configs, tests, docs, Renovate rule) as a proposal under .claude/scratch/. Use when planning a core or app stack.
---

# New stack proposal

Produces a **proposal**, never a deployment. Output goes to `.claude/scratch/<stack>/` on purpose:
a whole stack is never one commit (IN2), so the proposal is the design, and the real files under
`stacks/`, `tests/` and `docs/` land increment by increment through the `increment-plan` skill.

## Ask first, if unanswered

- Which roadmap stage — R3 core (Traefik) or R4 apps (Stirling PDF, AdGuard Home, Home Assistant)?
- Does the stack need inbound LAN or internet exposure, and through Traefik or directly?
- Does it hold persistent data that must enter the backup inventory?

Do not invent answers to these. A stack designed around a guessed exposure model is worse than no
draft.

## Produce

```text
.claude/scratch/<stack>/
├── compose/docker-compose.yml
├── compose/.env.example
├── <service>/<config files>
├── tests/test_<NN>_<stack>_postdeploy.py
├── docs/<stack>.md
└── PROPOSAL.md        # decisions, open questions, what the operator must check
```

## The compose file must satisfy `compose-stacks.md` from the first draft

Project name `homelab-home-prod-<stack>`; images pinned by full version tag; `monitoring` and
`apps` as **external** networks; bind mounts only, under `/srv/data/stacks/<stack>/<service>/`;
ports on `127.0.0.1` unless exposure is a decision you can name; `read_only`, `cap_drop: [ALL]`,
`no-new-privileges`, an explicit `user:` and a `healthcheck` on every service.

Do not copy the monitoring stack's known defects: no `apk add` at runtime (F8), no floating minor
tag (F37), no service without a config-hash label if it mounts a config (F29), and no Docker socket
mount — `:ro` is not a mitigation (F30), so a socket proxy plus an ADR is the path.

## Every stack ships with

- **Postdeploy tests** — containers healthy, ports reachable, endpoints returning meaningful data.
- **A Renovate rule** for each new image, in the same increment (IN10).
- **`.env.example`** listing every variable, with no values.
- **An increment plan** — a stack is never one commit. Use the `increment-plan` skill.
- **IN9 review** — new persistent data means the backup inventory (ADR-009 §4/§5) changes too.

## Open design questions to surface, not to decide alone

R3 Traefik with a LAN-only Pi needs DNS-01 and a public domain; the provider must be supported by
Traefik's ACME DNS providers, and that is unverified. R4.2 AdGuard needs port 53 and a decision on
client DNS. R4.3 Home Assistant commonly wants host networking, which conflicts with the
explicit-network rule and needs an ADR exception. List these in `PROPOSAL.md` rather than picking
an answer.
