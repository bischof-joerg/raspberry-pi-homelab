# Backup, Verification, and Restore Procedure

Last updated: 2026-05-27

This runbook defines the operator procedure for the Raspberry Pi GitOps homelab backup lifecycle. The architectural decision behind this runbook is documented in `docs/architecture/adr/ADR-009-backup-verify-restore.md`.

The target operating model is deterministic:

- Git remains the source of truth for declarative configuration.
- Backups cover runtime data, host-only secrets, and selected host evidence.
- Backup artifacts are encrypted with OpenPGP public-key encryption using GnuPG.
- The Pi never stores the backup private key.
- The Pi performs artifact-only verification.
- WSL/Admin performs decrypt verification and restore tests.

---

## 1. Scope

This procedure covers the future `backup`, `backup_verify`, and `restore` scripts for the Raspberry Pi homelab.

Initial stack scope:

```text
monitoring
```

Initial runtime roots:

```text
/srv/backups/homelab
/srv/data/stacks/monitoring
/etc/raspberry-pi-homelab
```

---

## 2. Command Contract

The repository should expose these Make targets:

```bash
make backup
make backup_verify
make restore
```

A compatibility alias may also exist:

```bash
make backup-verify
```

Recommended script layout:

```text
scripts/backup/
  common.sh
  backup.sh
  backup-verify.sh
  restore.sh
```

Recommended local repository paths:

```text
config/backup/homelab-backup-recovery-public.asc
config/backup/homelab-backup-recovery-public.fingerprint
secrets/backup/gpg/                         # local only, Git-ignored
```

The `secrets/` directory must never be committed.

---

## 3. Required Defaults

| Variable | Default | Purpose |
|---|---|---|
| `BACKUP_ROOT` | `/srv/backups/homelab` | Local backup root on Pi |
| `DATA_ROOT` | `/srv/data/stacks` | Persistent bind-mount root |
| `STACK_NAME` | `monitoring` | Initial stack scope |
| `STACK_DATA_ROOT` | `/srv/data/stacks/monitoring` | Monitoring data root |
| `REPO_ROOT` | auto-detected | GitOps repository checkout |
| `COMPOSE_FILE` | `$REPO_ROOT/stacks/monitoring/compose/docker-compose.yml` | Compose file |
| `SECRETS_FILE` | `/etc/raspberry-pi-homelab/monitoring.env` | Authoritative runtime env/secrets file |
| `HOST_SECRETS_DIR` | `/etc/raspberry-pi-homelab` | Host-only env/secrets directory |
| `BACKUP_RETENTION_DAYS` | `7` | Local retention target |
| `BACKUP_SIZE_THRESHOLD_BYTES` | `536870912000` | 500 GB size threshold |
| `BACKUP_MAX_AGE_HOURS` | `36` | Latest verified backup freshness threshold |
| `BACKUP_QUIESCE` | `1` | Stop stack before archiving service data |
| `BACKUP_INCLUDE_METRICS` | `1` | Include VictoriaMetrics archive |
| `BACKUP_INCLUDE_LOGS` | `1` | Include VictoriaLogs archive |
| `BACKUP_INCLUDE_SSH_HOST_KEYS` | `1` | Include encrypted SSH host key archive |
| `GPG_HOME` | `/var/lib/homelab-backup/gnupg` | Pi-side public-key-only GnuPG home |
| `GPG_PUBLIC_KEY_FILE` | `$REPO_ROOT/config/backup/homelab-backup-recovery-public.asc` | Public backup recipient key |
| `GPG_RECIPIENT_FINGERPRINT` | required | Full 40-hex fingerprint of backup recipient |

---

## 4. Backup Procedure on Pi

Run on the Raspberry Pi:

```bash
cd ~/iac/raspberry-pi-homelab
make backup
make backup_verify
```

The backup script must:

1. Acquire the host backup lock.
2. Verify it is running on the Pi unless `HOMELAB_ALLOW_NON_PI=1` is set for tests.
3. Verify the repository checkout and required paths.
4. Verify `/etc/raspberry-pi-homelab/monitoring.env` is `root:root 600`.
5. Verify GnuPG is installed.
6. Import or verify the public backup recipient key under `GPG_HOME`.
7. Verify the public key fingerprint equals `GPG_RECIPIENT_FINGERPRINT`.
8. Stop the monitoring stack if `BACKUP_QUIESCE=1`.
9. Create compressed tar streams with `zstd`.
10. Encrypt each archive stream to the pinned public key.
11. Write encrypted `.tar.zst.gpg` artifacts into the backup bundle.
12. Generate `manifest.json`.
13. Generate `checksums.sha256` for every produced artifact.
14. Restart/reconcile the stack through `sudo ./deploy.sh` if it was stopped.
15. Write logs under the backup bundle.

