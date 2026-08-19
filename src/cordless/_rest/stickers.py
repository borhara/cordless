"""Sticker REST endpoints (Discord API v10)."""

from .._multipart import build_form_multipart_body
from . import _client
from ._client import UNSET
from .models import Sticker, StickerPack


async def fetch_sticker(sticker_id, *, token=None):
    data = await _client.request("GET", f"/stickers/{sticker_id}", token=token)
    return Sticker(data)


async def fetch_sticker_packs(*, token=None):
    data = await _client.request("GET", "/sticker-packs", token=token)
    assert data is not None, "GET always returns a body"
    return [StickerPack(p) for p in data["sticker_packs"]]


async def fetch_sticker_pack(pack_id, *, token=None):
    data = await _client.request("GET", f"/sticker-packs/{pack_id}", token=token)
    return StickerPack(data)


async def fetch_guild_stickers(guild_id, *, token=None):
    data = await _client.request("GET", f"/guilds/{guild_id}/stickers", token=token)
    assert data is not None, "GET always returns a body"
    return [Sticker(s) for s in data]


async def fetch_guild_sticker(guild_id, sticker_id, *, token=None):
    data = await _client.request("GET", f"/guilds/{guild_id}/stickers/{sticker_id}", token=token)
    return Sticker(data)


async def create_guild_sticker(guild_id, name, description, tags, filename, file_bytes, *, token=None):
    """Unlike every other create/edit call in this package, Discord wants a
    plain multipart form here (name/description/tags as ordinary fields, the
    file as `file`), not the payload_json + files[n] attachment convention -
    see _multipart.build_form_multipart_body."""
    raw_body = build_form_multipart_body(
        {"name": name, "description": description, "tags": tags}, "file", filename, file_bytes
    )
    data = await _client.request("POST", f"/guilds/{guild_id}/stickers", raw_body=raw_body, token=token)
    return Sticker(data)


async def edit_guild_sticker(guild_id, sticker_id, *, name=UNSET, description=UNSET, tags=UNSET, token=None):
    payload = _client.payload(name=name, description=description, tags=tags)
    data = await _client.request("PATCH", f"/guilds/{guild_id}/stickers/{sticker_id}", payload, token=token)
    return Sticker(data)


async def delete_guild_sticker(guild_id, sticker_id, *, token=None):
    await _client.request("DELETE", f"/guilds/{guild_id}/stickers/{sticker_id}", token=token)
