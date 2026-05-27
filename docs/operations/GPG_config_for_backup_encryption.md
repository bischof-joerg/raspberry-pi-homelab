# GPG Configuration for Backup Encryption

Last updated: 2026-05-27

This document defines GnuPG installation, key handling, KeePassXC storage, and repository integration for encrypted Raspberry Pi homelab backups.

The architectural decision is:

```text
Encryption model:
  OpenPGP public-key encryption with GnuPG.

Backup key:
  Dedicated "Homelab Backup Recovery" key.
  Generated on WSL/Admin.
  No expiry date.
  Private key never installed on Pi.

Pi:
  Stores only public key.
  Pins full fingerprint.
  Produces encrypted .tar.zst.gpg artifacts.
  Runs artifact verification only.

WSL/Admin:
  Holds private key in the local repository checkout under a Git-ignored path.
  Runs decrypt verification and restore tests.

KeePassXC:
  Stores GPG passphrase, key metadata, backup storage credentials,
  private-key export attachment, restore notes, and revocation certificate.
```

Important wording: "in the GitHub project" means the local working tree for the repository, not the GitHub remote. The private key must be ignored by Git and must never be pushed.

---

## 1. Package Installation

### 1.1 WSL/Admin

Install on WSL Ubuntu:

```bash
sudo apt update
sudo apt install -y \
  gnupg \
  gpg-agent \
  dirmngr \
  pinentry-curses \
  ca-certificates \
  tar \
  zstd \
  coreutils
```

Configure terminal pinentry:

```bash
mkdir -p ~/.gnupg
chmod 700 ~/.gnupg

cat > ~/.gnupg/gpg-agent.conf <<'EOF'
pinentry-program /usr/bin/pinentry-curses
EOF

if ! grep -q 'GPG_TTY' ~/.profile; then
  echo 'export GPG_TTY=$(tty)' >> ~/.profile
fi

gpg-connect-agent reloadagent /bye
```

Open a new shell or run:

```bash
source ~/.profile
```

### 1.2 Raspberry Pi

Install on Raspberry Pi OS Lite:

```bash
sudo apt update
sudo apt install -y \
  gnupg \
  gpg-agent \
  dirmngr \
  ca-certificates \
  tar \
  zstd \
  coreutils
```

Create the dedicated public-key-only GnuPG home:

```bash
sudo install -d -m 0700 -o root -g root /var/lib/homelab-backup/gnupg
```

The Pi must not import or store the private backup key.

---

## 2. Repository Layout

Recommended tracked files:

```text
config/backup/homelab-backup-recovery-public.asc
config/backup/homelab-backup-recovery-public.fingerprint
docs/architecture/adr/ADR-009-backup-verify-restore.md
docs/operations/BackupVerifyRestore.md
docs/operations/GPG_config_for_backup_encryption.md
```

Recommended local-only files in the WSL/Admin checkout:

```text
secrets/backup/gpg/homelab-backup-recovery-secret.asc
secrets/backup/gpg/homelab-backup-recovery-ownertrust.txt
secrets/backup/gpg/homelab-backup-revocation.asc
```

Required `.gitignore` entries:

```gitignore
/secrets/
*.kdbx
*.keyx
*.env
*.asc.tmp
*.tar
*.tar.zst
```

Do not ignore the public key:

```text
config/backup/homelab-backup-recovery-public.asc
```

---

## 3. Generate the Backup Key on WSL/Admin

Generate a dedicated key with no expiry:

```bash
gpg --quick-generate-key \
  "Homelab Backup Recovery <backup-recovery@home.local>" \
  default \
  default \
  never
```

List the key and capture the full fingerprint:

```bash
gpg --list-secret-keys --keyid-format LONG --with-fingerprint \
  "Homelab Backup Recovery"
```

Set the fingerprint variable for the current shell:

```bash
export GPG_RECIPIENT_FINGERPRINT="0123456789ABCDEF0123456789ABCDEF01234567"
```

Use the real 40-hex fingerprint from `gpg --with-fingerprint`.

---

## 4. Export Public and Private Material

Create target directories:

```bash
mkdir -p config/backup
mkdir -p secrets/backup/gpg
chmod 700 secrets secrets/backup secrets/backup/gpg
```

Export the public key for Git tracking:

```bash
gpg --armor --export "$GPG_RECIPIENT_FINGERPRINT" \
  > config/backup/homelab-backup-recovery-public.asc
```

Write the pinned fingerprint:

```bash
printf '%s\n' "$GPG_RECIPIENT_FINGERPRINT" \
  > config/backup/homelab-backup-recovery-public.fingerprint
```

Export the private key into the local Git-ignored directory:

