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
import http.client
import json
import os
import threading
import urllib.error
import urllib.parse
import urllib.request

# bound directly rather than `import time` - asyncio's own event loop clock
# is time.monotonic(), so a test monkeypatching that module-level attribute
# to control this retry loop would also corrupt asyncio's internal timeouts
from time import monotonic, sleep
from typing import IO, cast

from .. import errors, ratelimit
from .._multipart import build_multipart_body
from .._payload import _attach_files
from .._useragent import USER_AGENT

# How long a request keeps retrying a 429 before giving up. Matches
# defer_worker's 30s default timeout - callers doing bursty sends from the
# main function's default 10s timeout should raise `timeout` in
# cordless.toml or move the work behind defer_worker.
_MAX_RETRY_SECONDS = 30.0

_TIMEOUT = 10

# Default idempotency-by-method for automatic retry after a network error:
# repeating one of these can't risk a duplicate side effect, since it's a
# no-op or lands on the same end state either way. POST and PATCH aren't
# included, since Discord gives no guarantee that resending one is safe if
# the first attempt actually reached Discord and was processed before the
# connection dropped.
#
# This is only a default, not a guarantee HTTP semantics enforce: it's
# verified true for every PUT _rest/*.py currently wraps (bulk command
# overwrite, pin/react/join/add-member-ish "ends up in state X" calls,
# sync template, ...), not something Discord's docs promise for every verb
# it might ever label PUT. A new PUT-based endpoint isn't automatically
# safe just because it's PUT: check that repeating it converges to the same
# state before trusting this default, and if it doesn't, pass
# idempotent=False explicitly at that call site (see request()/request_raw()).
_IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "PUT", "DELETE"})

# Kept open across invocations in a warm Lambda container, so most requests
# skip the TLS handshake instead of paying for it every time - same pattern
# as webhook.py/defer.py's own kept-alive connections.
_conn = None
_conn_lock = threading.Lock()


class _LockedResponse:
    """Proxies a 2xx http.client.HTTPResponse but keeps _conn_lock held
    until the caller is done reading it (released in __exit__). Releasing
    the lock right after getresponse(), before the body is read, lets a
    second concurrent caller send a new request on the same shared
    connection while this response is still unread; http.client refuses
    that (CannotSendRequest), and the reconnect-on-error path then closes
    the very socket this response's unread body still depends on."""

    def __init__(self, resp, lock):
        self._resp = resp
        self._lock = lock

    @property
    def status(self):
        return self._resp.status

    @property
    def headers(self):
        return self._resp.headers

    def read(self):
        return self._resp.read()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False

    def close(self):
        try:
            self._resp.close()
        finally:
            self._lock.release()


class _LockedErrorBody:
    """fp for the HTTPError raised on a non-2xx response, for the same
    hold-the-lock-until-read reason as _LockedResponse, but for the error
    path, where the caller drains the body via exc.read() outside of any
    `with` block, so the lock is released there instead of via __exit__.

    Needs its own close(), even though nothing here calls it directly:
    urllib.error.HTTPError is an io.IOBase subclass, so an HTTPError left
    unread and garbage-collected has its __del__ call close(), which calls
    fp.close(); without this, that raises AttributeError inside __del__
    (an "unraisable exception", silently logged rather than propagated)."""

    def __init__(self, resp, lock):
        self._resp = resp
        self._lock = lock
        self._released = False

    def read(self, *args):
        try:
            return self._resp.read(*args)
        finally:
            self._release()

    def close(self):
        try:
            self._resp.close()
        finally:
            self._release()

    def _release(self):
        if not self._released:
            self._released = True
            self._lock.release()


def _send(req, idempotent):
    """Send a urllib.request.Request over a persistent HTTPSConnection to
    discord.com instead of urllib.request.urlopen(), which always opens a
    fresh connection per call with no way to keep it warm. A drop-in
    replacement for urlopen() as far as callers can tell: a context manager
    with .read()/.headers on 2xx, raises urllib.error.HTTPError otherwise.

    idempotent is the caller's already-resolved answer (see
    _request_raw_sync) to whether resending req is safe; _send doesn't
    infer it from req's method itself, so it stays correct for a caller
    that overrode the default.

    _conn_lock is held across the whole call, including the caller's read
    of the response body (via _LockedResponse/_LockedErrorBody below), not
    just the request()/getresponse() pair; see their docstrings for why.
    """
    global _conn
    headers = dict(req.header_items())
    _conn_lock.acquire()
    try:
        if _conn is None:
            _conn = http.client.HTTPSConnection(req.host, timeout=_TIMEOUT)
        try:
            _conn.request(req.get_method(), req.selector, req.data, headers)
            resp = _conn.getresponse()
        except (http.client.HTTPException, OSError):
            # the other end closed the kept-alive connection. Always drop it
            # and open a fresh one so the next call doesn't inherit a dead
            # socket, but only actually resend this request when it's safe
            # to: if Discord already received and processed it before the
            # connection died, resending a non-idempotent request would
            # duplicate whatever it did (e.g. sending the same message twice)
            _conn.close()
            _conn = http.client.HTTPSConnection(req.host, timeout=_TIMEOUT)
            if not idempotent:
                raise
            _conn.request(req.get_method(), req.selector, req.data, headers)
            resp = _conn.getresponse()
    except BaseException:
        _conn_lock.release()
        raise

    if resp.status >= 300:
        # HTTPError's fp only needs to be duck-type compatible (read/close),
        # not literally IO[bytes]; cast rather than widen the real IO[bytes]
        # type callers of _LockedErrorBody.read() actually get back
        fp = cast(IO[bytes], _LockedErrorBody(resp, _conn_lock))
        raise urllib.error.HTTPError(req.full_url, resp.status, resp.reason, resp.headers, fp)
    return _LockedResponse(resp, _conn_lock)


