# ADR-009: Backup, Verification, Restore, and GPG Encryption Architecture

Last updated: 2026-05-27

This runbook defines the backup and restore operating model for the Raspberry Pi GitOps homelab. It is the source specification for the future `backup`, `backup_verify`, and `restore` scripts.

The runbook is intentionally specific to the current monitoring stack and host layout. When new stacks are added, update the artifact inventory before implementing or changing backup scripts.

---

## 1. Purpose

The goal is a boring, deterministic, testable recovery path.

Backups must cover:

- host-only secrets and runtime environment files
- persistent bind-mounted service data
- selected host configuration exports
- enough metadata to verify and restore the backup safely

Backups must not replace GitOps. Git remains the authoritative source for application and infrastructure configuration. Backups preserve runtime data and host-local secrets that are intentionally not stored in Git.

---

## 2. Script Contract

The future implementation should expose these Make targets:

```bash
make backup
make backup_verify
make restore
```

An optional compatibility alias may also be provided:

```bash
make backup-verify
```

Recommended script layout:

```text
scripts/
  backup/
    common.sh
    backup.sh
    backup-verify.sh
    restore.sh
```

### 2.1 Required defaults

| Variable | Default | Purpose |
|---|---|---|
| `BACKUP_ROOT` | `/srv/backups/homelab` | Local backup root |
| `DATA_ROOT` | `/srv/data/stacks` | Persistent bind-mount root |
| `STACK_NAME` | `monitoring` | Initial stack scope |
| `STACK_DATA_ROOT` | `/srv/data/stacks/monitoring` | Monitoring data root |
| `REPO_ROOT` | auto-detected from script path or current repo | GitOps repository |
| `COMPOSE_FILE` | `$REPO_ROOT/stacks/monitoring/compose/docker-compose.yml` | Compose file |
| `SECRETS_FILE` | `/etc/raspberry-pi-homelab/monitoring.env` | Authoritative env/secrets file |
| `HOST_SECRETS_DIR` | `/etc/raspberry-pi-homelab` | Host-only env/secrets directory |
| `BACKUP_RETENTION_DAYS` | `7` | Local retention target |
| `BACKUP_SIZE_THRESHOLD_BYTES` | `536870912000` | 500 GB size threshold |
| `BACKUP_MAX_AGE_HOURS` | `36` | Latest verified backup freshness threshold |
| `BACKUP_QUIESCE` | `1` | Stop stack before archiving data |
| `BACKUP_INCLUDE_METRICS` | `1` | Include VictoriaMetrics archive |
| `BACKUP_INCLUDE_LOGS` | `1` | Include VictoriaLogs archive |
| `BACKUP_INCLUDE_SSH_HOST_KEYS` | `1` | Include encrypted SSH host key archive |
| `GPG_HOME` | `/var/lib/homelab-backup/gnupg` | Dedicated GnuPG home on the Pi; contains public keys only |
| `GPG_PUBLIC_KEY_FILE` | `$REPO_ROOT/config/backup/homelab-backup-recovery-public.asc` | Git-tracked public backup recipient key |
| `GPG_RECIPIENT_FINGERPRINT` | unset | Required full 40-hex fingerprint of the backup recipient key |
| `GPG_PRIVATE_KEY_DIR` | `$REPO_ROOT/secrets/backup/gpg` | Local WSL/Admin-only, Git-ignored private-key material directory |

### 2.2 Restore controls

Restore must be intentionally guarded. Recommended controls:

| Variable | Default | Purpose |
|---|---|---|
| `RESTORE_BACKUP` | unset | Required path or backup ID to restore |
| `RESTORE_APPLY` | `0` | `0` means dry-run only; `1` applies changes |
| `RESTORE_COMPONENTS` | `all` | Comma-separated data components or `all` |
| `RESTORE_SECRETS` | `1` | Restore host-only secrets |
| `RESTORE_DATA` | `1` | Restore persistent data archives |
| `RESTORE_SSH_HOST_KEYS` | `0` | Restore SSH host keys only if explicitly enabled |
| `RESTORE_MACHINE_ID` | `0` | Machine ID restore disabled by default |
| `RESTORE_CONFIRM` | unset | Must be set to a documented confirmation string for destructive restore |

Recommended destructive restore confirmation:

```bash
RESTORE_APPLY=1 RESTORE_CONFIRM=RESTORE_HOMELAB_DATA make restore RESTORE_BACKUP=/srv/backups/homelab/<timestamp>
```

### 2.3 Exit codes

Scripts should use stable exit codes so CI/tests and future alerts can distinguish failures.

| Exit code | Meaning |
|---:|---|
| `0` | Success |
| `2` | Invalid usage, missing config, or failed pre-flight |
| `3` | Backup verification failed |
| `4` | Restore safety guard refused the operation |
| `5` | GPG encryption failed on Pi or decryption failed on WSL/Admin |
| `6` | Archive creation/listing/extraction failed |
| `7` | Deploy or postdeploy validation failed |

### 2.4 Locking

Backup and restore must not run concurrently.

Use a host-level lock file, for example:

```text
/run/lock/homelab-backup.lock
```

The first implementation should fail fast if another backup or restore is active. It must not silently wait forever.

### 2.5 Test mode

The implementation must be testable from WSL without touching the real Pi paths.

The scripts should support fixture overrides such as:

