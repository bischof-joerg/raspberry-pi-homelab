# Backup & Restore Runbook

This runbook defines the backup and restore operating model for the Raspberry Pi GitOps homelab. It is the source document for the future `backup`, `backup_verify`, and `restore` scripts.

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

## 2. Standard Procedure

### 2.1 Create a backup

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
  secrets/
  host/
  logs/
```

Secrets must be encrypted with GPG. Runtime data archives may remain unencrypted initially unless secrets are embedded in the data path; the script must still compute checksums for every produced artifact.

### 2.2 Verify a backup

Run after every backup:

```bash
make backup_verify
```

Verification must prove at minimum:

- the manifest exists and is valid JSON
- every file listed in `checksums.sha256` exists
- every checksum matches
- every archive can be listed
- encrypted secret archives can be decrypted or at least GPG packet-validated, depending on non-interactive constraints
- the backup root has not exceeded the configured size threshold
- the latest backup is recent enough for the configured policy

The backup size alert threshold is:

```text
500 GB
```

### 2.3 Restore on the same host

Use this path when the OS and repository are still intact, but service data or secrets must be restored.

1. Confirm the target backup:

   ```bash
   ls -lh /srv/backups/homelab
   ```

2. Stop the affected stack:

   ```bash
   cd ~/iac/raspberry-pi-homelab
   sudo docker compose \
     --env-file /etc/raspberry-pi-homelab/monitoring.env \
     -f stacks/monitoring/compose/docker-compose.yml \
     down
   ```

3. Restore secrets first, if needed.

4. Restore persistent bind-mounted data.

5. Run the normal deploy reconciliation:

   ```bash
   sudo ./deploy.sh
   ```

6. Validate:

   ```bash
   make postdeploy
   make backup_verify
   ```

### 2.4 Restore after fresh OS install

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

4. Restore `/etc/rspberry-pi-homelab` host-only secrets, with the corrected target path:

   ```text
   /etc/raspberry-pi-homelab
   ```

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

## 3. Current Backup-Relevant Reality

### 3.1 Runtime env files

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
| `stacks/monitoring/compose/.env.example` | Git-tracked example only; not backed up as secret |
| `stacks/monitoring/compose/.env` | Non-authoritative local artifact; do not rely on it for deploy; migrate unique values into `/etc/raspberry-pi-homelab/monitoring.env` and delete if possible |

`deploy.sh` refuses a repository-root `.env` file and validates that the active `SECRETS_FILE` exists, is readable, is owned by `root:root`, and has mode `600`.

### 3.2 Persistent service data

The current monitoring stack uses deterministic bind mounts under:

```text
/srv/data/stacks/monitoring
```

These are the currently observed data directories:

| Path | Owner/mode observed | Backup policy |
|---|---:|---|
| `/srv/data/stacks/monitoring/alertmanager` | `750 nobody:nogroup` | Back up and restore |
| `/srv/data/stacks/monitoring/alertmanager-config` | `755 root:root` | Do not treat as authoritative; recreate from Git + env; may include in host diagnostics only |
| `/srv/data/stacks/monitoring/grafana` | `750 472:472` | Back up and restore |
| `/srv/data/stacks/monitoring/vector` | `750 65532:65532` | Back up and restore |
| `/srv/data/stacks/monitoring/victorialogs` | `750 root:root` | Back up by default; restore by default; acceptable to lose history if explicitly selected |
| `/srv/data/stacks/monitoring/victoriametrics` | `750 root:root` | Back up by default; restore by default; acceptable to lose history if explicitly selected |

Subdirectories inherit the same backup policy as their parent directory unless explicitly excluded.

### 3.3 Rendered bind mounts

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

## 4. Artifact Inventory

### 4.1 Authoritative Git state

| Artifact | Backup? | Restore source |
|---|---:|---|
| Repository files | No separate Pi backup required | GitHub / Git remote |
| Compose files | No separate Pi backup required | Git |
| Grafana provisioning | No separate Pi backup required | Git |
| Grafana dashboards | No separate Pi backup required | Git |
| vmagent config | No separate Pi backup required | Git |
| vmalert config and rules | No separate Pi backup required | Git |
| Vector config | No separate Pi backup required | Git |
| Alertmanager templates and template source config | No separate Pi backup required | Git |

### 4.2 Host-only secrets

| Artifact | Backup? | Encryption | Restore mode |
|---|---:|---:|---|
| `/etc/raspberry-pi-homelab/monitoring.env` | Yes | GPG | `root:root 600` |
| `/etc/raspberry-pi-homelab/*.env` | Yes | GPG | `root:root 600` |
| `/etc/raspberry-pi-homelab/*.bak-*` | Yes, until cleaned up | GPG | Restore only if needed |
| GHCR credentials inside env file | Yes, as part of env file | GPG | `root:root 600` |
| SMTP secrets inside env file | Yes, as part of env file | GPG | `root:root 600` |
| Grafana admin credentials inside env file | Yes, as part of env file | GPG | `root:root 600` |

### 4.3 Persistent data

| Artifact | Backup? | Restore? | Notes |
|---|---:|---:|---|
| `/srv/data/stacks/monitoring/grafana` | Yes | Yes | Required for Grafana DB, plugins, state |
| `/srv/data/stacks/monitoring/alertmanager` | Yes | Yes | Required for silences and Alertmanager state |
| `/srv/data/stacks/monitoring/vector` | Yes | Yes | Preserves ingestion offsets/checkpoints |
| `/srv/data/stacks/monitoring/victoriametrics` | Yes by default | Yes by default | Metrics history is useful but not mandatory |
| `/srv/data/stacks/monitoring/victorialogs` | Yes by default | Yes by default | Logs are useful but not mandatory; capped separately by VictoriaLogs |
| `/srv/data/stacks/monitoring/alertmanager-config` | Diagnostic only | No by default | Generated from Git templates and env |

### 4.4 Host configuration exports

| Artifact | Backup? | Restore? | Notes |
|---|---:|---:|---|
| `ufw status numbered` output | Yes | Manually reconcile | Human-readable restore evidence |
| `/etc/ufw` | Yes | Carefully, same OS only | Useful for full host recovery |
| `/etc/docker/daemon.json` | Yes | Usually recreated by deploy | Also enforced by GitOps script |
| Docker networks listing | Yes | Recreated by deploy/bootstrap | Export for diagnostics |
| Docker version / Compose version | Yes | No | Manifest/debugging only |
| Package list | Yes | No | Debugging and rebuild evidence |
| `/etc/machine-id` value | Export only | Do not restore blindly | Restoring can duplicate host identity |
| `/etc/ssh/ssh_host_*` | Yes | Optional/manual | Restore only if stable SSH host identity is desired |

### 4.5 Explicit exclusions

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

## 5. Backup Strategy

### 5.1 Frequency

| Trigger | Required action |
|---|---|
| Daily | Run `make backup && make backup_verify` |
| Before host runtime upgrade | Run `make backup && make backup_verify` |
| Before major OS upgrade | Run `make backup && make backup_verify`; copy backup off-device manually until remote sync exists |
| After secrets change | Run `make backup && make backup_verify` |
| After service topology change | Update this runbook first, then run backup and verification |
| Before destructive restore test | Run backup and verification |

### 5.2 Retention

Default retention:

```text
7 days
```

The backup implementation must not delete the only verified backup. Retention cleanup must run only after a new backup has passed verification.

### 5.3 Size alert

The backup verification script must alert or fail when:

```text
du -sb /srv/backups/homelab > 500 GB
```

The first implementation may fail the verification target. Later this can be integrated into Alertmanager.

### 5.4 Local-only phase

The first implementation creates local backup bundles only.

Out of scope for the first script version:

- NAS copy
- S3/object storage copy
- off-site replication
- snapshot integration
- automated remote retention

These can be added after local backup/restore correctness is proven.

---

## 6. Backup Bundle Format

Each backup must be self-describing.

Example layout:

```text
/srv/backups/homelab/2026-05-22T203000Z/
  manifest.json
  checksums.sha256
  data/
    monitoring-alertmanager.tar.gz
    monitoring-grafana.tar.gz
    monitoring-vector.tar.gz
    monitoring-victoriametrics.tar.gz
    monitoring-victorialogs.tar.gz
  generated/
    monitoring-alertmanager-config.tar.gz
  secrets/
    etc-raspberry-pi-homelab.tar.gz.gpg
  host/
    docker-daemon.json
    ufw-status-numbered.txt
    ufw-status-verbose.txt
    etc-ufw.tar.gz
    machine-id.txt
    ssh-host-keys.tar.gz.gpg
    docker-info.txt
    docker-version.txt
    docker-compose-version.txt
    docker-networks.txt
    package-list.txt
    os-release.txt
    uname.txt
  logs/
    backup.log
```

### 6.1 Manifest requirements

`manifest.json` must include at least:

```json
{
  "schema_version": 1,
  "created_at_utc": "2026-05-22T20:30:00Z",
  "hostname": "rpi-hub",
  "repo_root": "/home/admin/iac/raspberry-pi-homelab",
  "git_commit": "unknown",
  "backup_root": "/srv/backups/homelab",
  "compose_file": "stacks/monitoring/compose/docker-compose.yml",
  "secrets_file": "/etc/raspberry-pi-homelab/monitoring.env",
  "included_paths": [],
  "excluded_paths": [],
  "notes": []
}
```

The scripts may extend this schema, but must not remove existing fields without updating this runbook.

---

## 7. Backup Procedure Details

### 7.1 Pre-flight checks

The backup script must check:

- running on the Raspberry Pi target, not the WSL dev machine
- `docker` and `docker compose` are available
- repository exists
- `git rev-parse HEAD` succeeds
- `/etc/raspberry-pi-homelab/monitoring.env` exists with `root:root 600`
- `/srv/data/stacks/monitoring` exists
- `/srv/backups/homelab` exists or can be created
- enough free space is available for a local backup
- `gpg` is installed

### 7.2 Stack quiescing policy

Default first implementation:

- Stop the monitoring stack before archiving persistent data.
- Archive data.
- Start the stack again with `sudo ./deploy.sh`. Implicitely runs postdeploy tests.

Reason: this is slower but simpler and safer than live-copying TSDB and SQLite-like service state.

Future improvement:

- Add service-specific online snapshot support where available.
- Allow `BACKUP_QUIESCE=0` only after backup consistency has been proven.

### 7.3 Data archives

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

- owner
- group
- mode
- symlinks
- timestamps

### 7.4 Secrets archive

Encrypt the entire host-only env directory:

```text
/etc/raspberry-pi-homelab
```

Use GPG symmetric encryption for the first implementation.

Required properties:

- output must be `.gpg`
- plaintext tar must not remain on disk after encryption
- passphrase must not be committed
- passphrase must not be echoed in logs
- restore procedure must verify target file mode after decryption

### 7.5 Host configuration exports

Export at least:

```bash
cat /etc/os-release
uname -a
docker version
docker compose version
docker network ls
docker compose --env-file /etc/raspberry-pi-homelab/monitoring.env \
  -f stacks/monitoring/compose/docker-compose.yml config
sudo ufw status numbered
sudo ufw status verbose
sudo tar -czf etc-ufw.tar.gz /etc/ufw
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

## 8. Restore Procedure Details

### 8.1 Pre-restore checks

Before restore, verify:

- target backup passed `backup_verify`
- target repo checkout is at the intended commit
- Docker is installed and running
- no unexpected local Git changes exist
- backup timestamp and manifest match the intended recovery point

### 8.2 Restore host-only secrets

Restore encrypted `/etc/raspberry-pi-homelab` material.

Required final state:

```text
/etc/raspberry-pi-homelab/monitoring.env root:root 600
```

Command shape:

```bash
sudo install -d -m 700 -o root -g root /etc/raspberry-pi-homelab
sudo gpg --decrypt secrets/etc-raspberry-pi-homelab.tar.gz.gpg \
  | sudo tar -xzpf - -C /
sudo chown root:root /etc/raspberry-pi-homelab/*.env
sudo chmod 600 /etc/raspberry-pi-homelab/*.env
```

### 8.3 Restore data

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

### 8.4 Recreate generated config and permissions

Do not manually restore generated Alertmanager config as authoritative state. Let deploy recreate it from Git templates and env.

Run:

```bash
sudo ./deploy.sh
```

This deploy path validates the host-only env file, ensures Docker daemon config, ensures journald read access, bootstraps networks, optionally runs init permissions, applies Compose, and runs postdeploy tests by default.

### 8.5 Restore `/etc/machine-id`

Default policy:

```text
Do not restore /etc/machine-id blindly.
```

The backup keeps `machine-id.txt` for diagnostics. Restore it only for an explicit, documented reason.

### 8.6 Restore SSH host keys

SSH host keys are backed up because replacing them changes the host identity seen by SSH clients.

Default policy:

```text
Do not restore SSH host keys automatically.
```

Restore them only when stable SSH host identity is required and the target host is intended to assume the original identity.

---

## 9. Restore Validation

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

## 10. Monitoring and Alerting Requirements

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

## 11. What Not To Do

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

---

## 12. Open Follow-up Items

Before implementing `backup`, `backup_verify`, and `restore`, resolve or encode these as explicit script defaults:

1. Remove or migrate `stacks/monitoring/compose/.env` if it contains unique values.
2. Decide whether VictoriaMetrics and VictoriaLogs can be skipped with flags such as:
   - `BACKUP_INCLUDE_METRICS=0`
   - `BACKUP_INCLUDE_LOGS=0`
3. Decide how the GPG passphrase is provided non-interactively, if scheduled backups are required.
4. Decide whether `make backup` should stop the monitoring stack by default or require `BACKUP_QUIESCE=1`.
5. Add a restore test target that restores into a temporary directory before touching live paths.

---

## 13. Design Decisions

### DD-001: Git first, backup second

Git is the source of truth for declarative configuration. Backups cover runtime data and host-local secrets only.

### DD-002: Bind mounts, not Docker named volumes

The monitoring stack uses deterministic host bind mounts under `/srv/data/stacks/monitoring`. Backup and restore operate on those paths.

### DD-003: Secrets are host-only and encrypted

Runtime secrets live under `/etc/raspberry-pi-homelab` and are backed up encrypted with GPG.

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
