"""Soundboard REST endpoints (Discord API v10)."""

from . import _client
from ._client import UNSET
from .models import SoundboardSound


async def send_soundboard_sound(channel_id, sound_id, *, source_guild_id=UNSET, token=None):
    """Bot must be connected to the voice channel. Requires SPEAK and
    USE_SOUNDBOARD, plus USE_EXTERNAL_SOUNDS to play a sound owned by
    another guild via source_guild_id."""
    payload = _client.payload(sound_id=sound_id, source_guild_id=source_guild_id)
    await _client.request("POST", f"/channels/{channel_id}/send-soundboard-sound", payload, token=token)


async def fetch_default_soundboard_sounds(*, token=None):
    data = await _client.request("GET", "/soundboard-default-sounds", token=token)
    assert data is not None, "GET always returns a body"
    return [SoundboardSound(s) for s in data]


async def fetch_guild_soundboard_sounds(guild_id, *, token=None):
    data = await _client.request("GET", f"/guilds/{guild_id}/soundboard-sounds", token=token)
    assert data is not None, "GET always returns a body"
    return [SoundboardSound(s) for s in data["items"]]


async def fetch_guild_soundboard_sound(guild_id, sound_id, *, token=None):
    data = await _client.request("GET", f"/guilds/{guild_id}/soundboard-sounds/{sound_id}", token=token)
    return SoundboardSound(data)


async def create_guild_soundboard_sound(
    guild_id, name, sound, *, volume=UNSET, emoji_id=UNSET, emoji_name=UNSET, reason=None, token=None
):
    """sound is a base64 data URI, same convention as create_guild_emoji's
    image."""
    payload = _client.payload(name=name, sound=sound, volume=volume, emoji_id=emoji_id, emoji_name=emoji_name)
    data = await _client.request("POST", f"/guilds/{guild_id}/soundboard-sounds", payload, reason=reason, token=token)
    return SoundboardSound(data)


async def edit_guild_soundboard_sound(
    guild_id, sound_id, *, name=UNSET, volume=UNSET, emoji_id=UNSET, emoji_name=UNSET, reason=None, token=None
):
    payload = _client.payload(name=name, volume=volume, emoji_id=emoji_id, emoji_name=emoji_name)
    data = await _client.request(
        "PATCH", f"/guilds/{guild_id}/soundboard-sounds/{sound_id}", payload, reason=reason, token=token
    )
    return SoundboardSound(data)


async def delete_guild_soundboard_sound(guild_id, sound_id, *, reason=None, token=None):
    await _client.request("DELETE", f"/guilds/{guild_id}/soundboard-sounds/{sound_id}", reason=reason, token=token)
