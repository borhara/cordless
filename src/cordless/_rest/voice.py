"""Voice REST endpoints (Discord API v10).

List Voice Regions is the one endpoint here that isn't guild scoped -
guild.fetch_voice_regions() (guilds.py) hits /guilds/{guild.id}/regions
instead, a separate, guild-specific endpoint Discord happens to keep under
the same Voice category in its docs.
"""

from . import _client
from ._client import UNSET
from .models import VoiceRegion, VoiceState


async def fetch_voice_regions(*, token=None):
    """Fetches every voice region Discord offers, not scoped to any one
    guild."""
    data = await _client.request_json("GET", "/voice/regions", token=token)
    return [VoiceRegion(r) for r in data]


async def fetch_current_user_voice_state(guild_id, *, token=None):
    """Fetches the bot's own voice state in the guild."""
    data = await _client.request("GET", f"/guilds/{guild_id}/voice-states/@me", token=token)
    return VoiceState(data)


async def fetch_user_voice_state(guild_id, user_id, *, token=None):
    """Fetches a user's voice state in the guild."""
    data = await _client.request("GET", f"/guilds/{guild_id}/voice-states/{user_id}", token=token)
    return VoiceState(data)


async def edit_current_user_voice_state(
    guild_id, *, channel_id=UNSET, suppress=UNSET, request_to_speak_timestamp=UNSET, token=None
):
    """channel_id must already be set (i.e. the bot is connected to a Stage
    channel) before this can change suppress/request_to_speak_timestamp."""
    payload = _client.payload(
        channel_id=channel_id, suppress=suppress, request_to_speak_timestamp=request_to_speak_timestamp
    )
    await _client.request("PATCH", f"/guilds/{guild_id}/voice-states/@me", payload, token=token)


async def edit_user_voice_state(guild_id, user_id, *, channel_id=UNSET, suppress=UNSET, token=None):
    """channel_id must already be set to a Stage channel; suppress=False
    invites/moves the user to speaker, suppress=True moves them back to
    the audience."""
    payload = _client.payload(channel_id=channel_id, suppress=suppress)
    await _client.request("PATCH", f"/guilds/{guild_id}/voice-states/{user_id}", payload, token=token)
