"""User REST endpoints (Discord API v10).

Only the endpoints a bot token can actually call. Create Group DM, Get
Current User Connections, Get Current User Guild Member, and the
application role connection endpoints all require an OAuth2 user access
token with a scope a bot token doesn't carry - this client only ever sends
`Authorization: Bot <token>`, so those would just 401/403 - and are left out
rather than shipped as REST calls that can never succeed.
"""

from ..models import Channel, Guild, User
from . import _client
from ._client import UNSET


async def fetch_current_user(*, token=None):
    """Fetches the bot's own user object."""
    data = await _client.request("GET", "/users/@me", token=token)
    return User(data)


async def fetch_user(user_id, *, token=None):
    """Fetches a user by id."""
    data = await _client.request("GET", f"/users/{user_id}", token=token)
    return User(data)


async def edit_current_user(*, username=UNSET, avatar=UNSET, banner=UNSET, token=None):
    """Edits the bot's own username, avatar or banner."""
    payload = _client.payload(username=username, avatar=avatar, banner=banner)
    data = await _client.request("PATCH", "/users/@me", payload, token=token)
    return User(data)


async def fetch_current_user_guilds(*, before=None, after=None, limit=None, with_counts=False, token=None):
    """Fetches a page of the guilds the bot is in."""
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
    data = await _client.request_json("GET", f"/users/@me/guilds{qs}", token=token)
    return [Guild(g) for g in data]


async def leave_guild(guild_id, *, token=None):
    """Makes the bot leave a guild."""
    await _client.request("DELETE", f"/users/@me/guilds/{guild_id}", token=token)


async def create_dm(recipient_id, *, token=None):
    """Opens a DM channel with a user, or returns the existing one if
    there already is one. Sending a message doesn't need this to be
    called first, only useful when the channel id itself is needed
    ahead of time."""
    payload = _client.payload(recipient_id=recipient_id)
    data = await _client.request("POST", "/users/@me/channels", payload, token=token)
    return Channel(data)