```bash
BACKUP_ROOT=/tmp/homelab-test/backups
DATA_ROOT=/tmp/homelab-test/data/stacks
HOST_SECRETS_DIR=/tmp/homelab-test/etc/raspberry-pi-homelab
SECRETS_FILE=/tmp/homelab-test/etc/raspberry-pi-homelab/monitoring.env
HOMELAB_ALLOW_NON_PI=1
```

Production execution must still require the Raspberry Pi target unless explicitly overridden for tests.

---

## 3. Standard Procedure

### 3.1 Create a backup

Run on the Raspberry Pi:

```bash
cd ~/iac/raspberry-pi-homelab

make backup
make backup_verify
```

The backup script must create a timestamped local backup bundle under:

```text
/srv/backups/homelab
```

The bundle must contain:

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

Backup archives must use OpenPGP public-key encryption with GnuPG. The Raspberry Pi encrypts compressed tar artifacts to the dedicated `Homelab Backup Recovery` public key and never stores the corresponding private key. The standard artifact extension is `.tar.zst.gpg`. Plaintext metadata such as `manifest.json`, `checksums.sha256`, and status files may remain readable because they are needed for Pi-side artifact verification; they must not contain secrets.

### 3.2 Verify a backup

Run after every backup:

```bash
make backup_verify
```

Verification must prove at minimum:

- `manifest.json` exists and is valid JSON
- required manifest fields are present
- every file listed in `checksums.sha256` exists
- every checksum matches
- every plaintext archive created during the backup phase is listed before encryption
- archive members are relative and do not contain unsafe `..` traversal entries
- encrypted archives are valid OpenPGP packets on the Pi
- encrypted archives are addressed to the pinned backup-recipient fingerprint where recipient metadata is available
- full decrypt/list verification is performed only on WSL/Admin, where the private key exists
- the backup root has not exceeded the configured size threshold
- the latest verified backup is recent enough for the configured policy

The backup size alert threshold is:

```text
500 GB
```

### 3.3 Restore on the same host

Use this path when the OS and repository are still intact, but service data or secrets must be restored.

1. Confirm the target backup:

   ```bash
   ls -lh /srv/backups/homelab
   ```

2. Verify the selected backup:

   ```bash
   RESTORE_BACKUP=/srv/backups/homelab/<timestamp> make backup_verify
   ```

3. Dry-run restore:

   ```bash
   RESTORE_BACKUP=/srv/backups/homelab/<timestamp> make restore
   ```

4. Apply restore:

   ```bash
   sudo RESTORE_BACKUP=/srv/backups/homelab/<timestamp> \
     RESTORE_APPLY=1 \
     RESTORE_CONFIRM=RESTORE_HOMELAB_DATA \
     make restore
   ```

5. Validate:

   ```bash
   make postdeploy
   make backup_verify
   ```

### 3.4 Restore after fresh OS install

Use this path for a clean Raspberry Pi OS install on the same Pi or a replacement Pi.

1. Install Raspberry Pi OS Lite 64-bit.
2. Install Git, Docker Engine, and Docker Compose plugin.
3. Clone the repository:

   ```bash
   mkdir -p ~/iac
   cd ~/iac
   git clone <repo-url> raspberry-pi-homelab
   cd raspberry-pi-homelab
   ```

4. Restore `/etc/raspberry-pi-homelab` host-only secrets.
5. Restore selected host identity artifacts only if explicitly intended.
6. Restore persistent bind-mounted data under `/srv/data/stacks`.
7. Run:

   ```bash
   sudo ./deploy.sh
   ```

8. Validate:

   ```bash
   make postdeploy
   make backup_verify
   ```

Do not restore service data before the Git checkout exists. Restore order is:

```text
OS baseline -> Git checkout -> host-only secrets -> persistent data -> deploy -> postdeploy tests
```

---

## 4. Current Backup-Relevant Reality

### 4.1 Runtime env files

The current deploy path uses one authoritative host-only environment file:

```text
/etc/raspberry-pi-homelab/monitoring.env
```

Observed on the host:

```text
600 root:root /etc/raspberry-pi-homelab/monitoring.env
```

The backup scope includes:

| Artifact | Policy |
|---|---|
| `/etc/raspberry-pi-homelab/monitoring.env` | Back up encrypted with GPG |
| Any future `/etc/raspberry-pi-homelab/*.env` | Back up encrypted |
| `/etc/raspberry-pi-homelab/*.bak-*` | Back up encrypted until cleaned up; restore only if explicitly selected |
| `stacks/monitoring/compose/.env.example` | Git-tracked example only; not backed up as secret |
| `stacks/monitoring/compose/.env` | Non-authoritative local artifact; do not rely on it for deploy; migrate unique values into `/etc/raspberry-pi-homelab/monitoring.env` and delete if possible |

`deploy.sh` refuses a repository-root `.env` file and validates that the active `SECRETS_FILE` exists, is readable, is owned by `root:root`, and has mode `600`.

### 4.2 Persistent service data

The current monitoring stack uses deterministic bind mounts under:

```text
/srv/data/stacks/monitoring
```

These are the currently observed data directories:

