---
paths:
  - "**/*.sh"
---

# Shell scripts

19 scripts in this repository. They reconcile host state, so a sloppy one is not a style problem —
it is a production incident on the Pi.

## MUST

- **Start with `#!/usr/bin/env bash` and `set -euo pipefail`.** 15 of 19 scripts do; the four that
  do not are a defect, not a precedent.
- **Pass ShellCheck** with the pinned version from `.venv` (`shellcheck-py` 0.10.0.1, identical to
  the pre-commit hook). Never judge by the system ShellCheck — it is 0.9.0 and disagrees (F21).
  Run it as `git ls-files '*.sh' | xargs -r .venv/bin/shellcheck -x`; `-x` follows sourced files.
- **Be idempotent.** A second run on an already-correct host must change nothing and exit 0.
  Check the desired state first, act only on a difference.
- **Guard the platform.** Pi-only scripts must refuse to run elsewhere and vice versa; the Makefile
  has `_guard-wsl` and `_guard-pi` for the same reason.
- **Quote every expansion** — `"$var"`, `"${arr[@]}"` — and prefer `[[ ]]` over `[ ]`.
- **Use LF line endings.** `.gitattributes` enforces `*.sh text eol=lf`; a CRLF shebang breaks the
  script on the Pi with a confusing error.
- **Never hardcode a host-specific path or name.** `cleanup-ufw.sh` still carries
  `/home/admin/iac/...` in its usage text and the stale bridge names `br-abe`/`br-bd2` in a regex
  (F19) — that is the anti-pattern.

## SHOULD

- **Default to dry-run for anything destructive**, with an explicit `--apply` to act.
  `cleanup-ufw.sh` does this correctly.
- Use `mktemp` instead of a fixed temp path. `bootstrap-networks.sh` uses a fixed
  `/tmp/bootstrap-networks.overlap`, which collides between concurrent runs (F19).
- Give a non-zero exit code a distinct meaning and document it in the script header.
- Keep the shared helpers in `common.sh` rather than copying logic between scripts.

## Claude must not execute them

Every script under `scripts/host/`, `scripts/host-runtime/`, `scripts/network/`, plus
`init-permissions.sh` and `deploy.sh`, mutates root-owned host state. They are Pi-only and are
**never** run here — not even in check or dry-run mode (C5). Reading, reviewing and editing them is
fine. See `host-runtime.md` for what each one actually does.

## Sources

`deploy.sh`, `scripts/`, `.pre-commit-config.yaml`, `.gitattributes`, `Makefile`,
`.claude/ClaudeTransition.md` findings F19 and F21.

## Violations

```bash
#!/bin/bash                    # not env-based
cd $DIR && rm -rf $TARGET/*    # unquoted, unguarded, no dry-run
```