The Pi must not have:

- the private GPG backup key
- the private-key passphrase
- KeePassXC database files
- plaintext secret archives left on disk

---

## 5. Backup Bundle Format

Each backup is a timestamped directory:

```text
/srv/backups/homelab/<timestamp>/
  manifest.json
  checksums.sha256
  data/
  generated/
  secrets/
  host/
  logs/
```

Example:

```text
/srv/backups/homelab/2026-05-27T203000Z/
  manifest.json
  checksums.sha256
  data/
    monitoring-alertmanager.tar.zst.gpg
    monitoring-grafana.tar.zst.gpg
    monitoring-vector.tar.zst.gpg
    monitoring-victoriametrics.tar.zst.gpg
    monitoring-victorialogs.tar.zst.gpg
  generated/
    monitoring-alertmanager-config.tar.zst.gpg
  secrets/
    etc-raspberry-pi-homelab.tar.zst.gpg
  host/
    docker-daemon.json
    ufw-status-numbered.txt
    ufw-status-verbose.txt
    etc-ufw.tar.zst.gpg
    machine-id.txt
    ssh-host-keys.tar.zst.gpg
    docker-info.txt
    docker-version.txt
    docker-compose-version.txt
    docker-networks.txt
    docker-compose-rendered.yml
    package-list.txt
    os-release.txt
    uname.txt
  logs/
    backup.log
    backup-verify.log
```

Plaintext files in `manifest.json`, `checksums.sha256`, `host/*.txt`, and logs must not contain secrets.

---

## 6. Artifact Inventory

### 6.1 Host-only secrets

| Artifact | Backup | Encryption | Restore mode |
|---|---:|---:|---|
| `/etc/raspberry-pi-homelab/monitoring.env` | Yes | OpenPGP public-key GPG | `root:root 600` |
| `/etc/raspberry-pi-homelab/*.env` | Yes | OpenPGP public-key GPG | `root:root 600` |
| `/etc/raspberry-pi-homelab/*.bak-*` | Yes until cleaned | OpenPGP public-key GPG | Restore only if explicitly selected |
| GHCR credentials inside env files | Yes | OpenPGP public-key GPG | As part of env restore |
| SMTP secrets inside env files | Yes | OpenPGP public-key GPG | As part of env restore |
| Grafana admin credentials inside env files | Yes | OpenPGP public-key GPG | As part of env restore |

### 6.2 Persistent data

| Artifact | Backup | Restore | Notes |
|---|---:|---:|---|
| `/srv/data/stacks/monitoring/grafana` | Yes | Yes | Grafana DB, plugins, generated state |
| `/srv/data/stacks/monitoring/alertmanager` | Yes | Yes | Silences and Alertmanager state |
| `/srv/data/stacks/monitoring/vector` | Yes | Yes | Ingestion offsets/checkpoints |
| `/srv/data/stacks/monitoring/victoriametrics` | Yes by default | Yes by default | Metrics history; not existential |
| `/srv/data/stacks/monitoring/victorialogs` | Yes by default | Yes by default | Log history; not existential |
| `/srv/data/stacks/monitoring/alertmanager-config` | Diagnostic only | No by default | Generated from Git templates and env |

### 6.3 Host evidence

| Artifact | Backup | Restore | Notes |
|---|---:|---:|---|
| `ufw status numbered` | Yes | Manually reconcile | Human-readable evidence |
| `/etc/ufw` | Yes | Carefully, same OS only | Encrypted artifact |
| `/etc/docker/daemon.json` | Yes | Usually recreated by deploy | Also enforced by GitOps script |
| Rendered Compose config | Yes | No | Debugging evidence |
| Docker networks listing | Yes | Recreated by deploy/bootstrap | Diagnostic only |
| Package list | Yes | No | Rebuild evidence |
| `/etc/machine-id` value | Export only | Do not restore blindly | Avoid duplicate host identity |
| `/etc/ssh/ssh_host_*` | Yes | Optional/manual | Encrypted; stable SSH identity only |

---

## 7. Pi-Side Verification: `make backup_verify`

