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
    payload = _command_payload(
        name, description, options, default_member_permissions, integration_types, contexts, type, nsfw, handler
    )
    data = await _client.request("POST", f"/applications/{application_id}/commands", payload, token=token)
    return ApplicationCommand(data)


async def fetch_global_command(application_id, command_id, *, token=None):
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
    await _client.request("DELETE", f"/applications/{application_id}/commands/{command_id}", token=token)


async def bulk_overwrite_global_commands(application_id, commands, *, token=None):
    data = await _client.request("PUT", f"/applications/{application_id}/commands", commands, token=token)
    assert data is not None, "PUT always returns a body"
    return [ApplicationCommand(c) for c in data]


async def fetch_guild_commands(application_id, guild_id, *, with_localizations=False, token=None):
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
    await _client.request(
        "DELETE", f"/applications/{application_id}/guilds/{guild_id}/commands/{command_id}", token=token
    )


async def bulk_overwrite_guild_commands(application_id, guild_id, commands, *, token=None):
    data = await _client.request(
        "PUT", f"/applications/{application_id}/guilds/{guild_id}/commands", commands, token=token
    )
    assert data is not None, "PUT always returns a body"
    return [ApplicationCommand(c) for c in data]


async def fetch_guild_command_permissions(application_id, guild_id, *, token=None):
    data = await _client.request(
        "GET", f"/applications/{application_id}/guilds/{guild_id}/commands/permissions", token=token
    )
    assert data is not None, "GET always returns a body"
    return [GuildApplicationCommandPermissions(p) for p in data]


async def fetch_command_permissions(application_id, guild_id, command_id, *, token=None):
    data = await _client.request(
        "GET",
        f"/applications/{application_id}/guilds/{guild_id}/commands/{command_id}/permissions",
        token=token,
    )
    return GuildApplicationCommandPermissions(data)
