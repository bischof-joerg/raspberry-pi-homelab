# Docker Daemon Configuration Management (`daemon.json`)

This homelab manages Docker Engine daemon settings via GitOps to ensure **deterministic, idempotent** host configuration on the Raspberry Pi.

The primary purpose is to enforce baseline Docker behavior that applies to **all containers**, with particular emphasis on **default logging behavior** (log driver and log rotation) to prevent unbounded disk growth.

---

## Scope and Principles

- **GitOps source of truth:** Docker daemon settings are version-controlled in this repository.
- **Idempotent apply:** Re-running deployment must not change a healthy system and must not cause unnecessary Docker restarts.
- **Fail-fast safety:** The configuration is validated before being applied; invalid JSON must never be installed.

---

## Files and Locations

### Repository (source of truth)

- `stacks/core/docker/daemon.json`

### Target host (Docker Engine)

- `/etc/docker/daemon.json`

### Apply mechanism

- `scripts/host/ensure-docker-daemon-json.sh`

The script syncs the repo-managed `daemon.json` to the host path and restarts Docker **only if** the effective file content changed.

---

## Operational Flow

### 1) `git pull` brings desired state to the Pi

The Raspberry Pi is a **deployment target only**. Updates are pulled from Git as the single source of truth.

### 2) `deploy.sh` orchestrates host bootstrap + stack deployment

During `sudo ./deploy.sh`, host configuration steps run in a predictable order. The Docker daemon configuration step is executed early to ensure Docker is configured correctly before stacks are started.

### 3) `ensure-docker-daemon-json.sh apply` enforces desired state

On each deploy:

1. Validate the repo file is present:
   - `stacks/core/docker/daemon.json`
2. Validate JSON (fail-fast):
   - Uses `jq` if available, otherwise `python3 -m json.tool`
3. Compare source vs target:
   - If identical: **no action**
   - If different: install updated file to `/etc/docker/daemon.json`
4. Restart Docker only on drift:
   - `systemctl restart docker`
   - Verify `docker` service is active

This guarantees the process is **idempotent** and avoids restart churn.

---

## Why Manage `daemon.json` via GitOps?

Docker daemon defaults affect all containers and stacks running on the host. Enforcing them centrally ensures:

- Consistent behavior across all services
- Predictable operational characteristics (especially logs)
- Reduced risk of host instability due to misconfiguration or drift

---

## Default Logging Behavior (Global)

The daemon-level `log-driver` and `log-opts` define the **default logging behavior for all containers** on the host.

Typical goals:

- Ensure logs use a known driver (e.g., `json-file`)
- Enforce rotation (e.g., size and file count limits)
- Prevent uncontrolled growth of container logs on disk

### Note: Per-service overrides are allowed

A service can override the global daemon defaults in `docker-compose.yml` by specifying a `logging:` section.

Example:

```yaml
services:
  grafana:
    image: grafana/grafana:11.0.0
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "5"
```

**Effect:**

- If `logging:` is not defined for a service, it inherits the daemon defaults from `/etc/docker/daemon.json`.
- If `logging:` is defined, Docker uses the service-level settings for that container, overriding daemon defaults for that service only.

This provides a safe baseline for all services while allowing exceptions where required (e.g., higher log volume workloads).

---

## Usage

### Apply desired state (idempotent)

```bash
sudo scripts/host/ensure-docker-daemon-json.sh apply
```

### Detect drift without applying

```bash
scripts/host/ensure-docker-daemon-json.sh check
```

### Deploy full stack (includes daemon sync)

```bash
sudo ./deploy.sh
```

---

## Validation and Troubleshooting

### Validate Docker is running after apply

```bash
sudo systemctl is-active docker
```

### Inspect Docker daemon logs on failure

```bash
sudo journalctl -u docker -b --no-pager | tail -200
```

### Common failure mode: invalid JSON

If the repo-managed `daemon.json` is malformed, the script fails before applying changes, preventing Docker restarts with broken configuration.

---

## Change Management

- Update desired Docker daemon settings by editing:
  - `stacks/core/docker/daemon.json`
- Commit and push changes via the normal Git workflow.
- On the Pi, `git pull` + `sudo ./deploy.sh` applies the new state.
- Rollback is done via `git revert` (GitOps rollback), then redeploy.
