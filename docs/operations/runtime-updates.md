# Runtime Updates

Last verified: 2026-05-21
Applies to: Raspberry Pi 5, Raspberry Pi OS Lite 64-bit, Docker Compose, GitOps deployment model

This document defines how host runtime updates are planned, applied, and verified for this Raspberry Pi homelab repository.

The Raspberry Pi is a deployment target only. Do not develop, edit, or experiment on the Pi. The repository remains the source of truth; the Pi only pulls validated commits and executes deployment or maintenance targets.

---

## 1. Procedure

Use this procedure for routine host runtime maintenance beyond repository dependency updates handled by Renovate.

### 1.1 Standard maintenance flow

Run the flow on the Raspberry Pi unless a step explicitly says otherwise.

```bash
cd ~/raspberry-pi-homelab
git pull --ff-only
git status --short
```

The working tree must be clean before applying host changes. A non-empty `git status --short` indicates drift and must be resolved before continuing.

Audit the current runtime state:

```bash
make host-audit
```

Run the repository backup procedure before applying updates. If the repository backup targets are available, use:

```bash
make backup
make backup-verify
```

Plan the host update without applying package upgrades:

```bash
make host-upgrade-plan
```

Review the output before continuing. At minimum, check:

- upgradable APT packages
- Docker Engine and Compose package status
- EEPROM status
- failed systemd units
- available disk space
- whether a reboot is already pending

Apply routine host runtime updates:

```bash
make host-upgrade-apply
```

If the script reports that a reboot is required, reboot explicitly:

```bash
sudo reboot
```

After the reboot, verify the deployed system:

```bash
cd ~/raspberry-pi-homelab
make postdeploy
```

The update is complete only when post-deploy checks pass.

### 1.2 EEPROM maintenance flow

EEPROM updates are handled separately from routine APT upgrades.

Check EEPROM state as part of the normal audit or plan:

```bash
make host-audit
make host-upgrade-plan
```

Apply an EEPROM update only as an explicit maintenance action:

```bash
make host-eeprom-apply
sudo reboot
cd ~/raspberry-pi-homelab
make postdeploy
```

Do not bundle EEPROM updates into unattended or implicit runtime update flows.

### 1.3 Renovate flow remains separate

Repository dependency updates are handled through the Renovate workflow and local validation flow:

```bash
make renovate-apply
make precommit
make ci
git push
```

After the Pi pulls a Renovate-backed change, deploy and verify it through the normal GitOps deployment and post-deploy checks.

Do not use `make renovate-apply` as a substitute for host runtime maintenance. It changes repository-declared dependency references; it does not patch the running Raspberry Pi host.

### 1.4 Acceptance criteria

A runtime maintenance change is accepted only when all of the following are true:

- The Pi working tree is clean before applying mutating targets.
- Backup and backup verification have completed according to the repository backup procedure.
- `make host-upgrade-plan` output has been reviewed.
- `make host-upgrade-apply` or `make host-eeprom-apply` exits successfully.
- Any required reboot has been completed.
- `make postdeploy` passes.
- No unexpected failed systemd units remain.
- Exposed services are reachable only through the intended routes and ports.

---

## 2. Background: update domains

Runtime maintenance covers host-level software and firmware that are not fully represented by Compose files, Docker image references, or other repository dependency files.

| Area | Renovate / `make renovate-apply` | Host runtime targets | Raspberry Pi OS major upgrade | Notes |
|---|---:|---:|---:|---|
| Compose image tags and digests | Yes | No | No | Renovate can extract Docker images from Docker Compose YAML files and propose tag or digest updates. |
| Dockerfile base images | Yes, if configured | No | No | Renovate can update Docker image references and can maintain digest pinning. |
| GitHub Actions workflow dependencies | Yes, if configured | No | No | Renovate's GitHub Actions manager extracts workflow dependencies. |
| Python/dev dependencies in the repo | Yes, if configured | No | No | These are development and CI dependencies, not Pi host runtime state. |
| Raspberry Pi OS packages | No | Yes | Reinstalled/rebased | Routine maintenance uses APT on the current major OS version. |
| Linux kernel and stable firmware | No | Yes | Reinstalled/rebased | Raspberry Pi documents that the usual Raspberry Pi OS update process updates the kernel to the latest stable release. |
| Experimental or pre-release firmware via `rpi-update` | No | No | No | `rpi-update` is not part of routine maintenance. It is reserved for testing, development, or specific Raspberry Pi engineer guidance. |
| Raspberry Pi EEPROM / bootloader | No | Explicit only | May need explicit check after rebuild | Managed with `rpi-eeprom-update`; apply through `make host-eeprom-apply`, not as an implicit package update side effect. |
| Docker Engine, Docker CLI, containerd, Buildx, Compose plugin | No | Yes, if installed via APT packages | Installed by bootstrap | Docker packages are maintained by the host package manager. Compose v2 is verified with `docker compose version`. |
| Docker networks | No | Audited indirectly | Recreated by bootstrap/deploy | Networks are declared and bootstrapped by deployment logic, not by Renovate. |
| UFW/firewall behavior | No | Audited | Reconfigured by bootstrap | Docker can interact with firewall behavior; runtime checks must verify effective exposure. |
| `.env` files and secrets on the Pi | No | Presence/permissions only, if checked | Restored manually or from secret backup | Secrets are never committed to Git. |
| Persistent service data | No | No direct mutation | Restored from backup | Data updates are service-specific. Runtime maintenance requires backup and restore readiness. |
| Major Raspberry Pi OS version, for example Bookworm to Trixie | No | No | Yes | Treat as a rebuild from a clean OS image, not as a routine host update. |