| Path | Owner/mode observed | Backup policy |
|---|---:|---|
| `/srv/data/stacks/monitoring/alertmanager` | `750 nobody:nogroup` | Back up and restore |
| `/srv/data/stacks/monitoring/alertmanager-config` | `750 root:nogroup`, `alertmanager.yml` `640` (was `755 root:root` / `644` until R1.1, finding F26) | Do not treat as authoritative; recreate from Git + env; include as generated diagnostics only |
| `/srv/data/stacks/monitoring/grafana` | `750 472:472` | Back up and restore |
| `/srv/data/stacks/monitoring/vector` | `750 65532:65532` | Back up and restore |
| `/srv/data/stacks/monitoring/victorialogs` | `750 root:root` | Back up by default; restore by default; acceptable to lose history if explicitly selected |
| `/srv/data/stacks/monitoring/victoriametrics` | `750 root:root` | Back up by default; restore by default; acceptable to lose history if explicitly selected |

Subdirectories inherit the same backup policy as their parent directory unless explicitly excluded.

### 4.3 Rendered bind mounts

The rendered monitoring stack includes these backup-relevant host mounts:

| Host path | Purpose | Backup policy |
|---|---|---|
| `/srv/data/stacks/monitoring/alertmanager` | Alertmanager runtime state | Back up and restore |
| `/srv/data/stacks/monitoring/alertmanager-config` | Rendered Alertmanager config output | Recreate; do not restore as authoritative |
| `/srv/data/stacks/monitoring/grafana` | Grafana DB, plugins, generated state | Back up and restore |
| `/srv/data/stacks/monitoring/vector` | Vector checkpoints/state | Back up and restore |
| `/srv/data/stacks/monitoring/victorialogs` | VictoriaLogs store | Back up by default |
| `/srv/data/stacks/monitoring/victoriametrics` | VictoriaMetrics TSDB | Back up by default |
| `/etc/machine-id` | Host identity read by containers | Export value; do not restore blindly |
| `/run/log/journal` | Runtime journald source | Do not back up |
| `/var/log/journal` | Persistent journald source | Do not back up by default; Vector/VictoriaLogs are the application log path |
| `/var/run/docker.sock` | Runtime Docker socket | Do not back up |
| `/run/containerd/containerd.sock` | Runtime containerd socket | Do not back up |
| `/sys`, `/sys/fs/cgroup`, `/`, `/var/lib/docker` | Read-only host observation mounts | Do not back up from this stack definition |

---

## 5. Artifact Inventory

### 5.1 Authoritative Git state

| Artifact | Backup? | Restore source |
|---|---:|---|
| Repository files | No separate Pi backup required | Git remote |
| Compose files | No separate Pi backup required | Git |
| Grafana provisioning | No separate Pi backup required | Git |
| Grafana dashboards | No separate Pi backup required | Git |
| vmagent config | No separate Pi backup required | Git |
| vmalert config and rules | No separate Pi backup required | Git |
| Vector config | No separate Pi backup required | Git |
| Alertmanager templates and template source config | No separate Pi backup required | Git |

### 5.2 Host-only secrets

| Artifact | Backup? | Encryption | Restore mode |
|---|---:|---:|---|
| `/etc/raspberry-pi-homelab/monitoring.env` | Yes | GPG | `root:root 600` |
| `/etc/raspberry-pi-homelab/*.env` | Yes | GPG | `root:root 600` |
| `/etc/raspberry-pi-homelab/*.bak-*` | Yes, until cleaned up | GPG | Restore only if needed |
| GHCR credentials inside env file | Yes, as part of env file | GPG | `root:root 600` |
| SMTP secrets inside env file | Yes, as part of env file | GPG | `root:root 600` |
| Grafana admin credentials inside env file | Yes, as part of env file | GPG | `root:root 600` |

### 5.3 Persistent data

| Artifact | Backup? | Restore? | Notes |
|---|---:|---:|---|
| `/srv/data/stacks/monitoring/grafana` | Yes | Yes | Required for Grafana DB, plugins, state |
| `/srv/data/stacks/monitoring/alertmanager` | Yes | Yes | Required for silences and Alertmanager state |
| `/srv/data/stacks/monitoring/vector` | Yes | Yes | Preserves ingestion offsets/checkpoints |
| `/srv/data/stacks/monitoring/victoriametrics` | Yes by default | Yes by default | Metrics history is useful but not mandatory |
| `/srv/data/stacks/monitoring/victorialogs` | Yes by default | Yes by default | Logs are useful but not mandatory; capped separately by VictoriaLogs |
| `/srv/data/stacks/monitoring/alertmanager-config` | Diagnostic only | No by default | Generated from Git templates and env |

### 5.4 Host configuration exports

| Artifact | Backup? | Restore? | Notes |
|---|---:|---:|---|
| `ufw status numbered` output | Yes | Manually reconcile | Human-readable restore evidence |
| `/etc/ufw` | Yes | Carefully, same OS only | Useful for full host recovery |
| `/etc/docker/daemon.json` | Yes | Usually recreated by deploy | Also enforced by GitOps script |
| Rendered Compose config | Yes | No | Debugging and restore evidence |
| Docker networks listing | Yes | Recreated by deploy/bootstrap | Export for diagnostics |
| Docker version / Compose version | Yes | No | Manifest/debugging only |
| Package list | Yes | No | Debugging and rebuild evidence |
| `/etc/machine-id` value | Export only | Do not restore blindly | Restoring can duplicate host identity |
| `/etc/ssh/ssh_host_*` | Yes | Optional/manual | Restore only if stable SSH host identity is desired |

### 5.5 Explicit exclusions

Do not back up these as part of the application backup:

