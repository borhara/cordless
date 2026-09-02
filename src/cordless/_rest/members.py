"""Guild member and role REST endpoints (Discord API v10)."""

from typing import Any

from .._payload import _with_guild_id
from ..models import Member, Role
from . import _client
from ._client import UNSET


async def fetch_guild_member(guild_id: str, user_id: str, *, token: str | None = None) -> Member:
    """One `Member`; NotFound if the user isn't in the guild."""
    data = await _client.request("GET", f"/guilds/{guild_id}/members/{user_id}", token=token)
    return Member(_with_guild_id(data, guild_id))


async def fetch_guild_members(
    guild_id: str, *, limit: int | None = None, after: str | None = None, token: str | None = None
) -> list[Member]:
    """Fetches a page of the guild's members, ordered by user id. Requires
    the Server Members intent."""
    qs = _client.query_string(limit=limit, after=after)
    data = await _client.request_json("GET", f"/guilds/{guild_id}/members{qs}", token=token)
    return [Member(_with_guild_id(m, guild_id)) for m in data]


async def search_guild_members(
    guild_id: str, query: str, *, limit: int | None = None, token: str | None = None
) -> list[Member]:
    """Fetches guild members whose username or nickname starts with
    query. Unlike fetch_guild_members, this doesn't need the Server
    Members intent."""
    qs = _client.query_string(query=query, limit=limit)
    data = await _client.request_json("GET", f"/guilds/{guild_id}/members/search{qs}", token=token)
    return [Member(_with_guild_id(m, guild_id)) for m in data]


async def add_guild_member(
    guild_id: str,
    user_id: str,
    access_token: str,
    *,
    nick: Any = UNSET,
    roles: Any = UNSET,
    mute: Any = UNSET,
    deaf: Any = UNSET,
    token: str | None = None,
) -> Member | None:
    """Returns the added Member, or None if the user was already a member
    (Discord returns 204 with no body in that case)."""
    payload = _client.payload(access_token=access_token, nick=nick, roles=roles, mute=mute, deaf=deaf)
    data = await _client.request("PUT", f"/guilds/{guild_id}/members/{user_id}", payload, token=token)
    return Member(_with_guild_id(data, guild_id)) if data else None


async def edit_guild_member(
    guild_id: str,
    user_id: str,
    *,
    nick: Any = UNSET,
    roles: Any = UNSET,
    mute: Any = UNSET,
    deaf: Any = UNSET,
    channel_id: Any = UNSET,
    communication_disabled_until: Any = UNSET,
    flags: Any = UNSET,
    reason: str | None = None,
    token: str | None = None,
) -> Member:
    """nick, channel_id and communication_disabled_until can all be cleared
    by passing None explicitly."""
    payload = _client.payload(
        nick=nick,
        roles=roles,
        mute=mute,
        deaf=deaf,
        channel_id=channel_id,
        communication_disabled_until=communication_disabled_until,
        flags=flags,
    )
    data = await _client.request("PATCH", f"/guilds/{guild_id}/members/{user_id}", payload, token=token, reason=reason)
    return Member(_with_guild_id(data, guild_id))


async def edit_current_member(
    guild_id: str,
    *,
    nick: Any = UNSET,
    banner: Any = UNSET,
    avatar: Any = UNSET,
    bio: Any = UNSET,
    token: str | None = None,
) -> Member:
    """Edits the bot's own guild profile: nickname, per-guild banner and
    avatar, and bio."""
    payload = _client.payload(nick=nick, banner=banner, avatar=avatar, bio=bio)
    data = await _client.request("PATCH", f"/guilds/{guild_id}/members/@me", payload, token=token)
    return Member(_with_guild_id(data, guild_id))


async def add_guild_member_role(
    guild_id: str, user_id: str, role_id: str, *, reason: str | None = None, token: str | None = None
) -> None:
    """Requires MANAGE_ROLES and a higher role than the one being granted."""
    await _client.request("PUT", f"/guilds/{guild_id}/members/{user_id}/roles/{role_id}", token=token, reason=reason)


