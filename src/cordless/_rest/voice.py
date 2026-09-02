"""Voice REST endpoints (Discord API v10).

List Voice Regions is the only non-guild-scoped call here.
guild.fetch_voice_regions() (guilds.py) hits the separate
/guilds/{guild.id}/regions endpoint instead.
"""

from typing import Any

from . import _client
from ._client import UNSET
from .models import VoiceRegion, VoiceState


async def fetch_voice_regions(*, token: str | None = None) -> list[VoiceRegion]:
    """Every voice region Discord offers globally. For a guild's own list use guild.fetch_voice_regions()."""
    data = await _client.request_json("GET", "/voice/regions", token=token)
    return [VoiceRegion(r) for r in data]


async def fetch_current_user_voice_state(guild_id: str, *, token: str | None = None) -> VoiceState:
    """The bot's `VoiceState` in this guild; NotFound if it isn't connected."""
    data = await _client.request("GET", f"/guilds/{guild_id}/voice-states/@me", token=token)
    return VoiceState(data)


async def fetch_user_voice_state(guild_id: str, user_id: str, *, token: str | None = None) -> VoiceState:
    """A member's `VoiceState` in this guild; NotFound if they aren't connected."""
    data = await _client.request("GET", f"/guilds/{guild_id}/voice-states/{user_id}", token=token)
    return VoiceState(data)


async def edit_current_user_voice_state(
    guild_id: str,
    *,
    channel_id: Any = UNSET,
    suppress: Any = UNSET,
    request_to_speak_timestamp: Any = UNSET,
    token: str | None = None,
) -> None:
    """The bot must already be connected to a stage channel before suppress or
    request_to_speak_timestamp will take."""
    payload = _client.payload(
        channel_id=channel_id, suppress=suppress, request_to_speak_timestamp=request_to_speak_timestamp
    )
    await _client.request("PATCH", f"/guilds/{guild_id}/voice-states/@me", payload, token=token)


async def edit_user_voice_state(
    guild_id: str, user_id: str, *, channel_id: Any = UNSET, suppress: Any = UNSET, token: str | None = None
) -> None:
    """Stage channels only. suppress=False moves the user to speaker,
    suppress=True back to the audience. Requires MUTE_MEMBERS."""
    payload = _client.payload(channel_id=channel_id, suppress=suppress)
    await _client.request("PATCH", f"/guilds/{guild_id}/voice-states/{user_id}", payload, token=token)