| Artifact | Reason |
|---|---|
| `/var/run/docker.sock` | Runtime socket |
| `/run/containerd/containerd.sock` | Runtime socket |
| `/run/log/journal` | Runtime journal |
| `/sys`, `/proc`, `/dev`, cgroups | Runtime/kernel state |
| Container writable layers | Recreated from images and bind mounts |
| Docker image layers | Re-pulled by deploy |
| Docker build cache | Recreated |
| Repository `.venv` and Python cache | Recreated locally |
| Repo-local `__pycache__` | Recreated |
| Repo-root `.env` | Invalid by policy |
| `stacks/monitoring/compose/.env` | Non-authoritative; migrate and remove |

---

## 6. Backup Strategy

### 6.1 Frequency

| Trigger | Required action |
|---|---|
| Daily | Run `make backup && make backup_verify` |
| Before host runtime upgrade | Run `make backup && make backup_verify` |
| Before major OS upgrade | Run `make backup && make backup_verify`; copy backup off-device manually until remote sync exists |
| After secrets change | Run `make backup && make backup_verify` |
| After service topology change | Update this runbook first, then run backup and verification |
| Before destructive restore test | Run backup and verification |

### 6.2 Retention

Default retention:

```text
7 days
```

Retention cleanup must not delete the only verified backup. Cleanup may run only after a new backup has passed verification.

Recommended first implementation:

- `backup.sh` creates a new bundle but does not prune.
- `backup-verify.sh` verifies the selected or latest backup.
- If verification succeeds, `backup-verify.sh` may prune backups older than `BACKUP_RETENTION_DAYS`, while keeping at least the latest verified backup.

### 6.3 Size alert

The backup verification script must alert or fail when:

```bash
du -sb /srv/backups/homelab > 536870912000
```

This is a 500 GB threshold. The first implementation may fail the verification target. Later this can be integrated into Alertmanager.

### 6.4 Local-only phase

The first implementation creates local backup bundles only.

Out of scope for the first script version:

- NAS copy
- S3/object storage copy
- off-site replication
- filesystem snapshot integration
- automated remote retention

These can be added after local backup/restore correctness is proven.

---

## 7. Backup Bundle Format

Each backup must be self-describing.

Example layout:

```text
/srv/backups/homelab/2026-05-22T203000Z/
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

### 7.1 Manifest requirements

`manifest.json` must include at least:

```json
{
  "schema_version": 1,
  "created_at_utc": "2026-05-22T20:30:00Z",
  "hostname": "rpi-hub",
  "repo_root": "/home/admin/iac/raspberry-pi-homelab",
  "git_commit": "unknown",
  "git_status_clean": true,
  "backup_root": "/srv/backups/homelab",
  "backup_id": "2026-05-22T203000Z",
  "compose_file": "stacks/monitoring/compose/docker-compose.yml",
  "secrets_file": "/etc/raspberry-pi-homelab/monitoring.env",
  "data_root": "/srv/data/stacks/monitoring",
  "included_paths": [],
  "excluded_paths": [],
  "archives": [],
  "encrypted_archives": [],
  "host_exports": [],
  "options": {
    "backup_quiesce": true,
    "include_metrics": true,
    "include_logs": true
  },
  "notes": []
}
```

The scripts may extend this schema, but must not remove existing fields without updating this runbook.

### 7.2 Checksum requirements

`checksums.sha256` must include all generated artifacts except `checksums.sha256` itself.

It must include:

- `manifest.json`
- every file under `data/`
- every file under `generated/`
- every file under `secrets/`
- every file under `host/`
- every file under `logs/` that exists before checksum generation

Verification must run:

```bash
sha256sum -c checksums.sha256
```

from the backup bundle directory.

---

## 8. Backup Procedure Details

### 8.1 Pre-flight checks

The backup script must check:

- running on the Raspberry Pi target, not the WSL dev machine, unless `HOMELAB_ALLOW_NON_PI=1` is set for tests
- `docker` and `docker compose` are available
- repository exists
- `git rev-parse HEAD` succeeds
- `/etc/raspberry-pi-homelab/monitoring.env` exists with `root:root 600`
- `/srv/data/stacks/monitoring` exists
- `/srv/backups/homelab` exists or can be created
- enough free space is available for a local backup
- `gpg` is installed
- no repo-root `.env` exists
- `stacks/monitoring/compose/.env` is either absent or recorded as a non-authoritative warning in the manifest

### 8.2 Free-space policy

Before archiving, estimate source data size with:

```bash
du -sb /srv/data/stacks/monitoring /etc/raspberry-pi-homelab
```

Then compare with available space under `BACKUP_ROOT`.

The first implementation may use a conservative rule:

```text
available bytes must be greater than estimated source bytes
```

This is conservative because compression may reduce size, but it avoids predictable backup failures.

### 8.3 Stack quiescing policy

Default first implementation:

- Stop the monitoring stack before archiving persistent data.
- Archive data.
- Start the stack again with `sudo ./deploy.sh`.
- Let deploy run postdeploy tests by default.

Reason: this is slower but simpler and safer than live-copying TSDB and SQLite-like service state.

Required failure behavior:

- If the script stopped the stack, it must attempt to run `sudo ./deploy.sh` in an `EXIT` trap unless explicitly disabled for tests.
- If archiving fails, the script must still attempt to restart the stack.
- The script must record restart/deploy result in `logs/backup.log` and `manifest.json` notes.

Future improvement:

- Add service-specific online snapshot support where available.
- Allow `BACKUP_QUIESCE=0` only after backup consistency has been proven.

### 8.4 Data archives

Archive these paths:

```text
/srv/data/stacks/monitoring/alertmanager
/srv/data/stacks/monitoring/grafana
/srv/data/stacks/monitoring/vector
/srv/data/stacks/monitoring/victoriametrics
/srv/data/stacks/monitoring/victorialogs
```

Archive this path as generated/diagnostic, not authoritative restore state:

```text
/srv/data/stacks/monitoring/alertmanager-config
```

Each archive must preserve:

- numeric owner
- numeric group
- mode
- symlinks
- timestamps

Recommended command shape:

```bash
sudo tar --create --numeric-owner --one-file-system \
  -C /srv/data/stacks/monitoring \
  grafana \
  | zstd -T0 -19 \
  | GNUPGHOME=/var/lib/homelab-backup/gnupg \
      gpg --batch --yes --trust-model always \
        --encrypt \
        --recipient "$GPG_RECIPIENT_FINGERPRINT" \
        --output data/monitoring-grafana.tar.zst.gpg
