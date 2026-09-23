---
paths:
  - "scripts/backup/**"
  - "docs/operations/BackupVerifyRestore.md"
  - "docs/operations/GPG_config_for_backup_encryption.md"
---

# Backup, verify, restore

Status: **in progress.** `backup.sh`, `backup-verify.sh`, `restore.sh` and `common.sh` exist;
**no tests exist yet.** ADR-009 is the contract and it is binding.

## The blocking rule — DD-012

> "`backup`, `backup_verify`, and `restore` scripts must include focused tests before being
> accepted into the repository."

Tests are therefore not a follow-up increment. Any change here ships with its tests, and the
missing tests (F9) are a debt to close, not a precedent to extend.

## MUST

- **Use the ADR's exit codes** — they are a contract that tests and future alerts depend on:

  | Code | Meaning |
  |---:|---|
  | `0` | success |
  | `2` | invalid usage, missing config, failed pre-flight |
  | `3` | backup verification failed |
  | `4` | restore safety guard refused the operation |
  | `5` | GPG encrypt (Pi) or decrypt (WSL) failed |
  | `6` | archive create/list/extract failed |
  | `7` | deploy or postdeploy validation failed |

- **Restore is dry-run by default** (DD-013). Acting requires an explicit opt-in, and a refusing
  safety guard exits `4` rather than continuing.
- **Lock against concurrency** via a host lock file such as `/run/lock/homelab-backup.lock`.
  Fail fast when another run holds it — never wait forever.
- **Keep the fixture overrides working.** The scripts must be testable from WSL without touching
  real Pi paths: `BACKUP_ROOT`, `DATA_ROOT`, `HOST_SECRETS_DIR`, `SECRETS_FILE`,
  `HOMELAB_ALLOW_NON_PI=1`. Production execution still requires the Pi unless explicitly overridden.
- **Public-key GPG only.** The Pi encrypts with the public key; it never holds the private key.
  The private key lives in the WSL working tree under git-ignored `secrets/backup/gpg/` — **never
  read it** (C3), never print a passphrase, never add key material to a test fixture.
- **Update the artifact inventory** (ADR-009 §4/§5) whenever an increment adds persistent data,
  a host secret, or a new bind mount. A backup that silently misses new data is worse than none.

## Claude must not run any of this

`make backup`, `backup-verify`, `backup_verify`, `backup-verify-decrypt`, `restore` are operator
targets. `make restore` supports `RESTORE_TARGET=user@host` and streams over SSH; that is direct Pi
access and is denied (C5/K7). `gpg` is denied outright. Propose the command, let the operator run it.

## Open work

- No tests at all (F9) — the first thing any backup increment must fix.
- `docs/operations/GPG_config_for_backup_encryption.md` step 6, installing the public key on the
  Pi, is the next open manual step.
- `config/backup/` (public key + fingerprint) does not exist yet.

## Sources

`docs/architecture/adr/ADR-009-backup-verify-restore.md` §2.3 exit codes, §2.4 locking, §2.5 test
mode, §4/§5 inventory, DD-012, DD-013; `scripts/backup/`;
`docs/operations/BackupVerifyRestore.md`; `docs/operations/GPG_config_for_backup_encryption.md`.
