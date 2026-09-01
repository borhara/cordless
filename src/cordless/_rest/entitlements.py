# pyright: strict
"""Entitlement REST endpoints (Discord API v10)."""

from . import _client
from .models import Entitlement


async def fetch_entitlements(
    application_id: str,
    *,
    user_id: str | None = None,
    sku_ids: list[str] | None = None,
    before: str | None = None,
    after: str | None = None,
    limit: int | None = None,
    guild_id: str | None = None,
    exclude_ended: bool | None = None,
    exclude_deleted: bool | None = None,
    token: str | None = None,
) -> list[Entitlement]:
    """Fetches the application's entitlements, its record of who owns
    which SKU, optionally filtered to a user, a guild, or a set of SKU
    ids."""
    parts = _client.query_parts(
        user_id=user_id,
        sku_ids=",".join(sku_ids) if sku_ids else None,
        before=before,
        after=after,
        limit=limit,
        guild_id=guild_id,
    )
    # exclude_ended/exclude_deleted are tri-state, unlike query_parts's own
    # flag convention: None omits the filter entirely, but an explicit
    # False is sent as-is rather than treated the same as not filtering.
    if exclude_ended is not None:
        parts.append(f"exclude_ended={'true' if exclude_ended else 'false'}")
    if exclude_deleted is not None:
        parts.append(f"exclude_deleted={'true' if exclude_deleted else 'false'}")
    qs = _client.join_query_parts(parts)
    data = await _client.request_json("GET", f"/applications/{application_id}/entitlements{qs}", token=token)
    return [Entitlement(e) for e in data]


async def fetch_entitlement(application_id: str, entitlement_id: str, *, token: str | None = None) -> Entitlement:
    """One `Entitlement` by id."""
    data = await _client.request("GET", f"/applications/{application_id}/entitlements/{entitlement_id}", token=token)
    return Entitlement(data)


async def consume_entitlement(application_id: str, entitlement_id: str, *, token: str | None = None) -> None:
    """Marks a one-time-purchase consumable entitlement as used. Only
    valid for consumable SKUs, subscriptions don't need this."""
    await _client.request("POST", f"/applications/{application_id}/entitlements/{entitlement_id}/consume", token=token)


async def create_test_entitlement(
    application_id: str, sku_id: str, owner_id: str, owner_type: int, *, token: str | None = None
) -> Entitlement:
    """Grants a fake entitlement for testing, without it ever going
    through Discord's payment flow. owner_type is 1 for a guild
    subscription or 2 for a user subscription."""
    payload = _client.payload(sku_id=sku_id, owner_id=owner_id, owner_type=owner_type)
    data = await _client.request("POST", f"/applications/{application_id}/entitlements", payload, token=token)
    return Entitlement(data)


async def delete_test_entitlement(application_id: str, entitlement_id: str, *, token: str | None = None) -> None:
    """Test entitlements only; a real purchase can't be deleted this way."""
    await _client.request("DELETE", f"/applications/{application_id}/entitlements/{entitlement_id}", token=token)
