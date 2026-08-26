"""Shared low-level HTTP plumbing for cordless's REST layer.

Extracted from what used to be Cordless._discord_request so it works without a
Cordless instance - every _rest/<resource>.py module awaits request()/request_raw()
directly. Cordless._discord_request is now a thin async shim over request_raw().

request()/request_raw() are async, matching every other public REST call in
cordless, but the actual urllib work is blocking - each call runs the whole
retry loop in a worker thread via run_in_executor, the same one-executor-call-
per-outbound-request shape the rest of the codebase already uses.
"""

import asyncio
import json
import os
import urllib.error
import urllib.parse
import urllib.request

# bound directly rather than `import time` - asyncio's own event loop clock
# is time.monotonic(), so a test monkeypatching that module-level attribute
# to control this retry loop would also corrupt asyncio's internal timeouts
from time import monotonic, sleep

from .. import ratelimit
from .._multipart import build_multipart_body
from .._useragent import USER_AGENT
from ..context import _attach_files

# How long a request keeps retrying a 429 before giving up. Matches
# defer_worker's 30s default timeout - callers doing bursty sends from the
# main function's default 10s timeout should raise `timeout` in
# cordless.toml or move the work behind defer_worker.
_MAX_RETRY_SECONDS = 30.0


def _request_raw_sync(method, path, payload=None, files=None, token=None, raw_body=None, reason=None):
    """The actual blocking urllib work; only ever run inside an executor thread.

    raw_body is an escape hatch for the handful of endpoints that don't use
    Discord's payload_json + files[n] attachment convention (e.g. Create
    Guild Sticker's plain multipart form): pass a pre-built
    (body_bytes, content_type) pair and it's sent as-is, bypassing payload/files.

    reason sets X-Audit-Log-Reason, shown in the guild's audit log next to
    the resulting entry: only meaningful on endpoints Discord actually
    audit-logs, but harmless to send otherwise."""
    token = token or os.environ["DISCORD_BOT_TOKEN"]
    if raw_body is not None:
        body, content_type = raw_body
    elif files:
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
        **({"X-Audit-Log-Reason": urllib.parse.quote(reason)} if reason else {}),
    }

    url = f"https://discord.com/api/v10{path}"
    deadline = monotonic() + _MAX_RETRY_SECONDS
    network_retried = False
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
            if exc.code == 429 and monotonic() < deadline:
                try:
                    # .get(..., 1) only covers a missing key - an explicit
                    # {"retry_after": null} body still reaches float(None),
                    # hence TypeError alongside the parsing failure modes
                    retry_after = float(json.loads(body_out).get("retry_after", 1))
                except (TypeError, ValueError, AttributeError):
                    retry_after = 1.0
                ratelimit.note_blocked(method, path, retry_after)
                sleep(ratelimit.jittered_wait(retry_after))
                continue
            raise RuntimeError(f"Discord API error {exc.code}: {body_out.decode(errors='replace')}") from exc
        except OSError:
            # a transient network blip (connection reset, dropped keep-alive, ...),
            # not an HTTP-level error, retry once, same as webhook.py/defer.py do
            # for their kept-alive connections.
            if network_retried:
                raise
            network_retried = True
            continue


async def request_raw(method, path, payload=None, files=None, token=None, raw_body=None, reason=None):
    """Make an authenticated Discord API call, retrying 429s. Returns the raw response body."""
    return await asyncio.get_event_loop().run_in_executor(
        None, _request_raw_sync, method, path, payload, files, token, raw_body, reason
    )


async def request(method, path, payload=None, files=None, token=None, raw_body=None, reason=None):
    """Like request_raw, but parses the JSON response body (None for an empty body)."""
    data = await request_raw(method, path, payload, files, token=token, raw_body=raw_body, reason=reason)
    return json.loads(data) if data else None


def query_string(**params):
    """Shared query-string builder for GET endpoints' optional scalar
    filters (limit/before/after/..., and boolean flags like with_counts).

    None and False are omitted: a flag defaulting to False reads the same
    as not sending it at all, which is what every existing caller wants.
    True becomes Discord's lowercase "true". Values are URL-encoded.
    Doesn't handle list values: Discord's array-style query params
    (author_id=1&author_id=2) need the repeated-key shape messages.py's
    _array_qs builds instead, and comma-joined ones (include_roles) join
    before being passed in here."""
    parts = []
    for key, value in params.items():
        if value is None or value is False:
            continue
        v = "true" if value is True else value
        parts.append(f"{key}={urllib.parse.quote(str(v))}")
    return ("?" + "&".join(parts)) if parts else ""


def pagination_qs(*, before=None, limit=None):
    """Shared query-string builder for the handful of endpoints paginated by
    before/limit (archived threads, channel pins, ...)."""
    return query_string(before=before, limit=limit)


class _Unset:
    __slots__ = ()

    def __repr__(self):
        return "UNSET"


UNSET = _Unset()


def payload(**fields):
    """Build a request body from a resource function's optional kwargs,
    keeping only the ones the caller actually set. Fields default to UNSET
    rather than None, so passing None explicitly (Discord's way of clearing
    a nullable field, e.g. nick=None or parent_id=None) still comes through
    instead of being silently dropped."""
    return {k: v for k, v in fields.items() if v is not UNSET}
