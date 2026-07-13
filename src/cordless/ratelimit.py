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
import time

_TABLE_ENV_VAR = "CORDLESS_RATELIMIT_TABLE"
_LOW_REMAINING = 1
_MAX_WAIT = 5.0

_local = {}


def enabled():
    return bool(os.environ.get(_TABLE_ENV_VAR))


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
    _local[_key(method, path)] = (int(float(remaining)), time.time() + float(reset_after))


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
        time.sleep(min(blocked_until - time.time(), _MAX_WAIT))


def note_blocked(method, path, retry_after):
    """Record a 429 so other concurrent invocations see the same bucket is blocked."""
    if not enabled():
        return
    key = _key(method, path)
    blocked_until = time.time() + retry_after
    _local[key] = (0, blocked_until)
    _put_shared(key, blocked_until)


def _table():
    import boto3

    return boto3.resource("dynamodb").Table(os.environ[_TABLE_ENV_VAR])


def _shared_block(key):
    try:
        item = _table().get_item(Key={"pk": key}).get("Item")
    except Exception:
        return None  # fail-open: a DynamoDB hiccup should never block sending
    return item["blocked_until"] if item else None


def _put_shared(key, blocked_until):
    try:
        _table().put_item(Item={"pk": key, "blocked_until": int(blocked_until) + 1, "ttl": int(blocked_until) + 60})
    except Exception:
        pass  # fail-open, same as above
