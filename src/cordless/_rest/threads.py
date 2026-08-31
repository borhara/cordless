"""Thread REST endpoints (Discord API v10)."""

from . import _client
from .models import Thread, ThreadMember


async def start_thread_from_message(channel_id, message_id, name, *, auto_archive_duration=None, token=None):
    """Starts a public thread from an existing message. The thread shares
    the message's id, and the message's author is added to it
    automatically."""
    payload = {"name": name}
    if auto_archive_duration is not None:
        payload["auto_archive_duration"] = auto_archive_duration
    data = await _client.request("POST", f"/channels/{channel_id}/messages/{message_id}/threads", payload, token=token)
    return Thread(data)


async def start_thread_without_message(channel_id, name, *, thread_type=11, invitable=None, token=None):
    """Starts a thread with no starter message. thread_type defaults to
    11 (a public thread); pass 12 for a private one. invitable only
    applies to private threads, and controls whether non-moderators can
    add other members."""
    payload = {"name": name, "type": thread_type}
    if invitable is not None:
        payload["invitable"] = invitable
    data = await _client.request("POST", f"/channels/{channel_id}/threads", payload, token=token)
    return Thread(data)


async def start_thread_from_forum(
    channel_id,
    name,
    *,
    message,
    applied_tags=None,
    auto_archive_duration=None,
    rate_limit_per_user=None,
    token=None,
    files=None,
):
    """Starts a new post in a forum or media channel. The post itself is
    both the thread and its first message, built from the message
    argument the same way create_message builds one."""
    payload = {"name": name, "message": {"content": message}}

    if applied_tags:
        payload["applied_tags"] = applied_tags

    if auto_archive_duration:
        payload["auto_archive_duration"] = auto_archive_duration

    # 0 is a meaningful explicit value (no slowmode), unlike the fields
    # above - only leaving it unset should fall back to the forum channel's
    # own default_thread_rate_limit_per_user.
    if rate_limit_per_user is not None:
        payload["rate_limit_per_user"] = rate_limit_per_user

    data = await _client.request("POST", f"/channels/{channel_id}/threads", payload, files=files, token=token)
    return Thread(data)


async def join_thread(channel_id, token=None):
    """Adds the bot to a thread it isn't already in."""
    await _client.request("PUT", f"/channels/{channel_id}/thread-members/@me", token=token)


async def leave_thread(channel_id, token=None):
    """Removes the bot from a thread."""
    await _client.request("DELETE", f"/channels/{channel_id}/thread-members/@me", token=token)


async def add_thread_member(channel_id, user_id, token=None):
    """Adds another user to a thread."""
    await _client.request("PUT", f"/channels/{channel_id}/thread-members/{user_id}", token=token)


async def remove_thread_member(channel_id, user_id, token=None):
    """Removes another user from a thread."""
    await _client.request("DELETE", f"/channels/{channel_id}/thread-members/{user_id}", token=token)


async def fetch_thread_member(channel_id, user_id, *, with_member=False, token=None):
    """Fetches a single thread member. with_member also attaches that
    user's guild member object."""
    qs = "?with_member=true" if with_member else ""
    data = await _client.request("GET", f"/channels/{channel_id}/thread-members/{user_id}{qs}", token=token)
    assert data is not None, "GET always returns a body"
    return ThreadMember(data)


async def fetch_thread_members(channel_id, *, with_member=False, after=None, limit=None, token=None):
    """after/limit only take effect when with_member=True - Discord ignores
    them otherwise and always returns every member in one page."""
    qs = _client.query_string(with_member=with_member, after=after, limit=limit)
    data = await _client.request("GET", f"/channels/{channel_id}/thread-members{qs}", token=token)
    assert data is not None, "GET always returns a body"
    return [ThreadMember(m) for m in data]


async def fetch_public_archived_threads(channel_id, *, before=None, limit=None, token=None):
    """Fetches a page of the channel's archived public threads, newest
    archived first."""
    qs = _client.pagination_qs(before=before, limit=limit)
    data = await _client.request("GET", f"/channels/{channel_id}/threads/archived/public{qs}", token=token)
    assert data is not None, "GET always returns a body"
    return [Thread(t) for t in data["threads"]]


async def fetch_private_archived_threads(channel_id, *, before=None, limit=None, token=None):
    """Fetches a page of the channel's archived private threads. Requires
    MANAGE_THREADS, unless fetching only threads the bot has joined via
    fetch_joined_private_archived_threads instead."""
    qs = _client.pagination_qs(before=before, limit=limit)
    data = await _client.request("GET", f"/channels/{channel_id}/threads/archived/private{qs}", token=token)
    assert data is not None, "GET always returns a body"
    return [Thread(t) for t in data["threads"]]


async def fetch_joined_private_archived_threads(channel_id, *, before=None, limit=None, token=None):
    """Fetches a page of the channel's archived private threads the bot
    has joined. Unlike fetch_private_archived_threads, this doesn't need
    MANAGE_THREADS."""
    qs = _client.pagination_qs(before=before, limit=limit)
    data = await _client.request("GET", f"/channels/{channel_id}/users/@me/threads/archived/private{qs}", token=token)
    assert data is not None, "GET always returns a body"
    return [Thread(t) for t in data["threads"]]


async def fetch_active_guild_threads(guild_id, *, token=None):
    """Fetches every active (non-archived) thread in the guild, across
    every channel."""
    data = await _client.request("GET", f"/guilds/{guild_id}/threads/active", token=token)
    assert data is not None, "GET always returns a body"
    return [Thread(t) for t in data["threads"]]


async def search_channel_threads(
    channel_id,
    *,
    name=None,
    slop=None,
    min_id=None,
    max_id=None,
    tag=None,
    tag_setting=None,
    archived=None,
    sort_by=None,
    sort_order=None,
    limit=None,
    offset=None,
    token=None,
):
    """Forum/media channels only. archived filters the result: None leaves it
    to the endpoint, False returns active threads only, True archived only.
    tag takes a single tag id or a list of up to 20, matching Discord's
    repeated-key array query param shape."""
    parts = _client.query_parts(
        name=name,
        slop=slop,
        min_id=min_id,
        max_id=max_id,
        tag_setting=tag_setting,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )
    # archived is a real filter, not a flag: False means "active only", so it
    # has to be sent, unlike query_parts which drops any False.
    if archived is not None:
        parts.append(f"archived={'true' if archived else 'false'}")
    if tag is not None:
        parts += [f"tag={t}" for t in (tag if isinstance(tag, (list, tuple)) else [tag])]
    qs = _client.join_query_parts(parts)
    data = await _client.request("GET", f"/channels/{channel_id}/threads/search{qs}", token=token)
    assert data is not None, "GET always returns a body"
    return [Thread(t) for t in data["threads"]]
