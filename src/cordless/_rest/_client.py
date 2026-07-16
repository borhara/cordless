"""Shared low-level HTTP plumbing for cordless's REST layer.

Extracted from what used to be Cordless._discord_request so it works without a
Cordless instance - every _rest/<resource>.py module calls request()/request_raw()
directly. Cordless._discord_request is now a thin shim over request_raw() so
existing callers/tests that patch it keep working unchanged.
"""

import json
import os
import time
import urllib.error
import urllib.request

from .. import ratelimit
from .._multipart import build_multipart_body
from .._useragent import USER_AGENT
from ..context import _attach_files

# How long a request keeps retrying a 429 before giving up. Matches
# defer_worker's 30s default timeout - callers doing bursty sends from the
# main function's default 10s timeout should raise `timeout` in
# cordless.toml or move the work behind defer_worker.
_MAX_RETRY_SECONDS = 30.0


def request_raw(method, path, payload=None, files=None, token=None):
    """Make an authenticated Discord API call, retrying 429s. Returns the raw response body."""
    token = token or os.environ["DISCORD_BOT_TOKEN"]
    if files:
        _attach_files(payload, files)
        body, content_type = build_multipart_body(payload, files)
    elif payload is not None:
        body, content_type = json.dumps(payload).encode(), "application/json"
    else:
        body, content_type = None, None
    headers = {
        "Authorization": f"Bot {token}",
        "User-Agent": USER_AGENT,
        **({"Content-Type": content_type} if content_type else {}),
    }

    url = f"https://discord.com/api/v10{path}"
    deadline = time.monotonic() + _MAX_RETRY_SECONDS
    while True:
        ratelimit.wait_if_needed(method, path)
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                data = resp.read()
                ratelimit.record_response(method, path, resp.headers)
                return data
        except urllib.error.HTTPError as exc:
            body_out = exc.read()
            if exc.code == 429 and time.monotonic() < deadline:
                try:
                    retry_after = float(json.loads(body_out).get("retry_after", 1))
                except (ValueError, AttributeError):
                    retry_after = 1.0
                ratelimit.note_blocked(method, path, retry_after)
                time.sleep(ratelimit.jittered_wait(retry_after))
                continue
            raise RuntimeError(f"Discord API error {exc.code}: {body_out.decode(errors='replace')}") from exc


def request(method, path, payload=None, files=None, token=None):
    """Like request_raw, but parses the JSON response body (None for an empty body)."""
    data = request_raw(method, path, payload, files, token=token)
    return json.loads(data) if data else None
