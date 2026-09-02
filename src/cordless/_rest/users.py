"""User REST endpoints (Discord API v10).

Only the calls a bot token can make. Group DM creation, connections, and
current-user guild member need an OAuth2 user token, so they're omitted.
"""

from typing import Any

from ..models import Channel, Guild, User
from . import _client
from ._client import UNSET


async def fetch_current_user(*, token: str | None = None) -> User:
    """The bot's own `User`."""
    data = await _client.request("GET", "/users/@me", token=token)
    return User(data)


async def fetch_user(user_id: str, *, token: str | None = None) -> User:
    """Any `User` by id; works without sharing a guild."""
    data = await _client.request("GET", f"/users/{user_id}", token=token)
    return User(data)


async def edit_current_user(
    *, username: Any = UNSET, avatar: Any = UNSET, banner: Any = UNSET, token: str | None = None
) -> User:
    """Heavily rate limited (roughly twice an hour)."""
    payload = _client.payload(username=username, avatar=avatar, banner=banner)
    data = await _client.request("PATCH", "/users/@me", payload, token=token)
    return User(data)


async def fetch_current_user_guilds(
    *,
    before: str | None = None,
    after: str | None = None,
    limit: int | None = None,
    with_counts: bool = False,
    token: str | None = None,
) -> list[Guild]:
    """A page of partial `Guild` objects. with_counts adds approximate member/presence counts."""
    params: list[str] = [
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


async def leave_guild(guild_id: str, *, token: str | None = None) -> None:
    """Irreversible without a fresh invite."""
    await _client.request("DELETE", f"/users/@me/guilds/{guild_id}", token=token)


async def create_dm(recipient_id: str, *, token: str | None = None) -> Channel:
    """Opens a DM channel with a user, or returns the existing one if
    there already is one. Sending a message doesn't need this to be
    called first, only useful when the channel id itself is needed
    ahead of time."""
    payload = _client.payload(recipient_id=recipient_id)
    data = await _client.request("POST", "/users/@me/channels", payload, token=token)
    return Channel(data)
