"""Subscription REST endpoints (Discord API v10).

Recurring premium purchases, sibling to skus.py's one-time SKU listing and
entitlements.py's one-time entitlements.
"""

from . import _client
from .models import Subscription


async def fetch_sku_subscriptions(sku_id, *, before=None, after=None, limit=None, user_id=None, token=None):
    qs = _client.query_string(before=before, after=after, limit=limit, user_id=user_id)
    data = await _client.request("GET", f"/skus/{sku_id}/subscriptions{qs}", token=token)
    assert data is not None, "GET always returns a body"
    return [Subscription(s) for s in data]


async def fetch_sku_subscription(sku_id, subscription_id, *, user_id=None, token=None):
    qs = _client.query_string(user_id=user_id)
    data = await _client.request("GET", f"/skus/{sku_id}/subscriptions/{subscription_id}{qs}", token=token)
    return Subscription(data)
