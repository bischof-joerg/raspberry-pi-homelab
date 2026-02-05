# Vector

## Journald access runbook (required for containerized Vector)

Reading journald from inside a container is primarily a permissions problem.

Ensure Docker uses journald logging driver (host-level change).

Ensure Vector can read:

- `/run/log/journal` and `/var/log/journal` (mounted read-only)
- `/etc/machine-id` (mounted read-only; required by sd-journal readers)

If Vector gets “permission denied” on journal files:

- Preferred: grant read to the journal directories via a **dedicated group** (e.g. `systemd-journal`) and align container group id or apply an ACL for a dedicated runtime group.
- Keep this as an **idempotent host script** (similar to your existing init-permissions approach) to prevent drift.

(We can implement the idempotent script next, but the above is the minimum you need documented because it’s environment-specific.)