```

Restore must decrypt on WSL/Admin or another approved recovery workstation, extract as root on the Pi, and preserve numeric owner information.

### 8.5 Secrets archive

Encrypt the entire host-only env directory:

```text
/etc/raspberry-pi-homelab
```

Use OpenPGP public-key encryption with GnuPG. The Pi uses only the public `Homelab Backup Recovery` key. The private key must never be imported into the Pi GnuPG home.

Required properties:

- output must be `.tar.zst.gpg`
- plaintext tar streams must not remain on disk after encryption
- the recipient must be the full pinned `GPG_RECIPIENT_FINGERPRINT`
- the public key fingerprint must be verified before encryption
- no GPG passphrase file is required or allowed on the Pi for backup creation
- restore procedure must verify target file ownership and mode after decryption

Recommended non-interactive shape on the Pi:

```bash
sudo tar --create --numeric-owner -C /etc raspberry-pi-homelab   | zstd -T0 -19   | GNUPGHOME=/var/lib/homelab-backup/gnupg       gpg --batch --yes --trust-model always         --encrypt         --recipient "$GPG_RECIPIENT_FINGERPRINT"         --output secrets/etc-raspberry-pi-homelab.tar.zst.gpg
```

The only GPG material on the Pi is the public keyring under `GPG_HOME`. The WSL/Admin private-key export may exist in the local repository working tree only under a Git-ignored path such as `secrets/backup/gpg/`.

### 8.6 Host configuration exports

Export at least:

```bash
cat /etc/os-release > host/os-release.txt
uname -a > host/uname.txt
docker version > host/docker-version.txt
docker info > host/docker-info.txt
docker compose version > host/docker-compose-version.txt
docker network ls > host/docker-networks.txt
docker compose --env-file /etc/raspberry-pi-homelab/monitoring.env \
  -f stacks/monitoring/compose/docker-compose.yml \
  config > host/docker-compose-rendered.yml
