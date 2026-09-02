"""Soundboard REST endpoints (Discord API v10)."""

from typing import Any

from . import _client
from ._client import UNSET
from .models import SoundboardSound


async def send_soundboard_sound(
    channel_id: str, sound_id: str, *, source_guild_id: Any = UNSET, token: str | None = None
) -> None:
    """Bot must be connected to the voice channel. Requires SPEAK and
    USE_SOUNDBOARD, plus USE_EXTERNAL_SOUNDS to play a sound owned by
    another guild via source_guild_id."""
    payload = _client.payload(sound_id=sound_id, source_guild_id=source_guild_id)
    await _client.request("POST", f"/channels/{channel_id}/send-soundboard-sound", payload, token=token)


async def fetch_default_soundboard_sounds(*, token: str | None = None) -> list[SoundboardSound]:
    """Fetches the soundboard sounds Discord provides for free, available
    to every guild."""
    data = await _client.request_json("GET", "/soundboard-default-sounds", token=token)
    return [SoundboardSound(s) for s in data]


async def fetch_guild_soundboard_sounds(guild_id: str, *, token: str | None = None) -> list[SoundboardSound]:
    """Fetches every custom soundboard sound uploaded to the guild."""
    data = await _client.request_json("GET", f"/guilds/{guild_id}/soundboard-sounds", token=token)
    return [SoundboardSound(s) for s in data["items"]]


async def fetch_guild_soundboard_sound(guild_id: str, sound_id: str, *, token: str | None = None) -> SoundboardSound:
    """One guild `SoundboardSound` by id."""
    data = await _client.request("GET", f"/guilds/{guild_id}/soundboard-sounds/{sound_id}", token=token)
    return SoundboardSound(data)


async def create_guild_soundboard_sound(
    guild_id: str,
    name: str,
    sound: str,
    *,
    volume: Any = UNSET,
    emoji_id: Any = UNSET,
    emoji_name: Any = UNSET,
    reason: str | None = None,
    token: str | None = None,
) -> SoundboardSound:
    """sound is a base64 data URI, same convention as create_guild_emoji's
    image."""
    payload = _client.payload(name=name, sound=sound, volume=volume, emoji_id=emoji_id, emoji_name=emoji_name)
    data = await _client.request("POST", f"/guilds/{guild_id}/soundboard-sounds", payload, reason=reason, token=token)
    return SoundboardSound(data)


async def edit_guild_soundboard_sound(
    guild_id: str,
    sound_id: str,
    *,
    name: Any = UNSET,
    volume: Any = UNSET,
    emoji_id: Any = UNSET,
    emoji_name: Any = UNSET,
    reason: str | None = None,
    token: str | None = None,
) -> SoundboardSound:
    """Edits an existing guild soundboard sound. The sound itself can't
    be changed after upload, delete and recreate instead."""
    payload = _client.payload(name=name, volume=volume, emoji_id=emoji_id, emoji_name=emoji_name)
    data = await _client.request(
        "PATCH", f"/guilds/{guild_id}/soundboard-sounds/{sound_id}", payload, reason=reason, token=token
    )
    return SoundboardSound(data)


async def delete_guild_soundboard_sound(
    guild_id: str, sound_id: str, *, reason: str | None = None, token: str | None = None
) -> None:
    """Requires MANAGE_GUILD_EXPRESSIONS, or being the sound's creator."""
    await _client.request("DELETE", f"/guilds/{guild_id}/soundboard-sounds/{sound_id}", reason=reason, token=token)
