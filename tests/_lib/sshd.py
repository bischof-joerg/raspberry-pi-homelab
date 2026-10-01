"""Read sshd configuration text for the F67 checks (R1.21)."""

from __future__ import annotations

# What stacks/core/ssh/10-homelab-hardening.conf sets, globally and in its `Match all` block, and
# what `sshd -T -C user=admin,...` must report on the Pi (keys in sshd -T's lower case).
HARDENING = {
    "allowtcpforwarding": "no",
    "allowagentforwarding": "no",
    "allowstreamlocalforwarding": "no",
    "x11forwarding": "no",
    "permittunnel": "no",
    "permitrootlogin": "no",
    "passwordauthentication": "no",
}


def parse_config(text: str) -> tuple[dict[str, str], list[tuple[str, dict[str, str]]]]:
    """Split an sshd config file into its global keywords and its Match blocks.

    Keys are lower-cased like sshd -T prints them; within one section the first value counts, as
    sshd applies it. A Match block runs to the next Match line or the end of the text.
    """
    global_values: dict[str, str] = {}
    blocks: list[tuple[str, dict[str, str]]] = []
    current = global_values
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        key, _, value = line.partition(" ")
        if key.lower() == "match":
            blocks.append((value.strip().lower(), {}))
            current = blocks[-1][1]
            continue
        current.setdefault(key.lower(), value.strip())
    return global_values, blocks


def effective_values(sshd_t_output: str) -> dict[str, str]:
    """Parse `sshd -T` output (one `key value` per line) into a dict."""
    values = {}
    for line in sshd_t_output.splitlines():
        key, _, value = line.strip().partition(" ")
        if key:
            values[key] = value
    return values
