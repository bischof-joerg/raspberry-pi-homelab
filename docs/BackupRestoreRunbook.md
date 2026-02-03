# Backup & Restore Runbook

This runbook defines **what is backed up, how backups are created, how restores are performed, and how restores are validated** for the Raspberry Pi GitOps homelab. It is designed for **repeatable, low-risk recovery** aligned with the existing Infrastructure-as-Code and GitOps model.

---

## 1. Scope and Design Principles

### In Scope

* Persistent data volumes of the monitoring stack
* Host-level configuration required to restore services
* Git repository as the single source of truth for configuration

### Explicitly Out of Scope

* OS reinstallation procedures (covered separately)
* Disaster recovery across different hardware
* Point-in-time restore of Prometheus metrics beyond filesystem snapshots

### Design Principles

* Backups are **host-based**, not container-internal
* Backups are **read-only snapshots** of Docker volumes
* Restore is **Git-driven first, data second**
* Recovery must be **idempotent and testable**

---

## 2. What Must Be Backed Up

### 2.1 Git Repository (Authoritative Configuration)

| Component      | Location          |
| -------------- | ----------------- |
| GitOps sources | GitHub repository |

Notes:

* Git is the primary recovery mechanism
* No backups on the Pi are required beyond normal Git hosting

---

### 2.2 Persistent Docker Volumes (Critical)

** NEEDS LOVE**

| Service      | Data                  | Typical Path                                   |
| ------------ | --------------------- | ---------------------------------------------- |
| Grafana      | DB, users, dashboards | `/var/lib/docker/volumes/*grafana*/_data`      |
| Alertmanager | Silences, state       | `/var/lib/docker/volumes/*alertmanager*/_data` |

These volumes **must** be backed up together to ensure consistency.

---

### 2.3 Secrets and Host Configuration

The project uses **multiple environment files** with a clear separation between **Git-tracked examples** and **host-only secrets**.

#### Secret Files (Runtime, NOT in Git)

| Purpose                | Runtime Location                             | Source Example                                       |
| ---------------------- | -------------------------------------------- | ---------------------------------------------------- |
| Docker Compose globals | `./monitoring/compose/.env`                  | `./monitoring/compose/.env.example`                  |
| Alertmanager secrets   | `./monitoring/alertmanager/alertmanager.env` | `./monitoring/alertmanager/alertmanager.env.example` |

Rules:

* Runtime `.env` files **must not** be committed to Git
* Only `*.env.example` files are tracked
* Runtime env files are backed up **encrypted**

#### Additional Host Configuration

| Item                 | Path                             |
| -------------------- | -------------------------------- |
| UFW rules            | `ufw status numbered` (exported) |
| Docker daemon config | `/etc/docker/daemon.json`        |

----|------|
| Secrets | `./monitoring/compose/.env and ./monitoring/alertmanager/alertmanager.env` |
| UFW rules | `ufw status numbered` (exported) |
| Docker daemon config | `/etc/docker/daemon.json` |

Notes:

* Secrets are backed up **encrypted**
* No secrets are ever committed to Git

---

## 3. Backup Strategy

### 3.1 Backup Frequency

| Data                | Frequency |
| ------------------- | --------- |
| Docker volumes      | Daily     |
| Secrets             | On change |
| UFW / Docker config | On change |

---

### 3.2 Backup Method (Recommended)

* Filesystem-level backup using `tar` or snapshot-based tooling
* Backups executed on the host
* Containers remain running (acceptable for Prometheus/Loki)

---

### 3.3 Example: Volume Backup Script

```bash
#!/usr/bin/env bash
set -euo pipefail

BACKUP_ROOT=/srv/backups/monitoring
DATE=$(date +%F)
DEST="$BACKUP_ROOT/$DATE"

mkdir -p "$DEST"

for v in grafana alertmanager; do
  docker run --rm \
    -v ${v}:/volume:ro \
    -v "$DEST":/backup \
    alpine \
    tar czf "/backup/${v}.tar.gz" -C /volume .
done
```

Properties:

* Read-only mounts
* No container privileges
* Deterministic output

---

### 3.4 Secrets Backup

All runtime secret files are backed up **explicitly and individually**.

```bash
sudo gpg --symmetric \
  --cipher-algo AES256 \
  monitoring/compose/.env

sudo gpg --symmetric \
  --cipher-algo AES256 \
  monitoring/alertmanager/alertmanager.env
```

Result:

* `./monitoring/compose/.env.gpg`
* `./monitoring/alertmanager/alertmanager.env.gpg`

Notes:

* Keys are stored outside the Raspberry Pi
* Decryption happens only during restore

---

## 4. Restore Scenarios

### 4.1 Scenario A: Service Failure (Same Host)

Symptoms:

* Containers start but data is missing or corrupted

Steps:

1. Stop stack:

   ```bash
   docker compose -f monitoring/compose/docker-compose.yml down
   ```

2. Restore affected volume(s)
3. Start stack:

   ```bash
   sudo ./deploy.sh
   ```

   which implicitly runs postdeploy tests

---

### 4.2 Scenario B: Full Monitoring Stack Loss (Same OS)

Steps:

1. Verify Git checkout:

    ```bash
    cd ~/iac/raspberry-pi-homelab
    git status
    git pull
    ```

2. Restore runtime secret env files:

    ```bash
    sudo gpg --decrypt monitoring/compose/.env.gpg \
      > monitoring/compose/.env
    sudo chmod 600 monitoring/compose/.env

    sudo gpg --decrypt monitoring/alertmanager/alertmanager.env.gpg \
      > monitoring/alertmanager/alertmanager.env
    sudo chmod 600 monitoring/alertmanager/alertmanager.env
    ```

3. Restore volumes:

**NEEDS LOVE**

    ```bash

    ```

4. Deploy:

   ```bash
   sudo ./deploy.sh
   ```

implicitly validates with postdeploy tests

---

### 4.3 Scenario C: New Raspberry Pi / Fresh OS

Order matters.

1. Install OS, Docker, Git
2. Clone repository
3. Restore runtime secret env files (`./monitoring/compose/.env`, `./monitoring/alertmanager/alertmanager.env`)
4. Restore Docker volumes
5. Deploy stack
6. Validate with postdeploy tests

Never restore volumes **before** the Git checkout.

---

## 5. Validation After Restore

### Mandatory Checks

```bash
make postdeploy
```

Additionally:

* Grafana dashboards load without "Discard changes"
* Prometheus shows historical data (if expected)
* Loki returns historical logs (if expected)
* Alertmanager silences exist (if expected)

---

## 6. What NOT to Do

* Do not restore individual files inside volumes
* Do not edit Grafana UI to "fix" issues after restore
* Do not mix volumes from different backup dates
* Do not restore volumes created by different image major versions without a migration plan
* Do not commit runtime .env files to Git

---

## 7. Maintenance and Testing

* Perform a full restore test quarterly
* Verify backups are readable (tar tzf ...)
* Document restore duration and issues

---

## 8. Summary

| Aspect             | Rule                             |
| ------------------ | -------------------------------- |
| Source of truth    | Git                              |
| Secret env files   | manual encryption and decription |
| Backup granularity | Docker volumes                   |
| Restore order      | Git → Secrets → Volumes → Deploy |
| Validation         | Automated tests                  |

This runbook ensures that recovery remains **boring, deterministic, and safe**.
