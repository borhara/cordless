"""SKU REST endpoints (Discord API v10)."""

from . import _client
from .models import SKU


async def fetch_skus(application_id, *, token=None):
    """Every SKU (subscription tier or one-time purchase) the app sells."""
    data = await _client.request_json("GET", f"/applications/{application_id}/skus", token=token)
    return [SKU(s) for s in data]
