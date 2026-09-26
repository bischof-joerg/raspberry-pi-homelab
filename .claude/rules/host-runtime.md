---
paths:
  - "scripts/host/**"
  - "scripts/host-runtime/**"
  - "scripts/network/**"
  - "stacks/core/docker/**"
  - "deploy.sh"
---

# Host and runtime reconciliation

The Pi's desired state is only **partly** reconciled on each deploy. Knowing which part is the
difference between a fix that holds and one that is silently undone.

## What `deploy.sh` actually reconciles on every deploy

| Script | Mode | Effect |
|---|---|---|
| `scripts/host/ensure-docker-daemon-json.sh` | `apply` | copies `stacks/core/docker/daemon.json` to `/etc/docker/daemon.json` and **restarts Docker on any change**, restarting every container (F18) |
| `scripts/host/ensure-journald-read.sh` | `apply`, `TARGET_USER=admin` | adds the user to `systemd-journal`, `chgrp -R`/`chmod g+rx` on journal dirs, returns the GID |
| `scripts/network/bootstrap-networks.sh` | create-if-missing | ensures `monitoring` and `apps` exist. Subnet/gateway/bridge are only validated or set **if** `MONITORING_SUBNET`/`…_BRIDGE_NAME` are in the environment — and `deploy.sh` does not export them (F16) |
| `stacks/monitoring/compose/init-permissions.sh` | auto | data directory ownership and modes |

## What it does **not** reconcile

- **UFW.** `scripts/network/cleanup-ufw.sh` is manual, dry-run by default, has no make target.
  `tests/postdeploy/test_35_network_and_ufw.py` *detects* drift but nothing repairs it (F15).
- **APT and EEPROM.** `scripts/host-runtime/*` runs only through the Pi-only targets
  `host-audit`, `host-upgrade-plan`, `host-upgrade-apply`, `host-eeprom-apply`. Deliberately
  separate from deploy — plan and apply stay split, EEPROM is always explicit, and there is no
  automatic reboot (`docs/operations/runtime-updates.md`).

## MUST

- **Treat ordering as part of the design.** `daemon.json` sets `metrics-addr` to the monitoring
  gateway IP and is applied *before* the networks are bootstrapped, so on a fresh host that address
  may not exist yet (F17). Do not add a new dependency on state that a later step creates.
- **Keep the three coupled values consistent** wherever they appear: subnet `172.20.0.0/16`,
  bridge `br-monitoring`, and the Docker metrics address `172.20.0.1:9323`. They are referenced by
  `daemon.json`, `cleanup-ufw.sh` and `tests/postdeploy/test_35_network_and_ufw.py`. Changing one
  without the others breaks the host quietly.
- **Extend the postdeploy checks in the same increment** as any change to ports, UFW rules,
  networks or host configuration.
- **Never run these scripts from here** (C5). They mutate `/etc/docker`, UFW, groups, Docker
  networks, APT and EEPROM. Read and edit them; the operator executes them on the Pi.

## SHOULD

- Prefer making a manual reconciliation automatic over documenting the manual step — but that is an
  ADR-level decision (scheduled for roadmap stage R1), not a drive-by change.
- Consider the restart blast radius: a `daemon.json` change restarts every container, so it needs a
  maintenance window and a backup beforehand.

## Sources

`deploy.sh`, `scripts/host/`, `scripts/host-runtime/`, `scripts/network/`,
`stacks/core/docker/daemon.json`, `tests/postdeploy/test_35_network_and_ufw.py`,
`docs/operations/runtime-updates.md`, `docs/architecture/adr/ADR-0001-networking-and-firewall.md`.
Findings F15–F19 in `.claude/reports/repo-findings.md`.
