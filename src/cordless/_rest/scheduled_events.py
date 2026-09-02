"""Guild scheduled event REST endpoints (Discord API v10)."""

from typing import Any

from .._payload import _with_guild_id
from . import _client
from ._client import UNSET
from .models import GuildScheduledEvent, GuildScheduledEventUser


async def fetch_guild_scheduled_events(
    guild_id: str, *, with_user_count: bool = False, token: str | None = None
) -> list[GuildScheduledEvent]:
    """Fetches every scheduled event in the guild, including ones that
    have already ended."""
    qs = _client.query_string(with_user_count=with_user_count)
    data = await _client.request_json("GET", f"/guilds/{guild_id}/scheduled-events{qs}", token=token)
    return [GuildScheduledEvent(e) for e in data]


async def create_guild_scheduled_event(
    guild_id: str,
    name: str,
    privacy_level: int,
    scheduled_start_time: str,
    entity_type: int,
    *,
    channel_id: Any = UNSET,
    entity_metadata: Any = UNSET,
    scheduled_end_time: Any = UNSET,
    description: Any = UNSET,
    image: Any = UNSET,
    recurrence_rule: Any = UNSET,
    token: str | None = None,
) -> GuildScheduledEvent:
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


async def fetch_guild_scheduled_event(
    guild_id: str, event_id: str, *, with_user_count: bool = False, token: str | None = None
) -> GuildScheduledEvent:
    """One `GuildScheduledEvent` by id."""
    qs = _client.query_string(with_user_count=with_user_count)
    data = await _client.request("GET", f"/guilds/{guild_id}/scheduled-events/{event_id}{qs}", token=token)
    return GuildScheduledEvent(data)


async def edit_guild_scheduled_event(
    guild_id: str,
    event_id: str,
    *,
    channel_id: Any = UNSET,
    entity_metadata: Any = UNSET,
    name: Any = UNSET,
    privacy_level: Any = UNSET,
    scheduled_start_time: Any = UNSET,
    scheduled_end_time: Any = UNSET,
    description: Any = UNSET,
    entity_type: Any = UNSET,
    status: Any = UNSET,
    image: Any = UNSET,
    recurrence_rule: Any = UNSET,
    token: str | None = None,
) -> GuildScheduledEvent:
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


async def delete_guild_scheduled_event(guild_id: str, event_id: str, *, token: str | None = None) -> None:
    """Requires MANAGE_EVENTS."""
    await _client.request("DELETE", f"/guilds/{guild_id}/scheduled-events/{event_id}", token=token)


async def fetch_guild_scheduled_event_users(
    guild_id: str,
    event_id: str,
    *,
    limit: int | None = None,
    with_member: bool = False,
    before: str | None = None,
    after: str | None = None,
    token: str | None = None,
) -> list[GuildScheduledEventUser]:
    """The `GuildScheduledEventUser` list, paginated by user id."""
    qs = _client.query_string(limit=limit, with_member=with_member, before=before, after=after)
    data = await _client.request_json("GET", f"/guilds/{guild_id}/scheduled-events/{event_id}/users{qs}", token=token)
    return [GuildScheduledEventUser(_with_guild_id(u, guild_id)) for u in data]
