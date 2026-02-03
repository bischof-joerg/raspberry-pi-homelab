from __future__ import annotations

import time

import requests


def wait_http_ok(url: str, timeout_s: int = 45) -> None:
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout_s:
        try:
            r = requests.get(url, timeout=3)
            if r.status_code < 500:
                return
            last = f"{r.status_code}: {r.text[:200]}"
        except Exception as e:
            last = str(e)
        time.sleep(1)
    raise AssertionError(f"Timeout waiting for {url} (last={last})")


def get_json(url: str) -> dict:
    r = requests.get(url, timeout=5)
    r.raise_for_status()
    return r.json()
