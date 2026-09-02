"""Optional cross-invocation coordination for outbound Discord rate limits.

Enabled by setting `ratelimit = true` in [deploy] (cordless.toml), which
provisions a DynamoDB table and points CORDLESS_RATELIMIT_TABLE at it in the
deployed function's environment. Header state from Discord's responses is
cached locally per warm execution environment, which is enough to avoid
re-requesting a bucket already known to be exhausted. DynamoDB is only
consulted when that local state is missing (cold start) or already close to
the limit - not before every request, since most concurrent Lambda
invocations never touch the same bucket at the same time.

State is keyed by Discord's own X-RateLimit-Bucket id, not by method+path.
Discord can and does share one bucket across multiple routes (the reaction
endpoints are a documented example), so two different routes reporting the
same bucket id collapse onto the same cached state instead of being tracked
as if they had independent quota. Which bucket a route belongs to is only
known once a response reveals it, so route_key stays the fallback identity
for any route this warm container hasn't seen a response for yet.

A fresh container starts with no bucket knowledge of its own (_route_buckets
is in-memory only), so it can't compute the same bucket-keyed key another
container just published shared state under, and would otherwise never find
it. Every shared publish is therefore mirrored under the plain route key too
(see _mirror_under_route_key), so a cold container's fallback lookup, which
is exactly what it's stuck using until it learns the bucket for itself,
still finds the block a warm sibling already recorded.
"""

import email.message
import os
import random
import re
import time
from collections.abc import Mapping
from typing import Any

from . import errors

_TABLE_ENV_VAR = "CORDLESS_RATELIMIT_TABLE"
_LOW_REMAINING = 1
_MAX_WAIT = 5.0
# wait_if_needed runs before a request is even sent, inside whatever timeout
# budget the caller has, and the default main handler's is 10s (see
# _rest/_client.py's _MAX_RETRY_SECONDS comment). A confirmed block (see
# note_blocked) is real, Discord-sourced knowledge that sending right now
# gets rejected, so it's always either fully honoured or not attempted at
# all, never under-waited and sent anyway, which would just trade a
# guaranteed clear error for a maybe-avoidable 429. This is the line: below
# it, wait_if_needed sleeps the confirmed block's actual remaining time
# (never less, same as retry_after_wait); at or above it, sleeping that long
# risks the caller's own timeout killing the invocation mid-wait with no
# response ever sent, so it raises instead of blocking that long on a guess
# about how much timeout budget is left.
_CONFIRMED_MAX_WAIT = 6.0
_RETRY_JITTER_CAP = 2.0

_local: dict[str, tuple[int, float, bool]] = {}

# route_key -> bucket id, learned from X-RateLimit-Bucket as responses come in.
# In-memory only: a fresh route this warm container hasn't seen yet just falls
# back to being keyed by its own route_key until a response teaches it otherwise.
_route_buckets: dict[str, str] = {}


def enabled() -> bool:
    return bool(os.environ.get(_TABLE_ENV_VAR))


def jittered_wait(seconds: float, cap: float = _MAX_WAIT) -> float:
    """Equal jitter: wait at least half the requested time, capped at cap.

    Concurrent callers given the same `seconds` (e.g. several requests that
    all just got the same Discord retry_after) spread out across the second
    half of the window instead of all waking up at the same instant and
    colliding again.
    """
    capped = min(seconds, cap)
    return capped / 2 + random.uniform(0, capped / 2)


def retry_after_wait(retry_after: float) -> float:
    """How long to sleep before retrying a request Discord just 429'd,
    given the response's own retry_after. Unlike jittered_wait above, this
    must never sleep less than retry_after: retrying early just turns one
    429 into a stream of further ones, which is why jittered_wait's cap
    isn't reused here. It's meant for proactively avoiding a bucket that
    isn't confirmed exhausted yet, where a short cap is the right call so
    a warm container doesn't block its whole request on a guess.

    Jitter is only ever added on top of retry_after, capped so it can't
    dominate a short one, mainly to spread out concurrent callers that all
    just got the same retry_after rather than to shorten anyone's wait."""
    return retry_after + random.uniform(0, min(retry_after, _RETRY_JITTER_CAP))


