"""Guild template REST endpoints (Discord API v10)."""

from . import _client
from ._client import UNSET
from .models import GuildTemplate


async def fetch_template(code, *, token=None):
    data = await _client.request("GET", f"/guilds/templates/{code}", token=token)
    return GuildTemplate(data)


async def fetch_guild_templates(guild_id, *, token=None):
    data = await _client.request("GET", f"/guilds/{guild_id}/templates", token=token)
    assert data is not None, "GET always returns a body"
    return [GuildTemplate(t) for t in data]


async def create_guild_template(guild_id, name, *, description=UNSET, token=None):
    payload = _client.payload(name=name, description=description)
    data = await _client.request("POST", f"/guilds/{guild_id}/templates", payload, token=token)
    return GuildTemplate(data)


async def sync_guild_template(guild_id, code, *, token=None):
    data = await _client.request("PUT", f"/guilds/{guild_id}/templates/{code}", token=token)
    return GuildTemplate(data)


async def edit_guild_template(guild_id, code, *, name=UNSET, description=UNSET, token=None):
    payload = _client.payload(name=name, description=description)
    data = await _client.request("PATCH", f"/guilds/{guild_id}/templates/{code}", payload, token=token)
    return GuildTemplate(data)


async def delete_guild_template(guild_id, code, *, token=None):
    data = await _client.request("DELETE", f"/guilds/{guild_id}/templates/{code}", token=token)
    return GuildTemplate(data)
