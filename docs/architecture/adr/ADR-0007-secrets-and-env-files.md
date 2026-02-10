# ADR-0007: Secrets and environment files for Compose-based GitOps deployments

- **Status:** Accepted
- **Date:** 2026-02-10
- **Decision Makers:** Homelab operators
- **Scope:** Raspberry Pi GitOps repo `raspberry-pi-homelab` (Docker Compose stacks)

## Context

This repository follows a strict **IaC + GitOps** operating model:

- The Git repository is the **source of truth** for stack definitions (Compose, configs, tests, docs).
- The Raspberry Pi is a **deploy target only**; no manual drift or ad-hoc edits on the Pi.
- **Secrets must never be committed** to Git (no `.env` with credentials, no tokens, no passwords).

Docker Compose introduces multiple mechanisms for environment variables:

- **`--env-file`**: explicit environment file passed at runtime (recommended for host secrets).
- **Project-level `.env`**: automatically loaded by the Compose CLI from the directory of the Compose file (useful for local CLI ergonomics, but easy to misuse).
- **Environment inherited from the shell**: variables exported by `deploy.sh` (used for host-derived runtime values).

We need a deterministic, testable policy for:

- Secrets vs non-secrets
- Host-derived runtime values
- Local-only Compose CLI defaults
- Documentation of required variables without storing real values in Git

## Decision

We adopt the following layered approach.

### 1) Host secrets live only in `/etc/raspberry-pi-homelab/monitoring.env`

- **All secrets and site-specific runtime configuration** for the monitoring stack are stored on the target host at:

  `/etc/raspberry-pi-homelab/monitoring.env`

- `deploy.sh` (and only `deploy.sh`) loads this file via `docker compose --env-file ...`.
- This file is **not tracked** in Git and is considered **host state**.
- Example contents:
  - Grafana admin credentials (`GRAFANA_ADMIN_PASSWORD`)
  - Alertmanager SMTP credentials (`ALERT_SMTP_AUTH_PASSWORD`)
  - Optional GHCR credentials (`GHCR_PAT`)
  - Service behavior flags (e.g., `ALERT_SMTP_REQUIRE_TLS=true`)

**Rationale:** this file captures **service intent** and secrets, and is the canonical place for sensitive values.

### 2) Compose-directory `.env` is allowed only for local CLI defaults (non-secret) and must not be committed

- A file named `.env` in a stack’s Compose directory may be used **only** to make
  `docker compose ps|logs|config` runnable without warnings when not invoking `deploy.sh`.
- This `.env` must be:
  - **non-secret**
  - **gitignored**
  - clearly labeled as local-only

Typical examples of values allowed in this `.env`:

- Placeholder values to avoid Compose interpolation warnings in local CLI usage.
- Dummy numeric IDs used for validation (e.g., GIDs) that are **not** authoritative.

**Explicitly disallowed in compose-directory `.env`:**

- passwords, tokens, credentials, API keys
- any data that would allow authentication or access escalation
- host-specific secrets that belong in `/etc/.../monitoring.env`

**Rationale:** Compose auto-loads `.env` implicitly; committing it risks secret leakage and configuration drift.

### 3) Host-derived runtime variables must be computed in `deploy.sh`, not stored

Variables derived from host state (and likely different across machines) must be
computed at deploy time by `deploy.sh`, then exported to Compose, e.g.:

- `SYSTEMD_JOURNAL_GID`: derived from the host `systemd-journal` group
- `DOCKER_GID`: derived from `/var/run/docker.sock` group id

These values are **not** secrets, but are **host-specific** and must not become static configuration in `/etc/.../monitoring.env`.

**Rationale:** host-derived values are infrastructure mechanics, not service configuration. Storing them introduces portability and drift risks.

### 4) `.env.example` is documentation only, and must never contain secrets

If `.env.example` exists, it is used purely for documentation:

- It lists variables expected in `/etc/raspberry-pi-homelab/monitoring.env`
- It contains **no real values**
- It may include safe defaults for non-secret boolean flags
- It must not include host-derived runtime values (e.g., GIDs)

Alternatively, if documentation is maintained in Markdown runbooks, `.env.example` may be removed.

**Rationale:** developers need a clear contract of required variables without risk of committing secrets.

## Consequences

### Positive

- Secrets are never committed and are isolated to host-only files.
- Deploys are deterministic: runtime host-derived values come from `deploy.sh`.
- Local CLI usage remains ergonomic without weakening the GitOps model.
- CI/pre-commit can validate Compose config via known safe defaults without requiring access to host secrets.

### Negative / Tradeoffs

- Developers may need a local `.env` (gitignored) to use `docker compose` directly without `deploy.sh`.
- Additional documentation discipline is required (either `.env.example` or runbook sections).
- Some validations require dummy defaults in tests to avoid “unset variable” warnings.

## Implementation details

### Repository rules

- `.env` files are ignored globally (or at minimum for stack compose folders):
  - `stacks/**/compose/.env`
- `/etc/raspberry-pi-homelab/*.env` is host-only and never appears in Git.

### Deploy rules

- `deploy.sh` is the only supported entry point on the Pi.
- `deploy.sh` loads host secrets via `--env-file /etc/raspberry-pi-homelab/monitoring.env`.
- `deploy.sh` computes and exports host-derived values needed for Compose interpolation.

### Testing rules

- Pre-commit/CI may set safe dummy defaults for interpolation-only variables so that
  `docker compose config` validation runs without requiring host secrets.

## Alternatives considered

1) **Commit `.env` in repo**

- Rejected: high risk of secret leakage and drift; violates the “no secrets in Git” policy.

2) **Store host-derived values (GIDs) in `/etc/.../monitoring.env`**

- Rejected: couples service config to a specific host, breaks portability, increases drift after OS/Docker changes.

3) **Rely only on shell exports**

- Rejected: decreases determinism and auditability; explicit `--env-file` on the host provides a clearer contract.

## Decision summary

- **Secrets & service configuration:** `/etc/raspberry-pi-homelab/monitoring.env` (host-only)
- **Host-derived runtime values:** computed in `deploy.sh` and exported (never persisted as config)
- **Local Compose CLI defaults:** optional compose-directory `.env` (non-secret, gitignored)
- **Documentation:** `.env.example` (no secrets) or runbook docs