def _key(method: str, path: str) -> str:
    return f"{method} {path}"


def _learn_bucket(route: str, headers: email.message.Message | Mapping[str, str] | None) -> None:
    """Record route's bucket id from a response's X-RateLimit-Bucket, if present."""
    bucket = headers.get("X-RateLimit-Bucket") if headers else None
    if bucket:
        _route_buckets[route] = bucket


# Discord's rate limit buckets aren't inclusive of the major resource a
# route acts on: two different channels (or guilds, or webhooks) can report
# the exact same X-RateLimit-Bucket id while Discord still tracks their
# quotas independently server-side. Matches the leading /channels/<id>,
# /guilds/<id>, or /webhooks/<id> segment, since that's the part of the
# path a shared bucket id must still be kept separate by.
_MAJOR_PARAM_RE = re.compile(r"^/(channels|guilds|webhooks)/[^/]+")


def _major_resource(path: str) -> str:
    match = _MAJOR_PARAM_RE.match(path)
    return match.group(0) if match else ""


def _mirror_under_route_key(key: str, route: str, blocked_until: float, confirmed: bool) -> None:
    """When key (bucket-based) differs from route (the plain fallback
    identity), also publish the exact same shared state under route.

    A container that has never itself seen a response for route has an
    empty _route_buckets entry for it and can't compute key, the same
    bucket-based key this container just published under; it can only
    ever fall back to querying by route directly (that's exactly what
    _effective_key returns when the bucket is unknown). Without this
    mirror, that fallback lookup always misses, so a cold container sends
    straight into a bucket another invocation already confirmed (or
    predicted) is exhausted, defeating the point of cross-invocation
    coordination for precisely the case (a fresh container) it matters
    most for."""
    if key != route:
        _put_shared(route, blocked_until, confirmed=confirmed)


def _effective_key(route: str, path: str) -> str:
    """route's bucket id, combined with path's major resource, if this warm
    container has learned a bucket id for route; otherwise route itself
    (which already encodes everything needed, major resource included).

    The major resource has to ride along with the bucket id: without it, a
    route for channel 123 and a route for channel 456 that happen to report
    the same bucket id would collapse onto one cached entry and each
    incorrectly throttle the other, even though Discord itself tracks their
    quotas separately."""
    bucket = _route_buckets.get(route)
    if bucket is None:
        return route
    major = _major_resource(path)
    return f"{bucket}:{major}" if major else bucket


def record_response(method: str, path: str, headers: email.message.Message | Mapping[str, str]) -> None:
    """Cache the bucket state Discord returned, for next time this route is called."""
    if not enabled():
        return
    remaining = headers.get("X-RateLimit-Remaining")
    reset_after = headers.get("X-RateLimit-Reset-After")
    if remaining is None or reset_after is None:
        return
    remaining = int(float(remaining))
    reset_at = time.time() + float(reset_after)
    route = _key(method, path)
    _learn_bucket(route, headers)
    key = _effective_key(route, path)
    # confirmed=False: this is a prediction from a still-successful response's
    # headers, not an actual rejection, so wait_if_needed treats it with more
    # caution than a block note_blocked recorded from a real 429.
    _local[key] = (remaining, reset_at, False)
    if remaining <= _LOW_REMAINING:
        # publish proactively, so a concurrent invocation can back off before
        # it ever gets a 429 itself, not just after someone else already has
        _put_shared(key, reset_at, confirmed=False)
        _mirror_under_route_key(key, route, reset_at, confirmed=False)