sudo ufw status numbered > host/ufw-status-numbered.txt
sudo ufw status verbose > host/ufw-status-verbose.txt
sudo tar -cpf - -C / etc/ufw | zstd -T0 -19 | gpg --batch --yes --trust-model always --encrypt --recipient "$GPG_RECIPIENT_FINGERPRINT" --output host/etc-ufw.tar.zst.gpg
sudo cp /etc/docker/daemon.json host/docker-daemon.json
cat /etc/machine-id > host/machine-id.txt
dpkg-query -W > host/package-list.txt
```

SSH host keys are sensitive host identity material. Back them up encrypted:

```text
/etc/ssh/ssh_host_*
```

Do not restore SSH host keys automatically unless the operator explicitly requests stable host identity.

---

## 9. Backup Verification Details

### 9.1 Selecting a backup

`backup-verify.sh` must verify one of:

1. `RESTORE_BACKUP` if set.
2. `BACKUP_DIR` if set.
3. the latest backup under `BACKUP_ROOT` if neither is set.

The selected path must contain `manifest.json` and `checksums.sha256`.

### 9.2 Manifest validation

The first implementation may validate manifest JSON with Python standard library:

```bash
python3 -m json.tool manifest.json >/dev/null
```

It must additionally check required keys, at minimum:

- `schema_version`
- `created_at_utc`
- `hostname`
- `backup_root`
- `backup_id`
- `secrets_file`
- `data_root`
- `archives`
- `encrypted_archives`

### 9.3 Archive validation

During backup creation, every tar stream must be listed before encryption or recorded through an equivalent member manifest. For every plaintext archive member list, verify that member paths are safe:

- no absolute paths
- no path segments equal to `..`
- no empty member names

After encryption, Pi-side verification validates encrypted artifacts rather than plaintext tar contents. Full tar listing after decryption is a WSL/Admin verification responsibility because the private key is not installed on the Pi.

### 9.4 GPG validation

Pi-side `backup_verify` must not require the private key. It must validate encrypted artifacts at artifact level:

```bash
GNUPGHOME=/var/lib/homelab-backup/gnupg   gpg --batch --list-packets secrets/etc-raspberry-pi-homelab.tar.zst.gpg >/dev/null
```

Where recipient metadata is visible, verification must check that the encrypted packet is addressed to the configured backup recipient. This is still weaker than a real decrypt/list test and must be reported as Pi-side artifact verification, not full restore proof.

WSL/Admin performs full decrypt/list verification because it holds the private key:

```bash
gpg --decrypt secrets/etc-raspberry-pi-homelab.tar.zst.gpg   | zstd -d   | tar -tf - >/dev/null
```

The verifier must distinguish these two modes explicitly:

- `artifact-only`: safe to run on the Pi; validates checksums, OpenPGP packets, freshness, and status files.
- `decrypt`: requires WSL/Admin private key; proves encrypted artifacts can be decrypted and listed.

### 9.5 Status files

The verifier should write machine-readable status files:

```text
/srv/backups/homelab/status/latest.json
/srv/backups/homelab/status/latest-success.json
/srv/backups/homelab/status/latest-failure.json
```

At minimum, `latest.json` should include:

```json
{
  "checked_at_utc": "2026-05-22T20:45:00Z",
  "backup_id": "2026-05-22T203000Z",
  "backup_dir": "/srv/backups/homelab/2026-05-22T203000Z",
  "result": "ok",
  "warnings": [],
  "errors": []
}
```

---

## 10. Restore Procedure Details

### 10.1 Pre-restore checks

Before restore, verify:

- target backup passed `backup_verify`
- target repo checkout is at the intended commit
- Docker is installed and running
- no unexpected local Git changes exist
- backup timestamp and manifest match the intended recovery point
- destructive restore flags are present if applying changes
- target paths are not symlinks to unexpected locations

### 10.2 Dry-run behavior

Default restore mode is dry-run.

When `RESTORE_APPLY=0`, the restore script must:

- select the backup
- run verification
- list what would be restored
- list what would be skipped
- list any current target directories that would be moved aside
- not change files, services, ownerships, or permissions

### 10.3 Restore host-only secrets

Restore encrypted `/etc/raspberry-pi-homelab` material from WSL/Admin. The private key is not installed on the Pi, so the standard restore path decrypts on WSL/Admin and streams the plaintext tar over SSH to the Pi.

Required final state:

```text
/etc/raspberry-pi-homelab/monitoring.env root:root 600
```

Command shape from WSL/Admin:

```bash
BACKUP_DIR=/path/to/verified/backup
PI_HOST=admin@rpi-hub

gpg --decrypt "$BACKUP_DIR/secrets/etc-raspberry-pi-homelab.tar.zst.gpg"   | zstd -d   | ssh "$PI_HOST" 'sudo tar --extract --preserve-permissions --numeric-owner --file - --directory /'

ssh "$PI_HOST" 'sudo chown root:root /etc/raspberry-pi-homelab/*.env && sudo chmod 600 /etc/raspberry-pi-homelab/*.env'
```

A local staging restore on WSL/Admin is also allowed for inspection:

```bash
mkdir -p restore-staging
gpg --decrypt "$BACKUP_DIR/secrets/etc-raspberry-pi-homelab.tar.zst.gpg"   | zstd -d   | tar --extract --preserve-permissions --numeric-owner --file - --directory restore-staging
```

Temporary import of the private key on the Pi is an emergency-only exception and must be followed by deleting the secret key and the temporary GnuPG home.

### 10.4 Restore data

Stop the monitoring stack first:

```bash
cd ~/iac/raspberry-pi-homelab

sudo docker compose \
  --env-file /etc/raspberry-pi-homelab/monitoring.env \
  -f stacks/monitoring/compose/docker-compose.yml \
  down
```

Then restore selected data archives under `/srv/data/stacks/monitoring`.

Required behavior:

- create missing parent directories
- preserve numeric owners and groups
- replace target directory atomically where practical
- keep a pre-restore safety copy when restoring on a non-empty directory
- do not restore `alertmanager-config` as authoritative state

Recommended safety-copy layout:

```text
/srv/backups/homelab/pre-restore/<timestamp>/
```

Recommended restore shape per component:

```bash
sudo mkdir -p /srv/data/stacks/monitoring
sudo rm -rf /srv/data/stacks/monitoring/.restore-tmp-grafana
sudo mkdir -p /srv/data/stacks/monitoring/.restore-tmp-grafana
gpg --decrypt data/monitoring-grafana.tar.zst.gpg \
  | zstd -d \
  | sudo tar --extract --preserve-permissions --numeric-owner --file - \
      --directory /srv/data/stacks/monitoring/.restore-tmp-grafana

# Move current target aside, then move restored directory into place.
sudo mv /srv/data/stacks/monitoring/grafana \
  /srv/backups/homelab/pre-restore/<timestamp>/grafana
sudo mv /srv/data/stacks/monitoring/.restore-tmp-grafana/grafana \
  /srv/data/stacks/monitoring/grafana
```

### 10.5 Recreate generated config and permissions

Do not manually restore generated Alertmanager config as authoritative state. Let deploy recreate it from Git templates and env.

Run:

```bash
sudo ./deploy.sh
```

This deploy path validates the host-only env file, ensures Docker daemon config, ensures journald read access, bootstraps networks, optionally runs init permissions, applies Compose, and runs postdeploy tests by default.

### 10.6 Restore `/etc/machine-id`

Default policy:

```text
Do not restore /etc/machine-id blindly.
```

The backup keeps `machine-id.txt` for diagnostics. Restore it only for an explicit, documented reason.

### 10.7 Restore SSH host keys

SSH host keys are backed up because replacing them changes the host identity seen by SSH clients.

Default policy:

```text
Do not restore SSH host keys automatically.
```

Restore them only when stable SSH host identity is required and the target host is intended to assume the original identity.

---

## 11. Restore Validation

After every restore:

```bash
cd ~/iac/raspberry-pi-homelab

