# pyright: strict
"""Sticker REST endpoints (Discord API v10)."""

from typing import Any

from .._multipart import build_form_multipart_body
from . import _client
from ._client import UNSET
from .models import Sticker, StickerPack


async def fetch_sticker(sticker_id: str, *, token: str | None = None) -> Sticker:
    """One `Sticker` by id, guild or Nitro-pack alike."""
    data = await _client.request("GET", f"/stickers/{sticker_id}", token=token)
    return Sticker(data)


async def fetch_sticker_packs(*, token: str | None = None) -> list[StickerPack]:
    """Discord's built-in Nitro sticker packs."""
    data = await _client.request_json("GET", "/sticker-packs", token=token)
    return [StickerPack(p) for p in data["sticker_packs"]]


async def fetch_sticker_pack(pack_id: str, *, token: str | None = None) -> StickerPack:
    """One `StickerPack` by id."""
    data = await _client.request("GET", f"/sticker-packs/{pack_id}", token=token)
    return StickerPack(data)


async def fetch_guild_stickers(guild_id: str, *, token: str | None = None) -> list[Sticker]:
    """Every custom `Sticker` in the guild."""
    data = await _client.request_json("GET", f"/guilds/{guild_id}/stickers", token=token)
    return [Sticker(s) for s in data]


async def fetch_guild_sticker(guild_id: str, sticker_id: str, *, token: str | None = None) -> Sticker:
    """One guild `Sticker` by id."""
    data = await _client.request("GET", f"/guilds/{guild_id}/stickers/{sticker_id}", token=token)
    return Sticker(data)


async def create_guild_sticker(
    guild_id: str, name: str, description: str, tags: str, filename: str, file_bytes: bytes, *, token: str | None = None
) -> Sticker:
    """Unlike every other create/edit call in this package, Discord wants a
    plain multipart form here (name/description/tags as ordinary fields, the
    file as `file`), not the payload_json + files[n] attachment convention -
    see _multipart.build_form_multipart_body."""
    raw_body = build_form_multipart_body(
        {"name": name, "description": description, "tags": tags}, "file", filename, file_bytes
    )
    data = await _client.request("POST", f"/guilds/{guild_id}/stickers", raw_body=raw_body, token=token)
    return Sticker(data)


async def edit_guild_sticker(
    guild_id: str,
    sticker_id: str,
    *,
    name: Any = UNSET,
    description: Any = UNSET,
    tags: Any = UNSET,
    token: str | None = None,
) -> Sticker:
    """Edits an existing guild sticker's name, description or tags. The
    image itself can't be changed after upload, delete and recreate
    instead."""
    payload = _client.payload(name=name, description=description, tags=tags)
    data = await _client.request("PATCH", f"/guilds/{guild_id}/stickers/{sticker_id}", payload, token=token)
    return Sticker(data)


async def delete_guild_sticker(guild_id: str, sticker_id: str, *, token: str | None = None) -> None:
    """Requires MANAGE_GUILD_EXPRESSIONS, or being the sticker's creator."""
    await _client.request("DELETE", f"/guilds/{guild_id}/stickers/{sticker_id}", token=token)