Run after every backup on the Pi:

```bash
cd ~/iac/raspberry-pi-homelab
make backup_verify
```

Pi-side verification must prove:

- selected backup directory exists
- `manifest.json` exists and is valid JSON
- required manifest fields exist
- `checksums.sha256` exists
- all listed checksums match
- encrypted artifacts exist and are non-empty
- encrypted artifacts are valid OpenPGP packets
- expected encrypted artifacts are present
- backup age is within `BACKUP_MAX_AGE_HOURS`
- backup root size is below `BACKUP_SIZE_THRESHOLD_BYTES`
- retention cleanup does not delete the only verified backup

Example packet-level check:

```bash
GNUPGHOME=/var/lib/homelab-backup/gnupg \
  gpg --batch --list-packets secrets/etc-raspberry-pi-homelab.tar.zst.gpg >/dev/null
```

This is artifact verification only. It does not prove that the backup can be decrypted because the Pi does not hold the private key.

The verifier should write:

```text
/srv/backups/homelab/status/latest.json
/srv/backups/homelab/status/latest-success.json
/srv/backups/homelab/status/latest-failure.json
```

---

## 8. WSL/Admin Decrypt Verification

Run on WSL/Admin after pulling or copying a backup from the Pi:

```bash
cd ~/iac/raspberry-pi-homelab
```

Verify the secret archive can be decrypted and listed:

```bash
BACKUP_DIR=/path/to/backup

gpg --decrypt "$BACKUP_DIR/secrets/etc-raspberry-pi-homelab.tar.zst.gpg" \
  | zstd -d \
  | tar -tf - >/dev/null
```

Verify a data archive:

```bash
gpg --decrypt "$BACKUP_DIR/data/monitoring-grafana.tar.zst.gpg" \
  | zstd -d \
  | tar -tf - >/dev/null
```

Restore-test into a local staging directory:

```bash
rm -rf /tmp/homelab-restore-test
mkdir -p /tmp/homelab-restore-test

gpg --decrypt "$BACKUP_DIR/secrets/etc-raspberry-pi-homelab.tar.zst.gpg" \
  | zstd -d \
  | tar --extract --preserve-permissions --numeric-owner --file - --directory /tmp/homelab-restore-test
```

Reject any archive that contains:

- absolute paths outside the expected restore root
- `..` path traversal segments
- unexpected symlinks into sensitive host paths
- empty member names

---

## 9. Restore Controls

Restore is dry-run by default.

| Variable | Default | Purpose |
|---|---|---|
| `RESTORE_BACKUP` | unset | Required path or backup ID |
| `RESTORE_APPLY` | `0` | `0` means dry-run; `1` mutates target |
| `RESTORE_COMPONENTS` | `all` | Comma-separated components or `all` |
| `RESTORE_SECRETS` | `1` | Restore host-only secrets |
| `RESTORE_DATA` | `1` | Restore persistent data archives |
| `RESTORE_SSH_HOST_KEYS` | `0` | Restore SSH host keys only if explicitly enabled |
| `RESTORE_MACHINE_ID` | `0` | Machine ID restore disabled by default |
| `RESTORE_CONFIRM` | unset | Must equal documented confirmation token for destructive restore |
| `RESTORE_TARGET` | unset | Pi SSH target for WSL/Admin-driven restore |

Destructive restore requires:

```bash
RESTORE_APPLY=1 RESTORE_CONFIRM=RESTORE_HOMELAB_DATA
```

---

## 10. Standard Restore from WSL/Admin to Pi

Use this path because the private GPG key stays on WSL/Admin.

1. Select backup:

   ```bash
   BACKUP_DIR=/path/to/verified/backup
   PI_HOST=admin@rpi-hub
   ```

2. Verify decrypt/list locally:

   ```bash
   gpg --decrypt "$BACKUP_DIR/secrets/etc-raspberry-pi-homelab.tar.zst.gpg" \
     | zstd -d \
     | tar -tf - >/dev/null
   ```

3. Stop the stack on the Pi:

   ```bash
   ssh "$PI_HOST" 'cd ~/iac/raspberry-pi-homelab && sudo docker compose --env-file /etc/raspberry-pi-homelab/monitoring.env -f stacks/monitoring/compose/docker-compose.yml down'
   ```