```bash
umask 077

gpg --armor --export-secret-keys "$GPG_RECIPIENT_FINGERPRINT" \
  > secrets/backup/gpg/homelab-backup-recovery-secret.asc

gpg --export-ownertrust \
  > secrets/backup/gpg/homelab-backup-recovery-ownertrust.txt
```

Create a revocation certificate:

```bash
gpg --gen-revoke "$GPG_RECIPIENT_FINGERPRINT" \
  > secrets/backup/gpg/homelab-backup-revocation.asc
```

Check local permissions:

```bash
chmod 600 secrets/backup/gpg/*.asc secrets/backup/gpg/*.txt
```

---

## 5. Verify the Public Key Fingerprint

Use this check in pre-commit, CI, deploy, and backup scripts:

```bash
expected_fpr="$(tr -d '[:space:]' < config/backup/homelab-backup-recovery-public.fingerprint)"
actual_fpr="$(
  gpg --show-keys --with-colons config/backup/homelab-backup-recovery-public.asc \
    | awk -F: '$1 == "fpr" { print $10; exit }'
)"

if [ "$actual_fpr" != "$expected_fpr" ]; then
  echo "ERROR: backup public key fingerprint mismatch" >&2
  echo "Expected: $expected_fpr" >&2
  echo "Actual:   $actual_fpr" >&2
  exit 1
fi
```

Any mismatch is a security failure. It means future backups may be encrypted to the wrong recipient.

---

## 6. Install Public Key on Pi

Copy the public key and fingerprint through the Git checkout or deploy process. Then import only the public key:

```bash
cd ~/iac/raspberry-pi-homelab

sudo install -d -m 0700 -o root -g root /var/lib/homelab-backup/gnupg

sudo GNUPGHOME=/var/lib/homelab-backup/gnupg \
  gpg --import config/backup/homelab-backup-recovery-public.asc
```

Verify the Pi has no private backup key:

```bash
sudo GNUPGHOME=/var/lib/homelab-backup/gnupg \
  gpg --list-secret-keys
```

Expected result: no secret keys are listed.

Verify the public key fingerprint on Pi:

```bash
sudo GNUPGHOME=/var/lib/homelab-backup/gnupg \
  gpg --list-keys --with-fingerprint
```

---

## 7. Encrypt Backup Artifacts on Pi

The backup script should stream tar to zstd to GPG:

```bash
export GNUPGHOME=/var/lib/homelab-backup/gnupg
export GPG_RECIPIENT_FINGERPRINT="0123456789ABCDEF0123456789ABCDEF01234567"

tar --create --numeric-owner --one-file-system \
  -C /srv/data/stacks/monitoring \
  grafana \
  | zstd -T0 -19 \
  | gpg --batch --yes --trust-model always \
      --encrypt \
      --recipient "$GPG_RECIPIENT_FINGERPRINT" \
      --output data/monitoring-grafana.tar.zst.gpg
```

For host-only secrets:

```bash
sudo tar --create --numeric-owner -C /etc raspberry-pi-homelab \
  | zstd -T0 -19 \
  | sudo GNUPGHOME=/var/lib/homelab-backup/gnupg \
      gpg --batch --yes --trust-model always \
        --encrypt \
        --recipient "$GPG_RECIPIENT_FINGERPRINT" \
        --output secrets/etc-raspberry-pi-homelab.tar.zst.gpg
```

`--trust-model always` is acceptable only because the script pins and verifies the full fingerprint before encryption. Do not use an email address as the sole recipient selector in automated backups.

---

## 8. Pi-Side Artifact Verification

Pi-side verification must not require private-key access.

Check checksum:

```bash
cd /srv/backups/homelab/<timestamp>
sha256sum -c checksums.sha256
```

Check OpenPGP packet readability:

```bash
GNUPGHOME=/var/lib/homelab-backup/gnupg \
  gpg --batch --list-packets secrets/etc-raspberry-pi-homelab.tar.zst.gpg >/dev/null
```

Check that no secret keys exist on Pi:

```bash
sudo GNUPGHOME=/var/lib/homelab-backup/gnupg \
  gpg --list-secret-keys
```

Do not label this as a restore test. It proves artifact integrity, not decryptability.

---

## 9. WSL/Admin Decrypt Verification

The private key exists on WSL/Admin. Verify decryptability there:

```bash
BACKUP_DIR=/path/to/backup

gpg --decrypt "$BACKUP_DIR/secrets/etc-raspberry-pi-homelab.tar.zst.gpg" \
  | zstd -d \
  | tar -tf - >/dev/null
```

Verify a data artifact:

```bash
gpg --decrypt "$BACKUP_DIR/data/monitoring-grafana.tar.zst.gpg" \
  | zstd -d \
  | tar -tf - >/dev/null
```

