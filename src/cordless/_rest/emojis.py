"""Guild and application emoji REST endpoints (Discord API v10).

Application emojis aren't scoped to a guild, so unlike everywhere else in
the REST layer there's no object to hang them off, they only exist as the
flat bot.<verb>_application_emoji() surface, keyed by an explicit
application_id.
"""

from typing import Any

from .._payload import _with_guild_id
from . import _client
from ._client import UNSET
from .models import Emoji


def _with_application_id(data: dict[str, Any], application_id: str) -> dict[str, Any]:
    # data always comes from a body-returning GET/POST/PATCH here, so unlike
    # _with_guild_id there's no None case to guard.
    return {**data, "application_id": application_id}


async def fetch_guild_emojis(guild_id: str, *, token: str | None = None) -> list[Emoji]:
    """Every custom `Emoji` in the guild."""
    data = await _client.request_json("GET", f"/guilds/{guild_id}/emojis", token=token)
    return [Emoji(_with_guild_id(e, guild_id)) for e in data]


async def fetch_guild_emoji(guild_id: str, emoji_id: str, *, token: str | None = None) -> Emoji:
    """One guild `Emoji` by id."""
    data = await _client.request("GET", f"/guilds/{guild_id}/emojis/{emoji_id}", token=token)
    return Emoji(_with_guild_id(data, guild_id))


async def create_guild_emoji(
    guild_id: str, name: str, image: str, *, roles: Any = UNSET, token: str | None = None
) -> Emoji:
    """Uploads a new custom emoji. image is a data URI. roles, if given,
    restricts the emoji to members with at least one of those roles."""
    payload = _client.payload(name=name, image=image, roles=roles)
    data = await _client.request("POST", f"/guilds/{guild_id}/emojis", payload, token=token)
    return Emoji(_with_guild_id(data, guild_id))


async def edit_guild_emoji(
    guild_id: str, emoji_id: str, *, name: Any = UNSET, roles: Any = UNSET, token: str | None = None
) -> Emoji:
    """Renames an emoji or changes which roles can use it. The image
    itself can't be changed after upload, delete and recreate instead."""
    payload = _client.payload(name=name, roles=roles)
    data = await _client.request("PATCH", f"/guilds/{guild_id}/emojis/{emoji_id}", payload, token=token)
    return Emoji(_with_guild_id(data, guild_id))


async def delete_guild_emoji(guild_id: str, emoji_id: str, *, token: str | None = None) -> None:
    """Requires MANAGE_GUILD_EXPRESSIONS, or being the emoji's creator."""
    await _client.request("DELETE", f"/guilds/{guild_id}/emojis/{emoji_id}", token=token)


async def fetch_application_emojis(application_id: str, *, token: str | None = None) -> list[Emoji]:
    """Fetches every emoji owned by the application, usable in messages
    from any guild the bot can see."""
    data = await _client.request_json("GET", f"/applications/{application_id}/emojis", token=token)
    return [Emoji(_with_application_id(e, application_id)) for e in data["items"]]


async def fetch_application_emoji(application_id: str, emoji_id: str, *, token: str | None = None) -> Emoji:
    """One application `Emoji` by id."""
    data = await _client.request("GET", f"/applications/{application_id}/emojis/{emoji_id}", token=token)
    return Emoji(_with_application_id(data, application_id))


async def create_application_emoji(application_id: str, name: str, image: str, *, token: str | None = None) -> Emoji:
    """Uploads a new application emoji. image is a data URI. Unlike a
    guild emoji it isn't tied to any one server and doesn't count against
    a guild's emoji slots."""
    payload = {"name": name, "image": image}
    data = await _client.request("POST", f"/applications/{application_id}/emojis", payload, token=token)
    return Emoji(_with_application_id(data, application_id))


async def edit_application_emoji(
    application_id: str, emoji_id: str, *, name: Any = UNSET, token: str | None = None
) -> Emoji:
    """Application emojis carry no role restriction, so the name is all that can change."""
    payload = _client.payload(name=name)
    data = await _client.request("PATCH", f"/applications/{application_id}/emojis/{emoji_id}", payload, token=token)
    return Emoji(_with_application_id(data, application_id))


async def delete_application_emoji(application_id: str, emoji_id: str, *, token: str | None = None) -> None:
    """Frees the emoji's name for reuse by the app."""
    await _client.request("DELETE", f"/applications/{application_id}/emojis/{emoji_id}", token=token)
