"""Subscription REST endpoints (Discord API v10).

Recurring premium purchases, sibling to skus.py's SKU listing and
entitlements.py's one-time entitlements.
"""

from . import _client
from .models import Subscription


async def fetch_sku_subscriptions(sku_id, *, before=None, after=None, limit=None, user_id=None, token=None):
    """user_id is required unless the request carries an OAuth2 token for that
    user (a bot token never does), so in practice always pass it."""
    qs = _client.query_string(before=before, after=after, limit=limit, user_id=user_id)
    data = await _client.request_json("GET", f"/skus/{sku_id}/subscriptions{qs}", token=token)
    return [Subscription(s) for s in data]


async def fetch_sku_subscription(sku_id, subscription_id, *, user_id=None, token=None):
    """One `Subscription` by id. Pass user_id, same as fetch_sku_subscriptions."""
    qs = _client.query_string(user_id=user_id)
    data = await _client.request("GET", f"/skus/{sku_id}/subscriptions/{subscription_id}{qs}", token=token)
    return Subscription(data)
