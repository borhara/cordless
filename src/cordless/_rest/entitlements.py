"""Entitlement REST endpoints (Discord API v10)."""

from . import _client
from .models import Entitlement


def _bool_qs(name, value):
    if value is None:
        return None
    return f"{name}={'true' if value else 'false'}"


async def fetch_entitlements(
    application_id,
    *,
    user_id=None,
    sku_ids=None,
    before=None,
    after=None,
    limit=None,
    guild_id=None,
    exclude_ended=None,
    exclude_deleted=None,
    token=None,
):
    params = [
        p
        for p in (
            f"user_id={user_id}" if user_id else None,
            f"sku_ids={','.join(sku_ids)}" if sku_ids else None,
            f"before={before}" if before else None,
            f"after={after}" if after else None,
            f"limit={limit}" if limit else None,
            f"guild_id={guild_id}" if guild_id else None,
            _bool_qs("exclude_ended", exclude_ended),
            _bool_qs("exclude_deleted", exclude_deleted),
        )
        if p
    ]
    qs = ("?" + "&".join(params)) if params else ""
    data = await _client.request("GET", f"/applications/{application_id}/entitlements{qs}", token=token)
    assert data is not None, "GET always returns a body"
    return [Entitlement(e) for e in data]


async def fetch_entitlement(application_id, entitlement_id, *, token=None):
    data = await _client.request("GET", f"/applications/{application_id}/entitlements/{entitlement_id}", token=token)
    return Entitlement(data)


async def consume_entitlement(application_id, entitlement_id, *, token=None):
    await _client.request("POST", f"/applications/{application_id}/entitlements/{entitlement_id}/consume", token=token)


async def create_test_entitlement(application_id, sku_id, owner_id, owner_type, *, token=None):
    payload = _client.payload(sku_id=sku_id, owner_id=owner_id, owner_type=owner_type)
    data = await _client.request("POST", f"/applications/{application_id}/entitlements", payload, token=token)
    return Entitlement(data)


async def delete_test_entitlement(application_id, entitlement_id, *, token=None):
    await _client.request("DELETE", f"/applications/{application_id}/entitlements/{entitlement_id}", token=token)
