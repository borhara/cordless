"""Guild template REST endpoints (Discord API v10).

Create Guild from Guild Template is left out on purpose, same reason as
create_guild in guilds.py: Discord blocked bot tokens from creating guilds
outright in 2025, this endpoint included."""

from . import _client
from ._client import UNSET
from .models import GuildTemplate


async def fetch_template(code, *, token=None):
    """Fetches a guild template by its code."""
    data = await _client.request("GET", f"/guilds/templates/{code}", token=token)
    return GuildTemplate(data)


async def fetch_guild_templates(guild_id, *, token=None):
    """Fetches every template the guild has created."""
    data = await _client.request_json("GET", f"/guilds/{guild_id}/templates", token=token)
    return [GuildTemplate(t) for t in data]


async def create_guild_template(guild_id, name, *, description=UNSET, token=None):
    """Creates a new template from the guild's current settings, roles
    and channels."""
    payload = _client.payload(name=name, description=description)
    data = await _client.request("POST", f"/guilds/{guild_id}/templates", payload, token=token)
    return GuildTemplate(data)


async def sync_guild_template(guild_id, code, *, token=None):
    """Updates a template to match the guild's current settings. A
    template is a snapshot, it doesn't stay in sync on its own."""
    data = await _client.request("PUT", f"/guilds/{guild_id}/templates/{code}", token=token)
    return GuildTemplate(data)


async def edit_guild_template(guild_id, code, *, name=UNSET, description=UNSET, token=None):
    """Renames a template or edits its description, without touching the
    snapshot itself. Use sync_guild_template to update the snapshot."""
    payload = _client.payload(name=name, description=description)
    data = await _client.request("PATCH", f"/guilds/{guild_id}/templates/{code}", payload, token=token)
    return GuildTemplate(data)


async def delete_guild_template(guild_id, code, *, token=None):
    """Deletes a template."""
    data = await _client.request("DELETE", f"/guilds/{guild_id}/templates/{code}", token=token)
    return GuildTemplate(data)
