"""Guild and application emoji REST endpoints (Discord API v10).

Application emojis aren't scoped to a guild, so unlike everywhere else in
the REST layer there's no object to hang them off, they only exist as the
flat bot.<verb>_application_emoji() surface, keyed by an explicit
application_id.
"""

from ..context import _with_guild_id
from . import _client
from ._client import UNSET
from .models import Emoji


def _with_application_id(data, application_id):
    """Every call site gets data from a GET/POST/PATCH that always returns a
    body, unlike _with_guild_id's ctx.member (None in DMs), so no None guard
    is needed here."""
    return {**data, "application_id": application_id}


async def fetch_guild_emojis(guild_id, *, token=None):
    data = await _client.request("GET", f"/guilds/{guild_id}/emojis", token=token)
    assert data is not None, "GET always returns a body"
    return [Emoji(_with_guild_id(e, guild_id)) for e in data]


async def fetch_guild_emoji(guild_id, emoji_id, *, token=None):
    data = await _client.request("GET", f"/guilds/{guild_id}/emojis/{emoji_id}", token=token)
    return Emoji(_with_guild_id(data, guild_id))


async def create_guild_emoji(guild_id, name, image, *, roles=UNSET, token=None):
    payload = _client.payload(name=name, image=image, roles=roles)
    data = await _client.request("POST", f"/guilds/{guild_id}/emojis", payload, token=token)
    return Emoji(_with_guild_id(data, guild_id))


async def edit_guild_emoji(guild_id, emoji_id, *, name=UNSET, roles=UNSET, token=None):
    payload = _client.payload(name=name, roles=roles)
    data = await _client.request("PATCH", f"/guilds/{guild_id}/emojis/{emoji_id}", payload, token=token)
    return Emoji(_with_guild_id(data, guild_id))


async def delete_guild_emoji(guild_id, emoji_id, *, token=None):
    await _client.request("DELETE", f"/guilds/{guild_id}/emojis/{emoji_id}", token=token)


async def fetch_application_emojis(application_id, *, token=None):
    data = await _client.request("GET", f"/applications/{application_id}/emojis", token=token)
    assert data is not None, "GET always returns a body"
    return [Emoji(_with_application_id(e, application_id)) for e in data["items"]]


async def fetch_application_emoji(application_id, emoji_id, *, token=None):
    data = await _client.request("GET", f"/applications/{application_id}/emojis/{emoji_id}", token=token)
    return Emoji(_with_application_id(data, application_id))


async def create_application_emoji(application_id, name, image, *, token=None):
    payload = {"name": name, "image": image}
    data = await _client.request("POST", f"/applications/{application_id}/emojis", payload, token=token)
    return Emoji(_with_application_id(data, application_id))


async def edit_application_emoji(application_id, emoji_id, *, name=UNSET, token=None):
    payload = _client.payload(name=name)
    data = await _client.request("PATCH", f"/applications/{application_id}/emojis/{emoji_id}", payload, token=token)
    return Emoji(_with_application_id(data, application_id))


async def delete_application_emoji(application_id, emoji_id, *, token=None):
    await _client.request("DELETE", f"/applications/{application_id}/emojis/{emoji_id}", token=token)
