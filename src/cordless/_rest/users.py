"""User REST endpoints (Discord API v10).

Only the endpoints a bot token can actually call. Create Group DM, Get
Current User Connections, and the application role connection endpoints all
require an OAuth2 user access token with a scope a bot token doesn't carry -
this client only ever sends `Authorization: Bot <token>`, so those would
just 401 - and are left out rather than shipped as REST calls that can never
succeed.
"""

from ..context import _with_guild_id
from ..models import Channel, Guild, Member, User
from . import _client
from ._client import UNSET


async def fetch_current_user(*, token=None):
    data = await _client.request("GET", "/users/@me", token=token)
    return User(data)


async def fetch_user(user_id, *, token=None):
    data = await _client.request("GET", f"/users/{user_id}", token=token)
    return User(data)


async def edit_current_user(*, username=UNSET, avatar=UNSET, banner=UNSET, token=None):
    payload = _client.payload(username=username, avatar=avatar, banner=banner)
    data = await _client.request("PATCH", "/users/@me", payload, token=token)
    return User(data)


async def fetch_current_user_guilds(*, before=None, after=None, limit=None, with_counts=False, token=None):
    params = [
        p
        for p in (
            f"before={before}" if before else None,
            f"after={after}" if after else None,
            f"limit={limit}" if limit else None,
            "with_counts=true" if with_counts else None,
        )
        if p
    ]
    qs = ("?" + "&".join(params)) if params else ""
    data = await _client.request("GET", f"/users/@me/guilds{qs}", token=token)
    assert data is not None, "GET always returns a body"
    return [Guild(g) for g in data]


async def fetch_current_user_guild_member(guild_id, *, token=None):
    data = await _client.request("GET", f"/users/@me/guilds/{guild_id}/member", token=token)
    return Member(_with_guild_id(data, guild_id))


async def leave_guild(guild_id, *, token=None):
    await _client.request("DELETE", f"/users/@me/guilds/{guild_id}", token=token)


async def create_dm(recipient_id, *, token=None):
    payload = _client.payload(recipient_id=recipient_id)
    data = await _client.request("POST", "/users/@me/channels", payload, token=token)
    return Channel(data)
