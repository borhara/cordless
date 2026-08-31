"""Guild member and role REST endpoints (Discord API v10)."""

from .._payload import _with_guild_id
from ..models import Member, Role
from . import _client
from ._client import UNSET


async def fetch_guild_member(guild_id, user_id, *, token=None):
    """Fetches a single guild member by user id."""
    data = await _client.request("GET", f"/guilds/{guild_id}/members/{user_id}", token=token)
    return Member(_with_guild_id(data, guild_id))


async def fetch_guild_members(guild_id, *, limit=None, after=None, token=None):
    """Fetches a page of the guild's members, ordered by user id. Requires
    the Server Members intent."""
    qs = _client.query_string(limit=limit, after=after)
    data = await _client.request_json("GET", f"/guilds/{guild_id}/members{qs}", token=token)
    return [Member(_with_guild_id(m, guild_id)) for m in data]


async def search_guild_members(guild_id, query, *, limit=None, token=None):
    """Fetches guild members whose username or nickname starts with
    query. Unlike fetch_guild_members, this doesn't need the Server
    Members intent."""
    qs = _client.query_string(query=query, limit=limit)
    data = await _client.request_json("GET", f"/guilds/{guild_id}/members/search{qs}", token=token)
    return [Member(_with_guild_id(m, guild_id)) for m in data]


async def add_guild_member(
    guild_id, user_id, access_token, *, nick=UNSET, roles=UNSET, mute=UNSET, deaf=UNSET, token=None
):
    """Returns the added Member, or None if the user was already a member
    (Discord returns 204 with no body in that case)."""
    payload = _client.payload(access_token=access_token, nick=nick, roles=roles, mute=mute, deaf=deaf)
    data = await _client.request("PUT", f"/guilds/{guild_id}/members/{user_id}", payload, token=token)
    return Member(_with_guild_id(data, guild_id)) if data else None


async def edit_guild_member(
    guild_id,
    user_id,
    *,
    nick=UNSET,
    roles=UNSET,
    mute=UNSET,
    deaf=UNSET,
    channel_id=UNSET,
    communication_disabled_until=UNSET,
    flags=UNSET,
    reason=None,
    token=None,
):
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


async def edit_current_member(guild_id, *, nick=UNSET, banner=UNSET, avatar=UNSET, bio=UNSET, token=None):
    """Edits the bot's own guild profile: nickname, per-guild banner and
    avatar, and bio."""
    payload = _client.payload(nick=nick, banner=banner, avatar=avatar, bio=bio)
    data = await _client.request("PATCH", f"/guilds/{guild_id}/members/@me", payload, token=token)
    return Member(_with_guild_id(data, guild_id))


async def add_guild_member_role(guild_id, user_id, role_id, *, reason=None, token=None):
    """Gives a member a role."""
    await _client.request("PUT", f"/guilds/{guild_id}/members/{user_id}/roles/{role_id}", token=token, reason=reason)


async def remove_guild_member_role(guild_id, user_id, role_id, *, reason=None, token=None):
    """Takes a role away from a member."""
    await _client.request("DELETE", f"/guilds/{guild_id}/members/{user_id}/roles/{role_id}", token=token, reason=reason)


async def remove_guild_member(guild_id, user_id, *, reason=None, token=None):
    """Kicks a member."""
    await _client.request("DELETE", f"/guilds/{guild_id}/members/{user_id}", token=token, reason=reason)


async def fetch_guild_roles(guild_id, *, token=None):
    """Fetches every role in the guild."""
    data = await _client.request_json("GET", f"/guilds/{guild_id}/roles", token=token)
    return [Role(_with_guild_id(r, guild_id)) for r in data]


async def fetch_guild_role(guild_id, role_id, *, token=None):
    """Fetches a single role by id."""
    data = await _client.request("GET", f"/guilds/{guild_id}/roles/{role_id}", token=token)
    return Role(_with_guild_id(data, guild_id))


async def fetch_guild_role_member_counts(guild_id, *, token=None):
    """Maps role id to member count. Doesn't include @everyone."""
    data = await _client.request_json("GET", f"/guilds/{guild_id}/roles/member-counts", token=token)
    return data


async def create_guild_role(
    guild_id,
    *,
    name=UNSET,
    permissions=UNSET,
    color=UNSET,
    colors=UNSET,
    hoist=UNSET,
    icon=UNSET,
    unicode_emoji=UNSET,
    mentionable=UNSET,
    reason=None,
    token=None,
):
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


async def edit_guild_role_positions(guild_id, positions, *, reason=None, token=None):
    """Reorders roles in the guild. positions is a list of
    {"id": role_id, "position": int} dicts; roles left out keep their
    current position."""
    data = await _client.request_json("PATCH", f"/guilds/{guild_id}/roles", positions, token=token, reason=reason)
    return [Role(_with_guild_id(r, guild_id)) for r in data]


async def edit_guild_role(
    guild_id,
    role_id,
    *,
    name=UNSET,
    permissions=UNSET,
    color=UNSET,
    colors=UNSET,
    hoist=UNSET,
    icon=UNSET,
    unicode_emoji=UNSET,
    mentionable=UNSET,
    reason=None,
    token=None,
):
    """Edits an existing role. Only the fields passed are changed."""
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


async def delete_guild_role(guild_id, role_id, *, reason=None, token=None):
    """Deletes a role, removing it from every member who has it."""
    await _client.request("DELETE", f"/guilds/{guild_id}/roles/{role_id}", token=token, reason=reason)
