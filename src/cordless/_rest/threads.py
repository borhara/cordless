# pyright: strict
"""Thread REST endpoints (Discord API v10)."""

from typing import Any

from .._multipart import build_multipart_body
from . import _client
from .models import Thread, ThreadMember


async def start_thread_from_message(
    channel_id: str, message_id: str, name: str, *, auto_archive_duration: int | None = None, token: str | None = None
) -> Thread:
    """Starts a public thread from an existing message. The thread shares
    the message's id, and the message's author is added to it
    automatically."""
    payload: dict[str, Any] = {"name": name}
    if auto_archive_duration is not None:
        payload["auto_archive_duration"] = auto_archive_duration
    data = await _client.request("POST", f"/channels/{channel_id}/messages/{message_id}/threads", payload, token=token)
    return Thread(data)


async def start_thread_without_message(
    channel_id: str, name: str, *, thread_type: int = 11, invitable: bool | None = None, token: str | None = None
) -> Thread:
    """Starts a thread with no starter message. thread_type defaults to
    11 (a public thread); pass 12 for a private one. invitable only
    applies to private threads, and controls whether non-moderators can
    add other members."""
    payload: dict[str, Any] = {"name": name, "type": thread_type}
    if invitable is not None:
        payload["invitable"] = invitable
    data = await _client.request("POST", f"/channels/{channel_id}/threads", payload, token=token)
    return Thread(data)


async def start_thread_from_forum(
    channel_id: str,
    name: str,
    *,
    message: str,
    applied_tags: list[str] | None = None,
    auto_archive_duration: int | None = None,
    rate_limit_per_user: int | None = None,
    token: str | None = None,
    files: list[tuple[str, bytes]] | None = None,
) -> Thread:
    """Starts a new post in a forum or media channel. The post itself is
    both the thread and its first message, built from the message
    argument the same way create_message builds one."""
    forum_message: dict[str, Any] = {"content": message}
    payload: dict[str, Any] = {"name": name, "message": forum_message}

    if applied_tags:
        payload["applied_tags"] = applied_tags

    if auto_archive_duration:
        payload["auto_archive_duration"] = auto_archive_duration

    # 0 is a meaningful explicit value (no slowmode), unlike the fields
    # above - only leaving it unset should fall back to the forum channel's
    # own default_thread_rate_limit_per_user.
    if rate_limit_per_user is not None:
        payload["rate_limit_per_user"] = rate_limit_per_user

    if files:
        # this endpoint carries the message params (attachments included)
        # under "message", not at the top level, so _client's generic
        # _attach_files can't place them, build the multipart body here.
        forum_message["attachments"] = [{"id": i, "filename": filename} for i, (filename, _) in enumerate(files)]
        raw_body = build_multipart_body(payload, files)
        data = await _client.request("POST", f"/channels/{channel_id}/threads", raw_body=raw_body, token=token)
    else:
        data = await _client.request("POST", f"/channels/{channel_id}/threads", payload, token=token)
    return Thread(data)


async def join_thread(channel_id: str, *, token: str | None = None) -> None:
    """No-op if the bot is already in the thread."""
    await _client.request("PUT", f"/channels/{channel_id}/thread-members/@me", token=token)


async def leave_thread(channel_id: str, *, token: str | None = None) -> None:
    """The bot stops receiving the thread's messages."""
    await _client.request("DELETE", f"/channels/{channel_id}/thread-members/@me", token=token)


async def add_thread_member(channel_id: str, user_id: str, *, token: str | None = None) -> None:
    """Needs the bot to be in the thread, and SEND_MESSAGES_IN_THREADS for a private one."""
    await _client.request("PUT", f"/channels/{channel_id}/thread-members/{user_id}", token=token)


async def remove_thread_member(channel_id: str, user_id: str, *, token: str | None = None) -> None:
    """Requires MANAGE_THREADS, or thread ownership for a private thread."""
    await _client.request("DELETE", f"/channels/{channel_id}/thread-members/{user_id}", token=token)


async def fetch_thread_member(
    channel_id: str, user_id: str, *, with_member: bool = False, token: str | None = None
) -> ThreadMember:
    """Fetches a single thread member. with_member also attaches that
    user's guild member object."""
    qs = "?with_member=true" if with_member else ""
    data = await _client.request_json("GET", f"/channels/{channel_id}/thread-members/{user_id}{qs}", token=token)
    return ThreadMember(data)


async def fetch_thread_members(
    channel_id: str,
    *,
    with_member: bool = False,
    after: str | None = None,
    limit: int | None = None,
    token: str | None = None,
) -> list[ThreadMember]:
    """after/limit only take effect when with_member=True - Discord ignores
    them otherwise and always returns every member in one page."""
    qs = _client.query_string(with_member=with_member, after=after, limit=limit)
    data = await _client.request_json("GET", f"/channels/{channel_id}/thread-members{qs}", token=token)
    return [ThreadMember(m) for m in data]


async def fetch_public_archived_threads(
    channel_id: str, *, before: str | None = None, limit: int | None = None, token: str | None = None
) -> list[Thread]:
    """Fetches a page of the channel's archived public threads, newest
    archived first."""
    qs = _client.pagination_qs(before=before, limit=limit)
    data = await _client.request_json("GET", f"/channels/{channel_id}/threads/archived/public{qs}", token=token)
    return [Thread(t) for t in data["threads"]]


async def fetch_private_archived_threads(
    channel_id: str, *, before: str | None = None, limit: int | None = None, token: str | None = None
) -> list[Thread]:
    """Fetches a page of the channel's archived private threads. Requires
    MANAGE_THREADS, unless fetching only threads the bot has joined via
    fetch_joined_private_archived_threads instead."""
    qs = _client.pagination_qs(before=before, limit=limit)
    data = await _client.request_json("GET", f"/channels/{channel_id}/threads/archived/private{qs}", token=token)
    return [Thread(t) for t in data["threads"]]


async def fetch_joined_private_archived_threads(
    channel_id: str, *, before: str | None = None, limit: int | None = None, token: str | None = None
) -> list[Thread]:
    """Fetches a page of the channel's archived private threads the bot
    has joined. Unlike fetch_private_archived_threads, this doesn't need
    MANAGE_THREADS."""
    qs = _client.pagination_qs(before=before, limit=limit)
    data = await _client.request_json(
        "GET", f"/channels/{channel_id}/users/@me/threads/archived/private{qs}", token=token
    )
    return [Thread(t) for t in data["threads"]]


async def fetch_active_guild_threads(guild_id: str, *, token: str | None = None) -> list[Thread]:
    """Fetches every active (non-archived) thread in the guild, across
    every channel."""
    data = await _client.request_json("GET", f"/guilds/{guild_id}/threads/active", token=token)
    return [Thread(t) for t in data["threads"]]