4. Restore host-only secrets:

   ```bash
   gpg --decrypt "$BACKUP_DIR/secrets/etc-raspberry-pi-homelab.tar.zst.gpg" \
     | zstd -d \
     | ssh "$PI_HOST" 'sudo tar --extract --preserve-permissions --numeric-owner --file - --directory /'

   ssh "$PI_HOST" 'sudo chown root:root /etc/raspberry-pi-homelab/*.env && sudo chmod 600 /etc/raspberry-pi-homelab/*.env'
   ```

5. Restore selected data component, example Grafana:

   ```bash
   ssh "$PI_HOST" 'sudo mkdir -p /srv/data/stacks/monitoring /srv/backups/homelab/pre-restore'

   gpg --decrypt "$BACKUP_DIR/data/monitoring-grafana.tar.zst.gpg" \
     | zstd -d \
     | ssh "$PI_HOST" 'sudo tar --extract --preserve-permissions --numeric-owner --file - --directory /srv/data/stacks/monitoring'
   ```

6. Reconcile with GitOps deploy:

   ```bash
   ssh "$PI_HOST" 'cd ~/iac/raspberry-pi-homelab && sudo ./deploy.sh'
   ```

7. Validate:

   ```bash
   ssh "$PI_HOST" 'cd ~/iac/raspberry-pi-homelab && make postdeploy && make backup_verify'
   ```

---

## 11. Fresh OS Restore Order

Use this path after reinstalling Raspberry Pi OS Lite 64-bit.

1. Install baseline OS.
2. Install Git, Docker Engine, Docker Compose plugin, GnuPG, `zstd`, and required tooling.
3. Clone the repository:

   ```bash
   mkdir -p ~/iac
   cd ~/iac
   git clone <repo-url> raspberry-pi-homelab
   cd raspberry-pi-homelab
   ```

4. Import the public GPG key only on the Pi.
5. From WSL/Admin, restore `/etc/raspberry-pi-homelab` by streaming decrypted tar over SSH.
6. From WSL/Admin, restore selected persistent data under `/srv/data/stacks`.
7. Run on the Pi:

   ```bash
   cd ~/iac/raspberry-pi-homelab
   sudo ./deploy.sh
   make postdeploy
   make backup_verify
   ```

Do not restore service data before the Git checkout exists.

Restore order:

```text
OS baseline -> Git checkout -> public GPG key on Pi -> host-only secrets -> persistent data -> deploy -> postdeploy tests
```

---

## 12. What Not To Do

Do not:

- commit runtime `.env` files
- commit the GPG private key
- import the GPG private key onto the Pi during normal operations
- store KeePassXC databases on the Pi
- rely on `stacks/monitoring/compose/.env` for production restore
- restore `/var/lib/docker` as an application backup
- restore runtime sockets
- restore `/etc/machine-id` automatically
- restore SSH host keys automatically
- mix data archives from different backup timestamps unless explicitly documented
- delete old backups before a new backup has passed verification
- leave plaintext secret archives on disk after encryption or decryption

---

## 13. Required Tests

Static checks:

```bash
bash -n scripts/backup/*.sh
shellcheck scripts/backup/*.sh
```

Fixture tests must cover:

- backup creates expected directory layout
- manifest JSON validates
- checksums validate
- GPG public key fingerprint pinning rejects mismatches
- GPG encryption works with only public key material
- Pi-side GPG packet validation works without private key
- WSL/Admin decrypt/list verification works with private key
- unsafe archive members are rejected
- missing secret file fails pre-flight
- wrong `monitoring.env` mode fails pre-flight
- dry-run restore changes nothing
- restore refuses without `RESTORE_APPLY=1`
- restore refuses without `RESTORE_CONFIRM=RESTORE_HOMELAB_DATA`
- retention does not delete the only verified backup

Integration tests on Pi before scheduling backups:

1. Create backup.
2. Verify backup on Pi.
3. Copy or pull backup to WSL/Admin.
4. Run decrypt/list verification on WSL/Admin.
5. Restore into staging.
6. Restore one non-critical component.
7. Run `sudo ./deploy.sh`.
8. Run `make postdeploy`.

---

## 14. Monitoring Requirements

The backup system should expose or write status for:

- age of latest verified backup
- last backup result
- last Pi-side verification result
- last WSL/Admin decrypt verification result
- total size of `/srv/backups/homelab`
- threshold violation above 500 GB
- number of retained backups
- failed GPG encryption
- failed GPG decrypt verification
- failed archive checksum validation

Initial implementation may write JSON files under:

```text
/srv/backups/homelab/status/
```
