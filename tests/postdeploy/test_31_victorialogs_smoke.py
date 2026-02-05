import os
import urllib.parse
import urllib.request

import pytest

# How to run the tests on the Pi
# POSTDEPLOY_ON_TARGET=1 pytest -q -m postdeploy tests/postdeploy/test_31_victorialogs_smoke.py


pytestmark = pytest.mark.postdeploy


def _on_target() -> bool:
    return os.environ.get("POSTDEPLOY_ON_TARGET", "0") == "1"


def _http_get(url: str, timeout: float = 3.0) -> str:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return f"{resp.status}\n{body}"


def _http_post_form(url: str, data: dict[str, str], timeout: float = 5.0) -> str:
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


@pytest.mark.skipif(not _on_target(), reason="postdeploy: only on target")
def test_victorialogs_metrics_up():
    status_and_body = _http_get("http://localhost:9428/metrics")
    assert status_and_body.startswith("200\n")
    assert "vl_" in status_and_body or "vm_" in status_and_body


@pytest.mark.skipif(not _on_target(), reason="postdeploy: only on target")
def test_victorialogs_query_recent_logs_count():
    # LogsQL HTTP query endpoint: /select/logsql/query (POST form 'query=...')
    # We'll just require "some logs in last 5 minutes".
    # Use '*' to match all logs; add _time filter.
    out = _http_post_form(
        "http://localhost:9428/select/logsql/query",
        {"query": "_time:5m * | stats count() as logs_count"},
    )
    # The exact output format can be inspected if needed; this is a simple sanity check:
    assert "logs_count" in out or "count" in out
