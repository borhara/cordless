"""Guild scheduled event REST endpoints (Discord API v10)."""

from ..context import _with_guild_id
from . import _client
from ._client import UNSET
from .models import GuildScheduledEvent, GuildScheduledEventException, GuildScheduledEventUser


async def fetch_guild_scheduled_events(guild_id, *, with_user_count=False, token=None):
    qs = _client.query_string(with_user_count=with_user_count)
    data = await _client.request("GET", f"/guilds/{guild_id}/scheduled-events{qs}", token=token)
    assert data is not None, "GET always returns a body"
    return [GuildScheduledEvent(e) for e in data]


async def create_guild_scheduled_event(
    guild_id,
    name,
    privacy_level,
    scheduled_start_time,
    entity_type,
    *,
    channel_id=UNSET,
    entity_metadata=UNSET,
    scheduled_end_time=UNSET,
    description=UNSET,
    image=UNSET,
    recurrence_rule=UNSET,
    token=None,
):
    """channel_id and entity_metadata are optional for entity_type EXTERNAL,
    scheduled_end_time is required for it."""
    payload = _client.payload(
        channel_id=channel_id,
        entity_metadata=entity_metadata,
        name=name,
        privacy_level=privacy_level,
        scheduled_start_time=scheduled_start_time,
        scheduled_end_time=scheduled_end_time,
        description=description,
        entity_type=entity_type,
        image=image,
        recurrence_rule=recurrence_rule,
    )
    data = await _client.request("POST", f"/guilds/{guild_id}/scheduled-events", payload, token=token)
    return GuildScheduledEvent(data)


async def fetch_guild_scheduled_event(guild_id, event_id, *, with_user_count=False, token=None):
    qs = _client.query_string(with_user_count=with_user_count)
    data = await _client.request("GET", f"/guilds/{guild_id}/scheduled-events/{event_id}{qs}", token=token)
    return GuildScheduledEvent(data)


async def edit_guild_scheduled_event(
    guild_id,
    event_id,
    *,
    channel_id=UNSET,
    entity_metadata=UNSET,
    name=UNSET,
    privacy_level=UNSET,
    scheduled_start_time=UNSET,
    scheduled_end_time=UNSET,
    description=UNSET,
    entity_type=UNSET,
    status=UNSET,
    image=UNSET,
    recurrence_rule=UNSET,
    token=None,
):
    """Set status to start/end the event. Switching entity_type to EXTERNAL
    requires channel_id=None, entity_metadata with a location, and
    scheduled_end_time all in the same call."""
    payload = _client.payload(
        channel_id=channel_id,
        entity_metadata=entity_metadata,
        name=name,
        privacy_level=privacy_level,
        scheduled_start_time=scheduled_start_time,
        scheduled_end_time=scheduled_end_time,
        description=description,
        entity_type=entity_type,
        status=status,
        image=image,
        recurrence_rule=recurrence_rule,
    )
    data = await _client.request("PATCH", f"/guilds/{guild_id}/scheduled-events/{event_id}", payload, token=token)
    return GuildScheduledEvent(data)


async def delete_guild_scheduled_event(guild_id, event_id, *, token=None):
    await _client.request("DELETE", f"/guilds/{guild_id}/scheduled-events/{event_id}", token=token)


async def fetch_guild_scheduled_event_users(
    guild_id, event_id, *, limit=None, with_member=False, before=None, after=None, token=None
):
    qs = _client.query_string(limit=limit, with_member=with_member, before=before, after=after)
    data = await _client.request("GET", f"/guilds/{guild_id}/scheduled-events/{event_id}/users{qs}", token=token)
    assert data is not None, "GET always returns a body"
    return [GuildScheduledEventUser(_with_guild_id(u, guild_id)) for u in data]


async def fetch_guild_scheduled_event_user_counts(guild_id, event_id, *, exception_ids=None, token=None):
    """Recurring events only. exception_ids narrows the per-exception counts
    returned alongside the event's own total."""
    parts = []
    for exception_id in exception_ids or []:
        parts.append(f"guild_scheduled_event_exception_ids={exception_id}")
    qs = _client.join_query_parts(parts)
    return await _client.request("GET", f"/guilds/{guild_id}/scheduled-events/{event_id}/users/counts{qs}", token=token)


async def create_guild_scheduled_event_exception(
    guild_id,
    event_id,
    original_scheduled_start_time,
    *,
    scheduled_start_time=UNSET,
    scheduled_end_time=UNSET,
    is_canceled=UNSET,
    token=None,
):
    """Recurring events only: override or cancel one occurrence."""
    payload = _client.payload(
        original_scheduled_start_time=original_scheduled_start_time,
        scheduled_start_time=scheduled_start_time,
        scheduled_end_time=scheduled_end_time,
        is_canceled=is_canceled,
    )
    data = await _client.request(
        "POST", f"/guilds/{guild_id}/scheduled-events/{event_id}/exceptions", payload, token=token
    )
    return GuildScheduledEventException(_with_guild_id(data, guild_id))


async def edit_guild_scheduled_event_exception(
    guild_id,
    event_id,
    exception_id,
    *,
    scheduled_start_time=UNSET,
    scheduled_end_time=UNSET,
    is_canceled=UNSET,
    token=None,
):
    payload = _client.payload(
        scheduled_start_time=scheduled_start_time, scheduled_end_time=scheduled_end_time, is_canceled=is_canceled
    )
    data = await _client.request(
        "PATCH", f"/guilds/{guild_id}/scheduled-events/{event_id}/exceptions/{exception_id}", payload, token=token
    )
    return GuildScheduledEventException(_with_guild_id(data, guild_id))


async def delete_guild_scheduled_event_exception(guild_id, event_id, exception_id, *, token=None):
    await _client.request(
        "DELETE", f"/guilds/{guild_id}/scheduled-events/{event_id}/exceptions/{exception_id}", token=token
    )


async def fetch_guild_scheduled_event_exception_users(
    guild_id, event_id, exception_id, *, with_member=False, limit=None, before=None, after=None, token=None
):
    qs = _client.query_string(with_member=with_member, limit=limit, before=before, after=after)
    data = await _client.request(
        "GET", f"/guilds/{guild_id}/scheduled-events/{event_id}/{exception_id}/users{qs}", token=token
    )
    return [GuildScheduledEventUser(_with_guild_id(u, guild_id)) for u in data or []]
