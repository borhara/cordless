"""Application command endpoints for inspecting and editing commands from a
running bot (Discord API v10). For deploy-time bulk registration use
register.sync_commands().

Editing command permissions is omitted: it needs a guild-owner Bearer token,
and batch editing is disabled by Discord.
"""

from typing import Any

from . import _client
from ._client import UNSET
from .models import ApplicationCommand, GuildApplicationCommandPermissions


def _command_payload(
    name: Any,
    description: Any,
    options: Any,
    default_member_permissions: Any,
    integration_types: Any,
    contexts: Any,
    type: Any,
    nsfw: Any,
    handler: Any,
) -> dict[str, Any]:
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


async def fetch_global_commands(
    application_id: str, *, with_localizations: bool = False, token: str | None = None
) -> list[ApplicationCommand]:
    """Every global command. with_localizations adds the per-locale name/description dicts."""
    qs = "?with_localizations=true" if with_localizations else ""
    data = await _client.request_json("GET", f"/applications/{application_id}/commands{qs}", token=token)
    return [ApplicationCommand(c) for c in data]


async def create_global_command(
    application_id: str,
    name: str,
    *,
    description: Any = UNSET,
    options: Any = UNSET,
    default_member_permissions: Any = UNSET,
    integration_types: Any = UNSET,
    contexts: Any = UNSET,
    type: Any = UNSET,
    nsfw: Any = UNSET,
    handler: Any = UNSET,
    token: str | None = None,
) -> ApplicationCommand:
    """Registers a new global command. Global command changes can take up
    to an hour to propagate to every guild, register a guild command
    instead while testing to see changes straight away."""
    payload = _command_payload(
        name, description, options, default_member_permissions, integration_types, contexts, type, nsfw, handler
    )
    data = await _client.request("POST", f"/applications/{application_id}/commands", payload, token=token)
    return ApplicationCommand(data)


async def fetch_global_command(application_id: str, command_id: str, *, token: str | None = None) -> ApplicationCommand:
    """A single global `ApplicationCommand` by id."""
    data = await _client.request("GET", f"/applications/{application_id}/commands/{command_id}", token=token)
    return ApplicationCommand(data)


async def edit_global_command(
    application_id: str,
    command_id: str,
    *,
    name: Any = UNSET,
    description: Any = UNSET,
    options: Any = UNSET,
    default_member_permissions: Any = UNSET,
    integration_types: Any = UNSET,
    contexts: Any = UNSET,
    nsfw: Any = UNSET,
    handler: Any = UNSET,
    token: str | None = None,
) -> ApplicationCommand:
    """Partial update: pass only the fields to change. Global changes take up to an hour to propagate."""
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


async def delete_global_command(application_id: str, command_id: str, *, token: str | None = None) -> None:
    """Removes a global command; up to an hour to clear from every guild."""
    await _client.request("DELETE", f"/applications/{application_id}/commands/{command_id}", token=token)


async def bulk_overwrite_global_commands(
    application_id: str, commands: Any, *, token: str | None = None
) -> list[ApplicationCommand]:
    """Replaces every global command with the given list in one call.
    Commands left out of the list are deleted; ones that match an existing
    command by name and type keep their id, so any per-command state such
    as guild permission overrides survives the overwrite."""
    data = await _client.request_json("PUT", f"/applications/{application_id}/commands", commands, token=token)
    return [ApplicationCommand(c) for c in data]


async def fetch_guild_commands(
    application_id: str, guild_id: str, *, with_localizations: bool = False, token: str | None = None
) -> list[ApplicationCommand]:
    """Every command registered to one guild."""
    qs = "?with_localizations=true" if with_localizations else ""
    data = await _client.request_json(
        "GET", f"/applications/{application_id}/guilds/{guild_id}/commands{qs}", token=token
    )
    return [ApplicationCommand(c) for c in data]


async def create_guild_command(
    application_id: str,
    guild_id: str,
    name: str,
    *,
    description: Any = UNSET,
    options: Any = UNSET,
    default_member_permissions: Any = UNSET,
    type: Any = UNSET,
    nsfw: Any = UNSET,
    handler: Any = UNSET,
    token: str | None = None,
) -> ApplicationCommand:
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


async def fetch_guild_command(
    application_id: str, guild_id: str, command_id: str, *, token: str | None = None
) -> ApplicationCommand:
    """A single guild `ApplicationCommand` by id."""
    data = await _client.request(
        "GET", f"/applications/{application_id}/guilds/{guild_id}/commands/{command_id}", token=token
    )
    return ApplicationCommand(data)


async def edit_guild_command(
    application_id: str,
    guild_id: str,
    command_id: str,
    *,
    name: Any = UNSET,
    description: Any = UNSET,
    options: Any = UNSET,
    default_member_permissions: Any = UNSET,
    nsfw: Any = UNSET,
    handler: Any = UNSET,
    token: str | None = None,
) -> ApplicationCommand:
    """Partial update: pass only the fields to change."""
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


async def delete_guild_command(
    application_id: str, guild_id: str, command_id: str, *, token: str | None = None
) -> None:
    """Removes a guild command; effective immediately, unlike global commands."""
    await _client.request(
        "DELETE", f"/applications/{application_id}/guilds/{guild_id}/commands/{command_id}", token=token
    )


async def bulk_overwrite_guild_commands(
    application_id: str, guild_id: str, commands: Any, *, token: str | None = None
) -> list[ApplicationCommand]:
    """Replaces every command in the guild with the given list in one
    call, the same as bulk_overwrite_global_commands but scoped to a
    single guild."""
    data = await _client.request_json(
        "PUT", f"/applications/{application_id}/guilds/{guild_id}/commands", commands, token=token
    )
    return [ApplicationCommand(c) for c in data]


async def fetch_guild_command_permissions(
    application_id: str, guild_id: str, *, token: str | None = None
) -> list[GuildApplicationCommandPermissions]:
    """The permission overrides for every command in the guild that has any set."""
    data = await _client.request_json(
        "GET", f"/applications/{application_id}/guilds/{guild_id}/commands/permissions", token=token
    )
    return [GuildApplicationCommandPermissions(p) for p in data]


async def fetch_command_permissions(
    application_id: str, guild_id: str, command_id: str, *, token: str | None = None
) -> GuildApplicationCommandPermissions:
    """The permission overrides for one command. NotFound if none are set."""
    data = await _client.request(
        "GET",
        f"/applications/{application_id}/guilds/{guild_id}/commands/{command_id}/permissions",
        token=token,
    )
    return GuildApplicationCommandPermissions(data)