sudo ./deploy.sh
make postdeploy
make backup_verify
```

Additional manual checks:

| Component | Check |
|---|---|
| Grafana | UI loads, dashboards available, datasource health OK |
| Alertmanager | `/alertmanager` state present, silences restored if expected |
| VictoriaMetrics | `/api/v1/query` works; history present if restored |
| VictoriaLogs | query endpoint works; history present if restored |
| Vector | no permission errors; journald ingestion resumes |
| UFW | expected ports exposed and unexpected ports blocked |
| Docker networks | `monitoring` and `apps` exist |
| Secrets | `/etc/raspberry-pi-homelab/monitoring.env` is `root:root 600` |
| SSH | host key behavior is expected |

---

## 12. Monitoring and Alerting Requirements

The backup system must eventually export or support checks for:

- age of latest verified backup
- success/failure of last backup
- success/failure of last verification
- total size of `/srv/backups/homelab`
- threshold violation above 500 GB
- number of retained backups
- failed GPG encryption/decryption validation
- failed archive checksum validation

Initial implementation may write status files under:

```text
/srv/backups/homelab/status/
```

Example:

```text
/srv/backups/homelab/status/latest.json
```

---

## 13. What Not To Do

Do not:

- commit runtime `.env` files
- rely on `stacks/monitoring/compose/.env` for production restore
- restore `/var/lib/docker` as an application backup
- restore runtime sockets
- restore `/etc/machine-id` automatically
- restore SSH host keys automatically
- mix data archives from different backup timestamps unless explicitly documented
- restore TSDB/log archives across incompatible image major versions without a migration plan
- hand-edit Grafana or Alertmanager state after restore instead of fixing Git or restored data
- delete old backups before a new backup has passed verification
- leave plaintext secret archives on disk after GPG encryption or decryption

---

## 14. Required Tests for Future Scripts

Before accepting `backup`, `backup_verify`, and `restore`, add focused tests.

### 14.1 Static checks

- `bash -n scripts/backup/*.sh`
- ShellCheck for all backup scripts
- no CRLF
- no secrets committed

### 14.2 Unit-style tests with fixtures

Use temporary directories and environment overrides.

Required cases:

- backup creates expected directory layout
- manifest JSON validates
- checksums validate
- archive listing validates
- unsafe archive members are rejected
- missing required secret file fails pre-flight
- wrong `monitoring.env` mode fails pre-flight
- repo-root `.env` fails or warns according to policy
- GPG packet validation works on the Pi without a private key
- GPG full decrypt/list works on WSL/Admin when the private key is available
- dry-run restore changes nothing
- restore refuses without `RESTORE_APPLY=1`
- restore refuses without `RESTORE_CONFIRM=RESTORE_HOMELAB_DATA`
- restore safety copy is created for non-empty target directories
- retention does not delete the only verified backup

### 14.3 Integration tests on Pi

Required before enabling scheduled backups:

1. Create backup.
2. Verify backup.
3. Restore into temporary directory only.
4. Restore one non-critical component on the live Pi.
5. Run `sudo ./deploy.sh`.
6. Run `make postdeploy`.

---

## 15. Open Follow-up Items

Before implementing scheduled backups, resolve or encode these as explicit script defaults:

1. Remove or migrate `stacks/monitoring/compose/.env` if it contains unique values.
2. Decide whether VictoriaMetrics and VictoriaLogs can be skipped with flags such as:
   - `BACKUP_INCLUDE_METRICS=0`
   - `BACKUP_INCLUDE_LOGS=0`
3. Configure remote/offsite copy after local public-key encrypted backup/restore correctness is proven.
4. Add a restore test target that restores into a temporary directory before touching live paths.
5. Add Alertmanager integration for backup freshness and backup root size.

---

## 16. Design Decisions

### DD-001: Git first, backup second

Git is the source of truth for declarative configuration. Backups cover runtime data and host-local secrets only.

### DD-002: Bind mounts, not Docker named volumes

The monitoring stack uses deterministic host bind mounts under `/srv/data/stacks/monitoring`. Backup and restore operate on those paths.

### DD-003: Secrets are host-only and encrypted

Runtime secrets live under `/etc/raspberry-pi-homelab` and are backed up with OpenPGP public-key encryption using GnuPG.

### DD-004: Local backup bundles first

The first implementation creates local backup bundles under `/srv/backups/homelab`. Remote copy is deliberately deferred.

### DD-005: Retention is one week

Keep seven days of backups. Cleanup runs only after the newest backup verifies successfully.

### DD-006: 500 GB backup root threshold

Verification fails or alerts if `/srv/backups/homelab` exceeds 500 GB.

### DD-007: Metrics and logs are useful but not existential

VictoriaMetrics and VictoriaLogs are backed up and restored by default, but losing their history is acceptable if a constrained restore or space-pressure decision requires it.

### DD-008: Generated Alertmanager config is not authoritative

`/srv/data/stacks/monitoring/alertmanager-config` is generated by the renderer. Restore should verify recreation from Git templates and env rather than treating it as primary state.

### DD-009: Machine identity is not restored blindly

`/etc/machine-id` is exported for diagnostics but not restored automatically.

### DD-010: SSH host identity is backed up but restored manually

SSH host keys are backed up encrypted. Restore is manual because it changes host identity semantics.

### DD-011: Deploy reconciles the host after restore

Restore ends by running `sudo ./deploy.sh`, which applies the GitOps deployment path and postdeploy tests.

### DD-012: Future scripts must be test-first

`backup`, `backup_verify`, and `restore` scripts must include focused tests before being accepted into the repository.

### DD-013: Restore is dry-run by default

The restore script must not mutate the host unless `RESTORE_APPLY=1` and the confirmation token are provided.

### DD-014: Quiesced backup first

The first implementation stops the monitoring stack before archiving service data. Live backups may be added only after consistency has been proven.

### DD-015: Verification is a first-class artifact

A backup is not considered usable until `backup_verify` succeeds and writes a successful status file.

### DD-016: Public-key GPG is the backup encryption boundary

The Pi encrypts backup artifacts with the dedicated `Homelab Backup Recovery` public key. The private key is generated and stored only on WSL/Admin, with an additional KeePassXC/offline recovery copy. Pi-side verification is artifact-only. Full decrypt verification and restore tests run on WSL/Admin.

---

## 17. GPG Encryption Architecture Decision

### 17.1 Decision

Backups use OpenPGP public-key encryption with GnuPG. The backup recipient is a dedicated `Homelab Backup Recovery` key generated on WSL/Admin with no expiry date. The Raspberry Pi stores only the public key and pins the full 40-hex fingerprint. The Pi produces encrypted `.tar.zst.gpg` artifacts and runs artifact-only verification. WSL/Admin holds the private key in the local repository checkout under a Git-ignored path and runs decrypt verification and restore tests.

### 17.2 Rationale

This keeps the deploy target from becoming the recovery trust anchor. If the Pi is compromised, an attacker can create new encrypted backups but cannot decrypt existing backup artifacts using material stored on the Pi. Restore authority remains on WSL/Admin and in documented offline/KeePassXC recovery material.

### 17.3 Accepted trade-off: no key expiry

The backup key is intentionally created without an expiry date to reduce disaster-recovery failure modes caused by an expired recipient key. This increases the importance of revocation handling, protected private-key storage, and periodic manual review of the key fingerprint and recovery material.

### 17.4 Key material placement

| Location | Allowed material | Prohibited material |
|---|---|---|
| Git repository remote | Public key, pinned fingerprint, scripts, tests, docs, `.env.example` | Private key, passphrase, storage credentials, real `.env` files |
| Pi | Public keyring, pinned fingerprint, encrypted backup artifacts | Private key, private-key passphrase, KeePassXC database |
| WSL/Admin local checkout | Private key export under Git-ignored path, restore tooling, decrypt-test fixtures | Committed private key or committed secrets |
| KeePassXC | GPG passphrase, key metadata, backup storage credentials, private key attachment, restore notes, revocation certificate | Sole copy of all recovery material |
| Offline storage | Private-key export, revocation certificate, ownertrust export, KeePassXC backup, printed recovery note | Permanently mounted writable backup target |

### 17.5 Repository layout

Recommended Git-tracked files:

```text
config/backup/homelab-backup-recovery-public.asc
config/backup/homelab-backup-recovery-public.fingerprint
docs/architecture/adr/ADR-009-backup-verify-restore.md
docs/operations/BackupVerifyRestore.md
docs/operations/GPG_config_for_backup_encryption.md
```

Recommended local-only ignored files:

```text
secrets/backup/gpg/homelab-backup-recovery-secret.asc
secrets/backup/gpg/homelab-backup-recovery-ownertrust.txt
secrets/backup/gpg/homelab-backup-revocation.asc
```

`.gitignore` must include:

```gitignore
/secrets/
*.kdbx
*.keyx
*.env
```

### 17.6 Script implications

`backup` must import or verify the public key, pin the expected fingerprint, create compressed tar streams, encrypt to the pinned recipient, write checksums for encrypted artifacts, and avoid writing plaintext archives to disk.

`backup_verify` on the Pi must validate manifest, checksums, OpenPGP packet readability, expected encrypted artifacts, backup age, retention, and backup-root size. It must not claim full restore proof without private-key decryption.

`backup_verify --decrypt` or the equivalent WSL/Admin verification path must decrypt each encrypted artifact, decompress it, list the tar members, and reject unsafe archive members.

`restore` must normally run from WSL/Admin, decrypt artifacts locally, and stream restored tar data to the Pi over SSH. Temporary private-key import on the Pi is emergency-only and must be documented in the restore log.

---

## 18. References

- Docker bind mounts: https://docs.docker.com/engine/storage/bind-mounts/
- Docker Compose environment variable precedence: https://docs.docker.com/compose/how-tos/environment-variables/envvars-precedence/
- GNU tar option summary: https://www.gnu.org/software/tar/manual/html_node/Option-Summary.html
- GnuPG operational commands: https://www.gnupg.org/documentation/manuals/gnupg/Operational-GPG-Commands.html
- GnuPG key management: https://www.gnupg.org/documentation/manuals/gnupg/OpenPGP-Key-Management.html
- KeePassXC documentation: https://keepassxc.org/docs/
