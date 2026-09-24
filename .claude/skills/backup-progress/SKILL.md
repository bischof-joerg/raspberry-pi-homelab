---
name: backup-progress
description: Map ADR-009's backup requirements against the scripts and tests that exist, and list the gaps. Use to answer "how far is the backup" or before any backup increment.
---

# Backup progress

ADR-009 is the contract; `scripts/backup/` is the implementation. This skill reports the delta
honestly, including the part nobody wants to hear.

## The headline, until it changes

**There are no backup tests.** ADR-009 DD-012 requires them *before* scripts are accepted into the
repository, so the current state is not "nearly done" — it is unaccepted by the project's own rule
(F9). Say this first, every time, until `tests/` contains backup tests.

## Collect

```bash
ls scripts/backup/
grep -rn "backup" --include="test_*.py" tests/ | head
grep -nE "^### DD-0[0-9]+|^## [0-9]" docs/architecture/adr/ADR-009-backup-verify-restore.md
grep -nE "^backup|^restore|^backup" Makefile
ls config/backup/ 2>/dev/null || echo "config/backup/ missing"
```

## Report against the contract

| ADR-009 requirement | Where | State |
|---|---|---|
| Exit codes 0/2/3/4/5/6/7 (§2.3) | `scripts/backup/*.sh` | |
| Lock file, fail fast, never wait forever (§2.4) | | |
| Fixture overrides `BACKUP_ROOT`, `DATA_ROOT`, `HOST_SECRETS_DIR`, `SECRETS_FILE`, `HOMELAB_ALLOW_NON_PI=1` (§2.5) | | |
| Restore dry-run by default (DD-013) | `restore.sh` | |
| Public-key GPG; Pi holds no private key (DD-016) | | |
| Artifact inventory current (§4/§5) | | |
| Tests exist (DD-012) | `tests/` | **missing (F9)** |

## Known open items, to confirm rather than repeat

- `docs/operations/GPG_config_for_backup_encryption.md` step 6 — install the public key on the Pi.
- `config/backup/` (public key plus fingerprint) does not exist yet.

## Boundaries

`make backup`, `backup-verify`, `backup_verify`, `backup-verify-decrypt` and `restore` are operator
targets and are never run from here. `make restore` with `RESTORE_TARGET=user@host` streams over
SSH, which is direct Pi access (C5). `gpg` is denied outright (C3). Read the scripts, report the
gaps, propose the commands — the operator executes them.

## Verdict

End with the single next step, and be specific: the next step is a test, not a feature, until
DD-012 is satisfied.
