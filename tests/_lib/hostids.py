from __future__ import annotations

import grp
import pwd


def resolve_nobody_nogroup() -> tuple[int, int]:
    """
    Mirror init-permissions.sh (resolve_nobody_ids):
    - user: nobody
    - group: prefer 'nogroup' if present, else nobody's primary gid
    """
    try:
        nobody = pwd.getpwnam("nobody")
    except KeyError as e:
        raise RuntimeError("Cannot resolve user 'nobody' on this host") from e

    try:
        return nobody.pw_uid, grp.getgrnam("nogroup").gr_gid
    except KeyError:
        return nobody.pw_uid, nobody.pw_gid
