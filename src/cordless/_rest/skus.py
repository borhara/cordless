"""SKU REST endpoints (Discord API v10)."""

from . import _client
from .models import SKU


async def fetch_skus(application_id, *, token=None):
    """Fetches every SKU (subscription tier or one-time purchase) the
    application sells."""
    data = await _client.request("GET", f"/applications/{application_id}/skus", token=token)
    assert data is not None, "GET always returns a body"
    return [SKU(s) for s in data]
