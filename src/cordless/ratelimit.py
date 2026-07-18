"""Optional cross-invocation coordination for outbound Discord rate limits.

Enabled by setting `ratelimit = true` in [deploy] (cordless.toml), which
provisions a DynamoDB table and points CORDLESS_RATELIMIT_TABLE at it in the
deployed function's environment. Header state from Discord's responses is
cached locally per warm execution environment, which is enough to avoid
re-requesting a bucket already known to be exhausted. DynamoDB is only
consulted when that local state is missing (cold start) or already close to
the limit - not before every request, since most concurrent Lambda
invocations never touch the same bucket at the same time.
"""

import os
import random
import time

_TABLE_ENV_VAR = "CORDLESS_RATELIMIT_TABLE"
_LOW_REMAINING = 1
_MAX_WAIT = 5.0

_local = {}


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


def _key(method, path):
    return f"{method} {path}"


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
    key = _key(method, path)
    _local[key] = (remaining, reset_at)
    if remaining <= _LOW_REMAINING:
        # publish proactively, so a concurrent invocation can back off before
        # it ever gets a 429 itself, not just after someone else already has
        _put_shared(key, reset_at)


def wait_if_needed(method, path):
    """Block until a bucket is clear, if local or shared state says it isn't."""
    if not enabled():
        return
    key = _key(method, path)
    cached = _local.get(key)
    if cached and cached[0] > _LOW_REMAINING and cached[1] > time.time():
        return  # comfortably clear locally, no need to ask anyone
    # not clear (or unknown) locally - local state is still a valid wait source on
    # its own, since DynamoDB can be unreachable/unconfigured and fails open to None
    candidates = [t for t in (cached[1] if cached else None, _shared_block(key)) if t]
    blocked_until = max(candidates, default=None)
    if blocked_until and blocked_until > time.time():
        time.sleep(jittered_wait(blocked_until - time.time()))


def note_blocked(method, path, retry_after):
    """Record a 429 so other concurrent invocations see the same bucket is blocked."""
    if not enabled():
        return
    key = _key(method, path)
    blocked_until = time.time() + retry_after
    _local[key] = (0, blocked_until)
    _put_shared(key, blocked_until)


_tables = {}


def _table():
    name = os.environ[_TABLE_ENV_VAR]
    table = _tables.get(name)
    if table is None:
        import boto3

        table = boto3.resource("dynamodb").Table(name)
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
