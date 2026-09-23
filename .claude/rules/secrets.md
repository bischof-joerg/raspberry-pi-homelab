---
paths:
  - "**/*.env.example"
  - "stacks/**/compose/**"
  - "scripts/backup/**"
---

# Secrets

ADR-0007 defines one model, and it has a single rule at its core: **secrets live on the host
filesystem, never in Git, and never in the repository working tree.**

## The model

- Runtime secrets live in `/etc/raspberry-pi-homelab/monitoring.env`, owned `root:root`, mode `600`.
- `deploy.sh` loads them with `docker compose --env-file`. Nothing else reads them.
- A repo-root `.env` is **refused** by `deploy.sh` — it is not a fallback, it is an error
  (`deploy.sh:109`, `die "Refusing repo-root .env …"`).
- A `.env` **in a stack's compose directory is allowed** (ADR-0007 §2), but only to make
  `docker compose ps|logs|config` run without interpolation warnings outside `deploy.sh`. It must be
  non-secret, gitignored, and labelled local-only. Passwords, tokens, credentials, API keys and
  anything belonging in `/etc/…/monitoring.env` are explicitly disallowed there.
- `.env.example` documents the required variable names and structure, with **no real values**.
- Host-derived values such as `DOCKER_GID` and `SYSTEMD_JOURNAL_GID` are computed in `deploy.sh`
  at deploy time. They do not belong in `.env.example` — `.env.example` currently lists them twice
  and carries host-derived values, contradicting ADR-0007 §4 (F12).

## MUST

- **Never read secret material** (C3): `secrets/**`, `*.env`, `*.kdbx`, `*.keyx`, `*.pem`, `*.key`,
  `*.p12`, `*.pfx`, `~/.ssh/**`, `~/.gnupg/**`, `~/.config/renovate/**`,
  `/etc/raspberry-pi-homelab/**`. `.env.example` is explicitly fine.
- **Never put a value in `.env.example`.** Variable name, a comment on what it is, and an empty or
  obviously-fake placeholder. If a reader could paste it and have it work, it is a secret.
- **Never reference a secret by value in compose, a script, a test fixture, a log line or a commit
  message.** Reference the variable name.
- **Add the variable to `.env.example` in the same increment** that introduces it, or the next
  person deploying gets a runtime failure with no clue what is missing.
- **Keep GPG private key material out of the repository.** It lives in git-ignored
  `secrets/backup/gpg/` in the WSL tree; the Pi holds only the public key.

## If a secret is found in Git

Treat it as leaked. Rotate it first, then remove it from the tree. Removing it from the working
copy does not un-leak it from the history — say so plainly rather than implying the problem is
solved by a commit.

## Checks that already exist

- `tests/precommit/test_10_no_tracked_env_and_secrets.py` fails if a tracked path is named like a
  secret or sits under a `secrets` directory.
- `tests/precommit/test_45_gitleaks.py` scans content.
- The root `.gitignore` ignores `.env`, `*.env`, `**/*.pem`, `**/*.key`, `/secrets/`, `*.kdbx`,
  `*.keyx`, with `!.env.example` and `!*.env.example` carved out.
- `.claude/.gitignore` keeps `settings.local.json` out of Git (C3).

A passing scanner is not proof of absence. It is one layer.

## Sources

`docs/architecture/adr/ADR-0007-secrets-and-env-files.md`, `deploy.sh`,
`stacks/monitoring/compose/.env.example`, `.gitignore`,
`tests/precommit/test_10_no_tracked_env_and_secrets.py`, `tests/precommit/test_45_gitleaks.py`.
Finding F12.
