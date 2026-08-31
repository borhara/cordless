"""Stage instance REST endpoints (Discord API v10)."""

from . import _client
from ._client import UNSET
from .models import StageInstance


async def create_stage_instance(
    channel_id,
    topic,
    *,
    privacy_level=UNSET,
    send_start_notification=UNSET,
    guild_scheduled_event_id=UNSET,
    token=None,
):
    """Takes a stage channel live. The bot must be a speaker or moderator on it."""
    payload = _client.payload(
        channel_id=channel_id,
        topic=topic,
        privacy_level=privacy_level,
        send_start_notification=send_start_notification,
        guild_scheduled_event_id=guild_scheduled_event_id,
    )
    data = await _client.request("POST", "/stage-instances", payload, token=token)
    return StageInstance(data)


async def fetch_stage_instance(channel_id, *, token=None):
    """Raises NotFound if the stage isn't live."""
    data = await _client.request("GET", f"/stage-instances/{channel_id}", token=token)
    return StageInstance(data)


async def edit_stage_instance(channel_id, *, topic=UNSET, privacy_level=UNSET, token=None):
    """Change a live stage's topic or privacy level. Requires stage moderator permissions."""
    payload = _client.payload(topic=topic, privacy_level=privacy_level)
    data = await _client.request("PATCH", f"/stage-instances/{channel_id}", payload, token=token)
    return StageInstance(data)


async def delete_stage_instance(channel_id, *, token=None):
    """Ends the live stage."""
    await _client.request("DELETE", f"/stage-instances/{channel_id}", token=token)
