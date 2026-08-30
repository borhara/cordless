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
"""

import os
import random
import re
import time

_TABLE_ENV_VAR = "CORDLESS_RATELIMIT_TABLE"
_LOW_REMAINING = 1
_MAX_WAIT = 5.0
_RETRY_JITTER_CAP = 2.0

_local = {}

# route_key -> bucket id, learned from X-RateLimit-Bucket as responses come in.
# In-memory only: a fresh route this warm container hasn't seen yet just falls
# back to being keyed by its own route_key until a response teaches it otherwise.
_route_buckets = {}


def enabled():
    return bool(os.environ.get(_TABLE_ENV_VAR))


def jittered_wait(seconds):
    """Equal jitter: wait at least half the requested time, capped at _MAX_WAIT.

    Concurrent callers given the same `seconds` (e.g. several requests that
    all just got the same Discord retry_after) spread out across the second
    half of the window instead of all waking up at the same instant and
    colliding again.
    """
    capped = min(seconds, _MAX_WAIT)
    return capped / 2 + random.uniform(0, capped / 2)


def retry_after_wait(retry_after):
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


def _key(method, path):
    return f"{method} {path}"


def _learn_bucket(route, headers):
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


def _major_resource(path):
    match = _MAJOR_PARAM_RE.match(path)
    return match.group(0) if match else ""


def _effective_key(route, path):
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


def record_response(method, path, headers):
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
    _local[key] = (remaining, reset_at)
    if remaining <= _LOW_REMAINING:
        # publish proactively, so a concurrent invocation can back off before
        # it ever gets a 429 itself, not just after someone else already has
        _put_shared(key, reset_at)


def wait_if_needed(method, path):
    """Block until a bucket is clear, if local or shared state says it isn't."""
    if not enabled():
        return
    key = _effective_key(_key(method, path), path)
    cached = _local.get(key)
    if cached and cached[0] > _LOW_REMAINING and cached[1] > time.time():
        return  # comfortably clear locally, no need to ask anyone
    # not clear (or unknown) locally - local state is still a valid wait source on
    # its own, since DynamoDB can be unreachable/unconfigured and fails open to None
    candidates = [t for t in (cached[1] if cached else None, _shared_block(key)) if t]
    blocked_until = max(candidates, default=None)
    if blocked_until and blocked_until > time.time():
        wait = jittered_wait(blocked_until - time.time())
        print(f"[cordless] rate limit: waiting {wait:.2f}s on {key}")
        time.sleep(wait)


def note_blocked(method, path, retry_after, headers=None):
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
    _local[key] = (0, blocked_until)
    _put_shared(key, blocked_until)


_tables = {}


def _table():
    name = os.environ[_TABLE_ENV_VAR]
    table = _tables.get(name)
    if table is None:
        import boto3

        # boto3.resource()'s return type is generated dynamically, so pyright
        # can't see .Table on it without the mypy-boto3-dynamodb stubs this
        # project doesn't depend on
        table = boto3.resource("dynamodb").Table(name)  # pyright: ignore[reportAttributeAccessIssue]
        _tables[name] = table
    return table


def _shared_block(key):
    try:
        item = _table().get_item(Key={"pk": key}).get("Item")
    except Exception:
        return None  # fail-open: a DynamoDB hiccup should never block sending
    # boto3's resource API deserializes DynamoDB's Number type as decimal.Decimal,
    # not float - cast here so callers can freely mix it with time.time() etc.
    return float(item["blocked_until"]) if item else None


def _put_shared(key, blocked_until):
    try:
        _table().put_item(Item={"pk": key, "blocked_until": int(blocked_until) + 1, "ttl": int(blocked_until) + 60})
    except Exception:
        pass  # fail-open, same as above