---

## 3. Boundary to Renovate

Renovate is repository dependency automation. In this repository, it is expected to update dependency references that are present in files under version control, such as Compose image references, Dockerfile base images, workflow actions, and other supported package files.

Renovate does not mutate the running Raspberry Pi host. It does not run `apt full-upgrade`, update installed Debian packages, update EEPROM, restart Docker, modify UFW, repair host permissions, or validate the live network boundary.

The correct separation is:

```text
Renovate job:
  repository dependency change -> validation -> commit/PR -> deploy -> postdeploy

Host runtime maintenance:
  audit -> backup -> plan -> apply host packages/EEPROM explicitly -> reboot if required -> postdeploy
```

Renovate may update container images and digest pins, but a successful Renovate change is not proof that the Pi host runtime is current. Conversely, a successful host runtime update is not proof that application images, GitHub Actions, or development dependencies are current.

---

## 4. Boundary to Raspberry Pi OS updates and upgrades

### 4.1 Routine Raspberry Pi OS update

Routine Raspberry Pi OS updates stay within the currently installed major OS version. Raspberry Pi recommends APT for this update path. This updates installed software packages and also includes the stable Linux kernel and firmware packages provided by Raspberry Pi OS.

In this repository, that path is represented by:

```bash
make host-upgrade-plan
make host-upgrade-apply
sudo reboot # only when required
make postdeploy
```

This is appropriate for normal security fixes, bug fixes, stable kernel updates, stable firmware updates, Docker package updates, and package cleanup.

### 4.2 Major Raspberry Pi OS upgrade

A major Raspberry Pi OS upgrade, for example Bookworm to Trixie, is not a routine runtime update. Raspberry Pi recommends a clean install rather than an in-place upgrade on the existing boot media.

For this GitOps setup, treat a major OS upgrade as a rebuild:

1. Prepare new boot media or a new NVMe image.
2. Install the target Raspberry Pi OS Lite 64-bit image.
3. Bootstrap the host using the repository bootstrap procedure.
4. Restore host-only secrets and `.env` files from the secret backup path.
5. Restore persistent service data from tested backups.
6. Pull the repository with `git pull --ff-only`.
7. Deploy stacks from Git.
8. Run `make postdeploy`.
9. Keep the previous boot media or disk image until rollback is no longer needed.

Do not model major OS upgrades as `apt dist-upgrade` or as a Renovate change.

### 4.3 `rpi-update` is excluded

Do not use `rpi-update` for routine maintenance. Raspberry Pi documents `rpi-update` as a tool for experimental or pre-release firmware and states that routine updates should use APT instead.

Only allow `rpi-update` under a documented exception, for example a vendor support case or explicit Raspberry Pi engineer recommendation. Such an exception must include:

- reason
- source link or support reference
- backup confirmation
- exact command
- rollback plan
- post-deploy validation result

---

## 5. References

- Raspberry Pi OS update and upgrade documentation: <https://www.raspberrypi.com/documentation/computers/os.html>
- Raspberry Pi Linux kernel update note: <https://www.raspberrypi.com/documentation/computers/linux_kernel.html#update>
- Raspberry Pi EEPROM update documentation: <https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#rpi-eeprom-update>
- Docker Engine on Raspberry Pi OS: <https://docs.docker.com/engine/install/raspberry-pi-os/>
- Docker Engine on Debian for 64-bit ARM package path: <https://docs.docker.com/engine/install/debian/>
- Docker Compose plugin installation and update: <https://docs.docker.com/compose/install/linux/>
- Renovate Docker support and digest pinning: <https://docs.renovatebot.com/docker/>
- Renovate Docker Compose manager: <https://docs.renovatebot.com/modules/manager/docker-compose/>
- Renovate GitHub Actions manager: <https://docs.renovatebot.com/modules/manager/github-actions/>

---

## 6. Design decisions

1. **Plan and apply are separate operations.** `make host-upgrade-plan` is used to inspect the update set before `make host-upgrade-apply` changes the host.

2. **No automatic reboot.** Runtime scripts may report that a reboot is required, but rebooting remains an explicit operator action.

3. **No `rpi-update` in routine maintenance.** Routine OS, kernel, and stable firmware updates use APT. Experimental firmware is excluded unless a documented exception exists.

4. **EEPROM updates are explicit.** `make host-eeprom-apply` is separate from `make host-upgrade-apply` because bootloader maintenance has a different risk profile from normal package updates.

5. **Mutating host targets require a clean Git work tree.** The Pi must not contain uncommitted or experimental state before host changes are applied.

6. **The Pi remains deploy target only.** Runtime maintenance is executed on the Pi, but source edits, validation commits, and development remain on the workstation/WSL side.

7. **Renovate and host runtime maintenance are intentionally separate.** Renovate changes version-controlled dependency declarations; host runtime targets change the installed host runtime.

8. **Major OS upgrades are rebuilds.** A major Raspberry Pi OS version change is implemented as a clean OS image, bootstrap, restore, deploy, and post-deploy verification flow.

9. **Post-deploy validation is mandatory.** A runtime update is not considered complete until `make postdeploy` passes after any required reboot.

10. **Rollback expectations differ by layer.** Repository changes roll back through Git. Host package or OS changes roll back through backups, boot media, snapshots, or rebuilds.
