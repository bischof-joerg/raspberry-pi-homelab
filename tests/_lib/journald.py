from __future__ import annotations


def effective_settings(text: str, section: str = "Journal") -> dict[str, str]:
    """Merge journald configuration text the way journald does (F62).

    `text` is one file or the output of `systemd-analyze cat-config systemd/journald.conf`, which
    lists the main file and every drop-in in the order journald applies them. Within `section`, the
    last assignment of a key wins and an empty assignment resets it to the compiled-in default.
    Comment lines (`#`, `;`), including cat-config's `# /path` headers, are ignored.
    """
    settings: dict[str, str] = {}
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line[0] in "#;":
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip()
            continue
        if current != section or "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if value:
            settings[key] = value
        else:
            settings.pop(key, None)
    return settings
