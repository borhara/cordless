# pyright: strict
"""Guild template REST endpoints (Discord API v10).

Create Guild from Guild Template is left out for the same reason as
create_guild in guilds.py: Discord blocked bot tokens from creating guilds
in 2025.
"""

from typing import Any

from . import _client
from ._client import UNSET
from .models import GuildTemplate


async def fetch_template(code: str, *, token: str | None = None) -> GuildTemplate:
    """A `GuildTemplate` by its share code. No permission or guild membership needed."""
    data = await _client.request("GET", f"/guilds/templates/{code}", token=token)
    return GuildTemplate(data)


async def fetch_guild_templates(guild_id: str, *, token: str | None = None) -> list[GuildTemplate]:
    """Every template created from this guild. Requires MANAGE_GUILD."""
    data = await _client.request_json("GET", f"/guilds/{guild_id}/templates", token=token)
    return [GuildTemplate(t) for t in data]


async def create_guild_template(
    guild_id: str, name: str, *, description: Any = UNSET, token: str | None = None
) -> GuildTemplate:
    """A one-off snapshot of the guild, not a live mirror. Requires MANAGE_GUILD."""
    payload = _client.payload(name=name, description=description)
    data = await _client.request("POST", f"/guilds/{guild_id}/templates", payload, token=token)
    return GuildTemplate(data)


async def sync_guild_template(guild_id: str, code: str, *, token: str | None = None) -> GuildTemplate:
    """A template is a one-off snapshot; call this to re-snapshot it against
    the guild's current state."""
    data = await _client.request("PUT", f"/guilds/{guild_id}/templates/{code}", token=token)
    return GuildTemplate(data)


async def edit_guild_template(
    guild_id: str, code: str, *, name: Any = UNSET, description: Any = UNSET, token: str | None = None
) -> GuildTemplate:
    """Changes the name/description only. Use sync_guild_template to refresh
    the snapshot."""
    payload = _client.payload(name=name, description=description)
    data = await _client.request("PATCH", f"/guilds/{guild_id}/templates/{code}", payload, token=token)
    return GuildTemplate(data)


async def delete_guild_template(guild_id: str, code: str, *, token: str | None = None) -> GuildTemplate:
    """Returns the deleted `GuildTemplate`."""
    data = await _client.request("DELETE", f"/guilds/{guild_id}/templates/{code}", token=token)
    return GuildTemplate(data)
