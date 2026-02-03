from __future__ import annotations

import time

import requests


def wait_http_ok(url: str, timeout_s: int = 45, allow_redirects: bool = True) -> None:
    """
    Wait until an HTTP endpoint becomes available and returns a success status.

    Strict semantics:
      - success = 200-399 (2xx + 3xx)
      - 4xx/5xx are considered NOT ready (including 404)
      - network errors are retried until timeout

    Raises AssertionError on timeout.
    """
    t0 = time.time()
    last: str | None = None

    while time.time() - t0 < timeout_s:
        try:
            r = requests.get(url, timeout=3, allow_redirects=allow_redirects)
            if 200 <= r.status_code < 400:
                return
            # Treat all non-2xx/3xx as not-ready; include short body for diagnostics
            last = f"{r.status_code}: {r.text[:200]}"
        except Exception as e:
            last = str(e)
        time.sleep(1)

    raise AssertionError(f"Timeout waiting for {url} (last={last})")


def get_json(url: str) -> dict:
    r = requests.get(url, timeout=5)
    r.raise_for_status()
    return r.json()