def _request_raw_sync(method, path, payload=None, files=None, token=None, raw_body=None, reason=None, idempotent=None):
    """The actual blocking urllib work; only ever run inside an executor thread.

    raw_body is an escape hatch for the handful of endpoints that don't use
    Discord's payload_json + files[n] attachment convention (e.g. Create
    Guild Sticker's plain multipart form): pass a pre-built
    (body_bytes, content_type) pair and it's sent as-is, bypassing payload/files.

    reason sets X-Audit-Log-Reason, shown in the guild's audit log next to
    the resulting entry: only meaningful on endpoints Discord actually
    audit-logs, but harmless to send otherwise.

    idempotent overrides _IDEMPOTENT_METHODS' default safe-to-retry-after-
    a-network-error guess for method. Only needed for the rare endpoint
    where the default guess is wrong for that specific call, e.g. a PUT
    that isn't actually idempotent (see _IDEMPOTENT_METHODS' docstring)."""
    safe_to_retry = method in _IDEMPOTENT_METHODS if idempotent is None else idempotent
    if not token:
        try:
            token = os.environ["DISCORD_BOT_TOKEN"]
        except KeyError:
            raise errors.MissingTokenError("set DISCORD_BOT_TOKEN or pass token=...") from None
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
            with _send(req, safe_to_retry) as resp:
                data = resp.read()
                ratelimit.record_response(method, path, resp.headers)
                return data
        except urllib.error.HTTPError as exc:
            body_out = exc.read()
            if exc.code == 429:
                try:
                    # .get(..., 1) only covers a missing key - an explicit
                    # {"retry_after": null} body still reaches float(None),
                    # hence TypeError alongside the parsing failure modes
                    retry_after = float(json.loads(body_out).get("retry_after", 1))
                except (TypeError, ValueError, AttributeError):
                    retry_after = 1.0
                # note_blocked runs even if we're about to give up ourselves,
                # so a concurrent invocation sharing this bucket still learns
                # about it instead of finding out the hard way
                ratelimit.note_blocked(method, path, retry_after, headers=exc.headers)
                wait = ratelimit.retry_after_wait(retry_after)
                # checked against the wait, not just the current time: a
                # 429 arriving near the deadline with a long retry_after
                # must not sleep past it just because the deadline hadn't
                # technically passed yet when the check ran
                if monotonic() + wait < deadline:
                    sleep(wait)
                    continue
            raise errors.discord_http_error(
                exc.code, body_out.decode(errors="replace"), body=body_out, headers=exc.headers
            ) from exc
        except OSError:
            # a transient network blip that hit after _send() already handed
            # back a response object, e.g. the connection dropped while
            # reading the body, after the status/headers had already come
            # through. Same idempotency reasoning as _send()'s own retry
            # applies here too: only safe to resend when safe_to_retry.
            if network_retried or not safe_to_retry:
                raise
            network_retried = True
            continue


async def request_raw(method, path, payload=None, files=None, token=None, raw_body=None, reason=None, idempotent=None):
    """Make an authenticated Discord API call, retrying 429s. Returns the raw
    response body. See _request_raw_sync's docstring for idempotent."""
    return await asyncio.get_event_loop().run_in_executor(
        None, _request_raw_sync, method, path, payload, files, token, raw_body, reason, idempotent
    )


async def request(method, path, payload=None, files=None, token=None, raw_body=None, reason=None, idempotent=None):
    """Like request_raw, but parses the JSON response body (None for an empty body)."""
    data = await request_raw(
        method, path, payload, files, token=token, raw_body=raw_body, reason=reason, idempotent=idempotent
    )
    return json.loads(data) if data else None


def join_query_parts(parts):
    """Shared '?'-or-'&' joiner for a list of already-formatted key=value
    query string parts, so a future fix to how they get combined only has
    to happen in one place - query_string, messages._array_qs, and
    entitlements' tri-state exclude_ended/exclude_deleted filters all end
    up here rather than each hand-rolling their own join."""
    return ("?" + "&".join(parts)) if parts else ""


def query_parts(**params):
    """Builds the key=value parts query_string() joins. Split out so a
    caller with one extra formatting quirk (entitlements' tri-state
    booleans) can add its own part to the same list before joining once,
    instead of building two separate query strings and splicing them.

    None and False are omitted: a flag defaulting to False reads the same
    as not sending it at all, which is what every existing caller wants.
    True becomes Discord's lowercase "true". Values are URL-encoded."""
    parts = []
    for key, value in params.items():
        if value is None or value is False:
            continue
        v = "true" if value is True else value
        parts.append(f"{key}={urllib.parse.quote(str(v))}")
    return parts


def query_string(**params):
    """Shared query-string builder for GET endpoints' optional scalar
    filters (limit/before/after/..., and boolean flags like with_counts).
    Doesn't handle list values: Discord's array-style query params
    (author_id=1&author_id=2) need the repeated-key shape messages.py's
    _array_qs builds instead, and comma-joined ones (include_roles) join
    before being passed in here."""
    return join_query_parts(query_parts(**params))


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