Extract into staging:

```bash
rm -rf /tmp/homelab-restore-test
mkdir -p /tmp/homelab-restore-test

gpg --decrypt "$BACKUP_DIR/secrets/etc-raspberry-pi-homelab.tar.zst.gpg" \
  | zstd -d \
  | tar --extract --preserve-permissions --numeric-owner --file - --directory /tmp/homelab-restore-test
```

---

## 10. KeePassXC Storage Model

Create this KeePassXC group structure:

```text
Homelab/
  Backup/
    GPG Backup Recovery Key
    Backup Storage Credentials
    Restore Procedure
  Infrastructure/
    Pi SSH
    GitHub Deploy Key
    Traefik DNS Provider Token
  Monitoring/
    Grafana Admin
    Alertmanager Webhooks
  Apps/
```

### 10.1 `Homelab / Backup / GPG Backup Recovery Key`

Store:

- key name: `Homelab Backup Recovery <backup-recovery@home.local>`
- full fingerprint
- key ID
- creation date
- no-expiry decision
- private-key passphrase
- location of local private-key export
- location of offline copy

Attach:

```text
homelab-backup-recovery-secret.asc
homelab-backup-recovery-ownertrust.txt
homelab-backup-revocation.asc
```

### 10.2 `Homelab / Backup / Backup Storage Credentials`

Store remote/offsite storage credentials when remote replication is added:

- S3/B2/WebDAV/rclone endpoint
- bucket/container name
- access key ID
- secret access key
- retention notes
- recovery URL or provider notes

### 10.3 `Homelab / Backup / Restore Procedure`

Store a short recovery note:

```text
1. Open KeePassXC.
2. Locate Homelab / Backup / GPG Backup Recovery Key.
3. Confirm fingerprint.
4. Restore private key on WSL/Admin if needed.
5. Decrypt backup artifact on WSL/Admin.
6. Stream restore to Pi over SSH.
7. Run sudo ./deploy.sh and make postdeploy.
```

KeePassXC must not be the only copy of the private key or recovery instructions.

---

## 11. Offline Recovery Material

Maintain an offline copy containing:

```text
homelab-backup-recovery-secret.asc
homelab-backup-recovery-ownertrust.txt
homelab-backup-revocation.asc
KeePassXC database backup
printed or exported restore note
```

Recommended storage pattern:

- one local offline USB/SD card
- one offsite copy
- printed fingerprint and recovery hint
- periodic readability check

The revocation certificate is sensitive. Anyone with it can revoke the key. Store it with the same care as the private key.

---

## 12. Restoring the Private Key on WSL/Admin

If WSL/Admin is rebuilt, import the private key from KeePassXC or offline media:

```bash
gpg --import secrets/backup/gpg/homelab-backup-recovery-secret.asc
gpg --import-ownertrust secrets/backup/gpg/homelab-backup-recovery-ownertrust.txt
```

Verify:

```bash
gpg --list-secret-keys --with-fingerprint "Homelab Backup Recovery"
```

Then run decrypt verification against a known backup:

```bash
gpg --decrypt /path/to/backup/secrets/etc-raspberry-pi-homelab.tar.zst.gpg \
  | zstd -d \
  | tar -tf - >/dev/null
```

---

## 13. Emergency-Only Private Key Import on Pi

Normal restore must not import the private key on the Pi.

Emergency exception:

1. Import private key from offline media.
2. Restore required artifacts.
3. Delete the private key.
4. Delete the temporary GnuPG home if one was used.
5. Reboot or otherwise confirm no agent cache remains.
6. Record the exception in the restore log.

Example cleanup:

```bash
sudo GNUPGHOME=/root/tmp-restore-gnupg gpg --delete-secret-keys "$GPG_RECIPIENT_FINGERPRINT"
sudo rm -rf /root/tmp-restore-gnupg
```

---

## 14. Operational Checks

Run on Pi:

```bash
sudo GNUPGHOME=/var/lib/homelab-backup/gnupg gpg --list-secret-keys
```

Expected: empty.

Run in repository:

```bash
git status --short
```

Expected: no private-key material listed as staged or tracked.

Check tracked files:

```bash
git ls-files | grep -E '(^secrets/|\.kdbx$|homelab-backup-recovery-secret|revocation)'
```

Expected: no output.

---

## 15. References

- GnuPG operational commands: https://www.gnupg.org/documentation/manuals/gnupg/Operational-GPG-Commands.html
- GnuPG OpenPGP key management: https://www.gnupg.org/documentation/manuals/gnupg/OpenPGP-Key-Management.html
- KeePassXC documentation: https://keepassxc.org/docs/
- Debian `pinentry-curses` package: https://packages.debian.org/stable/pinentry-curses
