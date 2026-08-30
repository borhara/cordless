"""Application command REST endpoints (Discord API v10).

For bulk deploy-time registration, see `register.sync_commands()` (used by
`Cordless.sync_commands()`) instead - it is a separate, synchronous tool
built for that one job. This module is for inspecting/editing commands from
a running bot.

Editing and batch-editing command permissions are both left out: editing
requires a Bearer token authorised by the guild owner, which this bot-token-
only client can't send, and batch editing has been disabled outright on
Discord's side (see the "Batch Edit Application Command Permissions" notice
in Discord's docs).
"""

from . import _client
from ._client import UNSET
from .models import ApplicationCommand, GuildApplicationCommandPermissions


def _command_payload(
    name, description, options, default_member_permissions, integration_types, contexts, type, nsfw, handler
):
    return _client.payload(
        name=name,
        description=description,
        options=options,
        default_member_permissions=default_member_permissions,
        integration_types=integration_types,
        contexts=contexts,
        type=type,
        nsfw=nsfw,
        handler=handler,
    )


async def fetch_global_commands(application_id, *, with_localizations=False, token=None):
    """Fetches every global command registered for the application."""
    qs = "?with_localizations=true" if with_localizations else ""
    data = await _client.request("GET", f"/applications/{application_id}/commands{qs}", token=token)
    assert data is not None, "GET always returns a body"
    return [ApplicationCommand(c) for c in data]


async def create_global_command(
    application_id,
    name,
    *,
    description=UNSET,
    options=UNSET,
    default_member_permissions=UNSET,
    integration_types=UNSET,
    contexts=UNSET,
    type=UNSET,
    nsfw=UNSET,
    handler=UNSET,
    token=None,
):
    """Registers a new global command. Global command changes can take up
    to an hour to propagate to every guild, register a guild command
    instead while testing to see changes straight away."""
    payload = _command_payload(
        name, description, options, default_member_permissions, integration_types, contexts, type, nsfw, handler
    )
    data = await _client.request("POST", f"/applications/{application_id}/commands", payload, token=token)
    return ApplicationCommand(data)


async def fetch_global_command(application_id, command_id, *, token=None):
    """Fetches a single global command by id."""
    data = await _client.request("GET", f"/applications/{application_id}/commands/{command_id}", token=token)
    return ApplicationCommand(data)


async def edit_global_command(
    application_id,
    command_id,
    *,
    name=UNSET,
    description=UNSET,
    options=UNSET,
    default_member_permissions=UNSET,
    integration_types=UNSET,
    contexts=UNSET,
    nsfw=UNSET,
    handler=UNSET,
    token=None,
):
    """Edits an existing global command. Only the fields passed are
    changed, everything else keeps its current value."""
    payload = _client.payload(
        name=name,
        description=description,
        options=options,
        default_member_permissions=default_member_permissions,
        integration_types=integration_types,
        contexts=contexts,
        nsfw=nsfw,
        handler=handler,
    )
    data = await _client.request("PATCH", f"/applications/{application_id}/commands/{command_id}", payload, token=token)
    return ApplicationCommand(data)


async def delete_global_command(application_id, command_id, *, token=None):
    """Deletes a global command."""
    await _client.request("DELETE", f"/applications/{application_id}/commands/{command_id}", token=token)


async def bulk_overwrite_global_commands(application_id, commands, *, token=None):
    """Replaces every global command with the given list in one call.
    Commands left out of the list are deleted; ones that match an existing
    command by name and type keep their id, so any per-command state such
    as guild permission overrides survives the overwrite."""
    data = await _client.request("PUT", f"/applications/{application_id}/commands", commands, token=token)
    assert data is not None, "PUT always returns a body"
    return [ApplicationCommand(c) for c in data]


async def fetch_guild_commands(application_id, guild_id, *, with_localizations=False, token=None):
    """Fetches every command registered for the application in a specific
    guild."""
    qs = "?with_localizations=true" if with_localizations else ""
    data = await _client.request("GET", f"/applications/{application_id}/guilds/{guild_id}/commands{qs}", token=token)
    assert data is not None, "GET always returns a body"
    return [ApplicationCommand(c) for c in data]


async def create_guild_command(
    application_id,
    guild_id,
    name,
    *,
    description=UNSET,
    options=UNSET,
    default_member_permissions=UNSET,
    type=UNSET,
    nsfw=UNSET,
    handler=UNSET,
    token=None,
):
    """Registers a new command scoped to a single guild. Unlike a global
    command, it appears in that guild immediately, which makes guild
    commands the better choice while iterating on a command's shape."""
    payload = _client.payload(
        name=name,
        description=description,
        options=options,
        default_member_permissions=default_member_permissions,
        type=type,
        nsfw=nsfw,
        handler=handler,
    )
    data = await _client.request(
        "POST", f"/applications/{application_id}/guilds/{guild_id}/commands", payload, token=token
    )
    return ApplicationCommand(data)


async def fetch_guild_command(application_id, guild_id, command_id, *, token=None):
    """Fetches a single guild command by id."""
    data = await _client.request(
        "GET", f"/applications/{application_id}/guilds/{guild_id}/commands/{command_id}", token=token
    )
    return ApplicationCommand(data)


async def edit_guild_command(
    application_id,
    guild_id,
    command_id,
    *,
    name=UNSET,
    description=UNSET,
    options=UNSET,
    default_member_permissions=UNSET,
    nsfw=UNSET,
    handler=UNSET,
    token=None,
):
    """Edits an existing guild command. Only the fields passed are
    changed, everything else keeps its current value."""
    payload = _client.payload(
        name=name,
        description=description,
        options=options,
        default_member_permissions=default_member_permissions,
        nsfw=nsfw,
        handler=handler,
    )
    data = await _client.request(
        "PATCH", f"/applications/{application_id}/guilds/{guild_id}/commands/{command_id}", payload, token=token
    )
    return ApplicationCommand(data)


async def delete_guild_command(application_id, guild_id, command_id, *, token=None):
    """Deletes a guild command."""
    await _client.request(
        "DELETE", f"/applications/{application_id}/guilds/{guild_id}/commands/{command_id}", token=token
    )


async def bulk_overwrite_guild_commands(application_id, guild_id, commands, *, token=None):
    """Replaces every command in the guild with the given list in one
    call, the same as bulk_overwrite_global_commands but scoped to a
    single guild."""
    data = await _client.request(
        "PUT", f"/applications/{application_id}/guilds/{guild_id}/commands", commands, token=token
    )
    assert data is not None, "PUT always returns a body"
    return [ApplicationCommand(c) for c in data]


async def fetch_guild_command_permissions(application_id, guild_id, *, token=None):
    """Fetches the permission overrides for every command in the guild
    that has any set."""
    data = await _client.request(
        "GET", f"/applications/{application_id}/guilds/{guild_id}/commands/permissions", token=token
    )
    assert data is not None, "GET always returns a body"
    return [GuildApplicationCommandPermissions(p) for p in data]


async def fetch_command_permissions(application_id, guild_id, command_id, *, token=None):
    """Fetches the permission overrides for a single command in the
    guild."""
    data = await _client.request(
        "GET",
        f"/applications/{application_id}/guilds/{guild_id}/commands/{command_id}/permissions",
        token=token,
    )
    return GuildApplicationCommandPermissions(data)