async def remove_guild_member_role(
    guild_id: str, user_id: str, role_id: str, *, reason: str | None = None, token: str | None = None
) -> None:
    """Requires MANAGE_ROLES."""
    await _client.request("DELETE", f"/guilds/{guild_id}/members/{user_id}/roles/{role_id}", token=token, reason=reason)


async def remove_guild_member(
    guild_id: str, user_id: str, *, reason: str | None = None, token: str | None = None
) -> None:
    """Requires KICK_MEMBERS. The member can rejoin with a new invite."""
    await _client.request("DELETE", f"/guilds/{guild_id}/members/{user_id}", token=token, reason=reason)


async def fetch_guild_roles(guild_id: str, *, token: str | None = None) -> list[Role]:
    """Every `Role` in the guild, including @everyone."""
    data = await _client.request_json("GET", f"/guilds/{guild_id}/roles", token=token)
    return [Role(_with_guild_id(r, guild_id)) for r in data]


async def fetch_guild_role(guild_id: str, role_id: str, *, token: str | None = None) -> Role:
    """One `Role` by id."""
    data = await _client.request("GET", f"/guilds/{guild_id}/roles/{role_id}", token=token)
    return Role(_with_guild_id(data, guild_id))


async def fetch_guild_role_member_counts(guild_id: str, *, token: str | None = None) -> Any:
    """Maps role id to member count. Doesn't include @everyone."""
    data = await _client.request_json("GET", f"/guilds/{guild_id}/roles/member-counts", token=token)
    return data


async def create_guild_role(
    guild_id: str,
    *,
    name: Any = UNSET,
    permissions: Any = UNSET,
    color: Any = UNSET,
    colors: Any = UNSET,
    hoist: Any = UNSET,
    icon: Any = UNSET,
    unicode_emoji: Any = UNSET,
    mentionable: Any = UNSET,
    reason: str | None = None,
    token: str | None = None,
) -> Role:
    """Creates a new role. Its position starts at the bottom of the
    hierarchy, below the bot's own highest role, use
    edit_guild_role_positions to move it."""
    payload = _client.payload(
        name=name,
        permissions=permissions,
        color=color,
        colors=colors,
        hoist=hoist,
        icon=icon,
        unicode_emoji=unicode_emoji,
        mentionable=mentionable,
    )
    data = await _client.request("POST", f"/guilds/{guild_id}/roles", payload, token=token, reason=reason)
    return Role(_with_guild_id(data, guild_id))


async def edit_guild_role_positions(
    guild_id: str, positions: Any, *, reason: str | None = None, token: str | None = None
) -> list[Role]:
    """Reorders roles in the guild. positions is a list of
    {"id": role_id, "position": int} dicts; roles left out keep their
    current position."""
    data = await _client.request_json("PATCH", f"/guilds/{guild_id}/roles", positions, token=token, reason=reason)
    return [Role(_with_guild_id(r, guild_id)) for r in data]


async def edit_guild_role(
    guild_id: str,
    role_id: str,
    *,
    name: Any = UNSET,
    permissions: Any = UNSET,
    color: Any = UNSET,
    colors: Any = UNSET,
    hoist: Any = UNSET,
    icon: Any = UNSET,
    unicode_emoji: Any = UNSET,
    mentionable: Any = UNSET,
    reason: str | None = None,
    token: str | None = None,
) -> Role:
    """Partial update: pass only the fields to change."""
    payload = _client.payload(
        name=name,
        permissions=permissions,
        color=color,
        colors=colors,
        hoist=hoist,
        icon=icon,
        unicode_emoji=unicode_emoji,
        mentionable=mentionable,
    )
    data = await _client.request("PATCH", f"/guilds/{guild_id}/roles/{role_id}", payload, token=token, reason=reason)
    return Role(_with_guild_id(data, guild_id))


async def delete_guild_role(
    guild_id: str, role_id: str, *, reason: str | None = None, token: str | None = None
) -> None:
    """Requires MANAGE_ROLES. Every member loses the role."""
    await _client.request("DELETE", f"/guilds/{guild_id}/roles/{role_id}", token=token, reason=reason)