def wait_if_needed(method: str, path: str) -> None:
    """Block until a bucket is clear, if local or shared state says it isn't.

    Raises DiscordHTTPError(429, ...) instead of blocking, without sending
    anything, if a confirmed block's remaining time exceeds
    _CONFIRMED_MAX_WAIT (see that constant's comment for why). A merely
    predicted block (not yet confirmed by an actual 429) never raises; it
    only ever gets a short, capped, best-effort wait, since the prediction
    itself might already be stale or wrong.
    """
    if not enabled():
        return
    key = _effective_key(_key(method, path), path)
    cached = _local.get(key)
    if cached and cached[0] > _LOW_REMAINING and cached[1] > time.time():
        return  # comfortably clear locally, no need to ask anyone
    # not clear (or unknown) locally - local state is still a valid wait source on
    # its own, since DynamoDB can be unreachable/unconfigured and fails open to None
    local = (cached[1], cached[2]) if cached else None
    candidates = [c for c in (local, _shared_block(key)) if c and c[0] > time.time()]
    if not candidates:
        return
    blocked_until, confirmed = max(candidates, key=lambda c: c[0])
    remaining = blocked_until - time.time()

    if confirmed and remaining > _CONFIRMED_MAX_WAIT:
        raise errors.discord_http_error(
            429, f"cached rate limit on {key} has {remaining:.1f}s left, not attempting the request"
        )
    wait = retry_after_wait(remaining) if confirmed else jittered_wait(remaining)
    print(f"[cordless] rate limit: waiting {wait:.2f}s on {key}")
    time.sleep(wait)


def note_blocked(
    method: str, path: str, retry_after: float, headers: email.message.Message | Mapping[str, str] | None = None
) -> None:
    """Record a 429 so other concurrent invocations see the same bucket is blocked.

    headers is the 429 response's own headers, not just its parsed body: a 429
    is exactly when a shared bucket's siblings most need to learn about it, so
    this is as much a bucket-learning opportunity as record_response is.
    """
    if not enabled():
        return
    route = _key(method, path)
    _learn_bucket(route, headers)
    key = _effective_key(route, path)
    blocked_until = time.time() + retry_after
    # confirmed=True: Discord actually rejected a real request with this
    # exact retry_after, unlike record_response's merely-predicted block.
    _local[key] = (0, blocked_until, True)
    _put_shared(key, blocked_until, confirmed=True)
    _mirror_under_route_key(key, route, blocked_until, confirmed=True)


_tables: dict[str, Any] = {}
_warned_degraded = False


def _warn_degraded(action: str, exc: BaseException) -> None:
    """Print once when a DynamoDB call fails. Shared state is a best-effort
    optimisation, so a failure falls back to per-container state rather than
    raising, but staying silent hides a missing table or IAM permission for
    the whole life of the deployment."""
    global _warned_degraded
    if not _warned_degraded:
        _warned_degraded = True
        print(
            f"[cordless] ratelimit: shared state {action} failed "
            f"({type(exc).__name__}: {exc}); using per-container state only"
        )


def _table() -> Any:
    name = os.environ[_TABLE_ENV_VAR]
    table = _tables.get(name)
    if table is None:
        import boto3

        table = boto3.resource("dynamodb").Table(name)
        _tables[name] = table
    return table


def _shared_block(key: str) -> tuple[float, bool] | None:
    """(blocked_until, confirmed), or None if key has no recorded block (or
    the table is unreachable/unconfigured, see the fail-open note below)."""
    try:
        item: Any = _table().get_item(Key={"pk": key}).get("Item")
    except Exception as exc:
        _warn_degraded("read", exc)
        return None  # fail-open: a DynamoDB hiccup should never block sending
    if not item:
        return None
    # boto3's resource API deserializes DynamoDB's Number type as decimal.Decimal,
    # not float - cast here so callers can freely mix it with time.time() etc.
    return float(item["blocked_until"]), bool(item.get("confirmed", False))


def _put_shared(key: str, blocked_until: float, confirmed: bool) -> None:
    try:
        _table().put_item(
            Item={
                "pk": key,
                "blocked_until": int(blocked_until) + 1,
                "confirmed": confirmed,
                "ttl": int(blocked_until) + 60,
            }
        )
    except Exception as exc:
        _warn_degraded("write", exc)  # fail-open, same as above
