# ADR-0013: Read-only /boot/firmware with an APT remount hook

- **Status:** Accepted (operator, 2026-09-29, after deploy, postdeploy and a controlled reboot)
- **Date:** 2026-09-29
- **Scope:** the firmware partition `/boot/firmware` on the Pi; every APT caller on the Pi
  (unattended-upgrades, `make host-upgrade-apply`, a manual `apt-get`)

## Context

Finding F60, measured on the Pi on 2026-09-29:

- `/etc/fstab` mounts the firmware partition read-only on purpose:
  `PARTUUID=dab535d3-01  /boot/firmware  vfat  defaults,ro,nosuid,nodev,noexec  0  2`
  (file changed 2026-01-01). The entry exists only on the host; the repository does not manage
  `fstab`. `HostFilesystemReadOnly` in `stacks/monitoring/vmalert/rules/host-storage.yml` has
  exempted `/boot/firmware` since 2026-01-08 (commit `2f1c49d`), without a written reason.
- The package `raspi-firmware` installs `/etc/initramfs/post-update.d/z50-raspi-firmware` and
  `/etc/kernel/postinst.d/z50-raspi-firmware`. Inside dpkg they copy the newest initramfs and
  kernel of each flavour into `/boot/firmware`. On the read-only partition the copy fails,
  `initramfs-tools` stays half-configured, and **every** APT run exits 1 — including
  unattended-upgrades, which has installed no security update since at least 2026-09-26.
- The partition was made writable by hand at least once for a kernel update (firmware files dated
  2026-05-27); that procedure is written down nowhere.

Read in apt 3.0.3 (`apt-pkg/deb/dpkgpm.cc`, `pkgDPkgPM::Go`): a failing `DPkg::Pre-Invoke` returns
before dpkg runs; after a dpkg failure the loop stops, but `DPkg::Post-Invoke` still runs. Between
the two hooks, only internal errors (`pipe`, `mkdtemp`, `symlink`) and a failing
`DPkg::Pre-Install-Pkgs` return early. `apt-daily-upgrade.service` has no `ProtectSystem`,
`ReadWritePaths` or `PrivateMounts`, so a remount from the hook applies to the host.

## Decision

1. `/boot/firmware` **stays read-only** between package operations. The fstab line above is the
   expected host state; it is checked, not reconciled (`tests/postdeploy/test_06_host_boot_firmware.py`).
2. APT remounts it read-write for each dpkg run and read-only afterwards, through
   `/etc/apt/apt.conf.d/99homelab-boot-firmware` (source `stacks/core/apt/99homelab-boot-firmware`):
   `DPkg::Pre-Invoke` → `homelab-boot-firmware rw`, `DPkg::Post-Invoke` → `homelab-boot-firmware ro`.
3. The hook calls a **root-owned copy** of `scripts/host/homelab-boot-firmware.sh` at
   `/usr/local/sbin/homelab-boot-firmware`, never a file in the checkout: APT runs hooks as root,
   and the checkout belongs to `admin`, so a hook into it would let `admin` become root.
4. The helper remounts only on a difference and logs every remount to the journal
   (`logger -t homelab-boot-firmware`). A failed `rw` exits 1, so APT stops before dpkg. A failed
   `ro` only warns and exits 0: a failing `DPkg::Post-Invoke` fails the whole APT run, which is the
   F60 symptom.
5. `deploy.sh` installs both files on every deploy with
   `scripts/host/ensure-apt-boot-firmware-hook.sh apply` (toggle `ENSURE_APT_BOOT_FIRMWARE_HOOK`),
   idempotently, as it does for `daemon.json`.

## Result (measured 2026-09-29)

Deployed with merge `3c5d7e5` (PR #51). The first deploy installed both files, the second logged
`apt-boot-firmware: OK (no changes)`; postdeploy was green both times, including
`tests/postdeploy/test_06_host_boot_firmware.py`. A single `sudo apt-get -y -f install` finished
the pending `initramfs-tools` configure with exit 0; `dpkg --audit` is empty, and the journal shows
the partition opened read-write and closed read-only again six seconds later.

The `initramfs-tools` trigger regenerated the initramfs of **every** installed kernel, so the file
the Pi 5 boots, `/boot/firmware/initramfs_2712`, changed as well (it equals
`/boot/initrd.img-6.18.29+rpt-rpi-2712`); the kernel image did not. A controlled reboot proved the
Pi boots it: kernel `6.18.29+rpt-rpi-2712`, `/boot/firmware` read-only, no failed units. Any APT run
that fires this trigger changes the boot path; the next reboot is its test.

## Alternatives considered

- **Give up the read-only mount** (Raspberry Pi OS default). Simplest and robust, but the operator
  chose to keep the partition protected from accidental writes between updates.
- **Remount inside `scripts/host-runtime/upgrade-apply.sh` only.** Rejected: unattended-upgrades and
  manual `apt-get` would still fail.
- **Call the helper from the checkout.** Rejected: privilege escalation from `admin` to root
  (Decision 3).

## Consequences

### Positive

- APT works again for every caller; security updates flow; kernel and initramfs updates reach the
  firmware partition.
- The protection stays in place outside package operations, and each opening is logged.

### Negative / Tradeoffs

- **A direct `dpkg -i` or `dpkg --configure` bypasses APT hooks** and fails as before. Use
  `apt-get` (for example `apt-get -f install` to finish a pending configure).
- If APT returns early between the hooks (internal errors above) or `ro` fails because the
  partition is busy, `/boot/firmware` stays read-write until the next APT run or reboot. The
  postdeploy check reports it; an alert needs vmalert to reload rule changes (F1) and is not part
  of this decision.
- The fstab line lives only on the host. A rebuilt host must set it again; whether it belongs in
  a bootstrap step or the backup inventory is open (R3).
- **Rollback:** reverting the change does not remove installed host files. After the revert is
  deployed, the operator runs
  `sudo rm /etc/apt/apt.conf.d/99homelab-boot-firmware /usr/local/sbin/homelab-boot-firmware`.
- Unattended-upgrades itself, including its automatic reboot at 03:30, is F61 and not decided
  here.

## Enforcement

- `tests/guards/test_55_boot_firmware_hook.py` — the snippet calls only the root-owned helper and
  parses as apt configuration; the helper's behaviour against stubbed `findmnt`/`mount`/`logger`;
  the ensure script's idempotency, drift detection and sandbox guard; the wiring in `deploy.sh`.
- `tests/postdeploy/test_06_host_boot_firmware.py` — on the Pi the installed files equal the
  repository and are `root:root` with modes `0755`/`0644`, and `/boot/firmware` is read-only after
  the deploy.
