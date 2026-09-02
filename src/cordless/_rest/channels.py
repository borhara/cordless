"""Channel REST endpoints (Discord API v10), plus the two guild-scoped
channel endpoints (create, list, reorder) that only make sense alongside
them."""

from typing import Any

from ..models import Channel
from . import _client
from ._client import UNSET
from .models import FollowedChannel, Invite, MessagePin


async def fetch_channel(channel_id: str, *, token: str | None = None) -> Channel:
    """Fetches a channel by id. Works for a guild channel, a thread, or a
    DM, whatever channel_id happens to point at."""
    data = await _client.request("GET", f"/channels/{channel_id}", token=token)
    return Channel(data)


async def edit_channel(
    channel_id: str,
    *,
    name: Any = UNSET,
    icon: Any = UNSET,
    type: Any = UNSET,
    position: Any = UNSET,
    topic: Any = UNSET,
    nsfw: Any = UNSET,
    rate_limit_per_user: Any = UNSET,
    bitrate: Any = UNSET,
    user_limit: Any = UNSET,
    permission_overwrites: Any = UNSET,
    parent_id: Any = UNSET,
    rtc_region: Any = UNSET,
    video_quality_mode: Any = UNSET,
    default_auto_archive_duration: Any = UNSET,
    flags: Any = UNSET,
    available_tags: Any = UNSET,
    default_reaction_emoji: Any = UNSET,
    default_thread_rate_limit_per_user: Any = UNSET,
    default_sort_order: Any = UNSET,
    default_forum_layout: Any = UNSET,
    archived: Any = UNSET,
    auto_archive_duration: Any = UNSET,
    locked: Any = UNSET,
    invitable: Any = UNSET,
    applied_tags: Any = UNSET,
    reason: str | None = None,
    token: str | None = None,
) -> Channel:
    """One endpoint covers group DMs, guild channels and threads alike -
    Discord just looks at which fields you actually send. Pass only the ones
    that apply to what channel_id happens to be. Most nullable fields
    (parent_id, icon, rtc_region, ...) can be cleared by passing None."""
    payload = _client.payload(
        name=name,
        icon=icon,
        type=type,
        position=position,
        topic=topic,
        nsfw=nsfw,
        rate_limit_per_user=rate_limit_per_user,
        bitrate=bitrate,
        user_limit=user_limit,
        permission_overwrites=permission_overwrites,
        parent_id=parent_id,
        rtc_region=rtc_region,
        video_quality_mode=video_quality_mode,
        default_auto_archive_duration=default_auto_archive_duration,
        flags=flags,
        available_tags=available_tags,
        default_reaction_emoji=default_reaction_emoji,
        default_thread_rate_limit_per_user=default_thread_rate_limit_per_user,
        default_sort_order=default_sort_order,
        default_forum_layout=default_forum_layout,
        archived=archived,
        auto_archive_duration=auto_archive_duration,
        locked=locked,
        invitable=invitable,
        applied_tags=applied_tags,
    )
    data = await _client.request("PATCH", f"/channels/{channel_id}", payload, token=token, reason=reason)
    return Channel(data)


async def delete_channel(channel_id: str, *, reason: str | None = None, token: str | None = None) -> Channel:
    """Deletes a guild channel, closes a DM, or deletes a thread - returns
    the now-deleted channel object."""
    data = await _client.request("DELETE", f"/channels/{channel_id}", token=token, reason=reason)
    return Channel(data)


async def edit_channel_permissions(
    channel_id: str,
    overwrite_id: str,
    *,
    type: int,
    allow: Any = UNSET,
    deny: Any = UNSET,
    reason: str | None = None,
    token: str | None = None,
) -> None:
    """`type` is 0 for a role overwrite, 1 for a member overwrite. `allow`/`deny`
    are permission bitfields as strings (see `Permissions`)."""
    payload = _client.payload(type=type, allow=allow, deny=deny)
    path = f"/channels/{channel_id}/permissions/{overwrite_id}"
    await _client.request("PUT", path, payload, token=token, reason=reason)


async def delete_channel_permission(
    channel_id: str, overwrite_id: str, *, reason: str | None = None, token: str | None = None
) -> None:
    """Requires MANAGE_ROLES."""
    await _client.request("DELETE", f"/channels/{channel_id}/permissions/{overwrite_id}", token=token, reason=reason)


async def fetch_channel_invites(channel_id: str, *, token: str | None = None) -> list[Invite]:
    """Fetches every invite pointing at this channel, each with its own
    use count."""
    data = await _client.request_json("GET", f"/channels/{channel_id}/invites", token=token)
    return [Invite(i) for i in data]


async def create_channel_invite(
    channel_id: str,
    *,
    max_age: Any = UNSET,
    max_uses: Any = UNSET,
    temporary: Any = UNSET,
    unique: Any = UNSET,
    target_type: Any = UNSET,
    target_user_id: Any = UNSET,
    target_application_id: Any = UNSET,
    token: str | None = None,
) -> Invite:
    """Creates an invite to this channel. Leaving max_age and max_uses
    unset gives an invite that never expires and has no use limit."""
    payload = _client.payload(
        max_age=max_age,
        max_uses=max_uses,
        temporary=temporary,
        unique=unique,
        target_type=target_type,
        target_user_id=target_user_id,
        target_application_id=target_application_id,
    )
    data = await _client.request("POST", f"/channels/{channel_id}/invites", payload, token=token)
    return Invite(data)


async def follow_announcement_channel(
    channel_id: str, webhook_channel_id: str, *, token: str | None = None
) -> FollowedChannel:
    """Mirrors this announcement channel's future posts into webhook_channel_id.
    Returns the created webhook as a `FollowedChannel`."""
    data = await _client.request(
        "POST", f"/channels/{channel_id}/followers", {"webhook_channel_id": webhook_channel_id}, token=token
    )
    return FollowedChannel(data)


async def trigger_typing(channel_id: str, *, token: str | None = None) -> None:
    """Shows the typing indicator for ~10 seconds, or until a message is sent."""
    await _client.request("POST", f"/channels/{channel_id}/typing", token=token)


async def set_voice_channel_status(channel_id: str, status: str | None = None, *, token: str | None = None) -> None:
    """`status=None` clears it. Requires SET_VOICE_CHANNEL_STATUS, or SEND_MESSAGES
    plus CONNECT if you're the one currently connected."""
    await _client.request("PUT", f"/channels/{channel_id}/voice-status", {"status": status}, token=token)


async def add_group_dm_recipient(
    channel_id: str, user_id: str, access_token: str, *, nick: Any = UNSET, token: str | None = None
) -> None:
    """Adds a user to a group DM. access_token is an OAuth2 token for that
    user with the gdm.join scope, obtained separately, a bot can't add
    someone to a group DM on its own authority."""
    payload = _client.payload(access_token=access_token, nick=nick)
    await _client.request("PUT", f"/channels/{channel_id}/recipients/{user_id}", payload, token=token)


async def remove_group_dm_recipient(channel_id: str, user_id: str, *, token: str | None = None) -> None:
    """Group DMs only."""
    await _client.request("DELETE", f"/channels/{channel_id}/recipients/{user_id}", token=token)


async def fetch_channel_pins(
    channel_id: str, *, before: str | None = None, limit: int | None = None, token: str | None = None
) -> list[MessagePin]:
    """Fetches the channel's pinned messages, newest first."""
    qs = _client.pagination_qs(before=before, limit=limit)
    data = await _client.request_json("GET", f"/channels/{channel_id}/messages/pins{qs}", token=token)
    return [MessagePin(p) for p in data["items"]]


async def pin_message(channel_id: str, message_id: str, *, token: str | None = None) -> None:
    """Pins a message. A channel can only hold 50 pinned messages at
    once."""
    await _client.request("PUT", f"/channels/{channel_id}/messages/pins/{message_id}", token=token)


async def unpin_message(channel_id: str, message_id: str, *, token: str | None = None) -> None:
    """Unpins a message without deleting it."""
    await _client.request("DELETE", f"/channels/{channel_id}/messages/pins/{message_id}", token=token)


# -- guild-scoped, but only ever meaningful alongside the channel endpoints above --


async def fetch_guild_channels(guild_id: str, *, token: str | None = None) -> list[Channel]:
    """Fetches every top-level channel in the guild. Threads aren't
    included, use the thread listing endpoints for those."""
    data = await _client.request_json("GET", f"/guilds/{guild_id}/channels", token=token)
    return [Channel(c) for c in data]


async def create_guild_channel(
    guild_id: str,
    name: str,
    *,
    type: Any = UNSET,
    topic: Any = UNSET,
    bitrate: Any = UNSET,
    user_limit: Any = UNSET,
    rate_limit_per_user: Any = UNSET,
    position: Any = UNSET,
    permission_overwrites: Any = UNSET,
    parent_id: Any = UNSET,
    nsfw: Any = UNSET,
    rtc_region: Any = UNSET,
    video_quality_mode: Any = UNSET,
    default_auto_archive_duration: Any = UNSET,
    default_reaction_emoji: Any = UNSET,
    available_tags: Any = UNSET,
    default_sort_order: Any = UNSET,
    default_forum_layout: Any = UNSET,
    default_thread_rate_limit_per_user: Any = UNSET,
    flags: Any = UNSET,
    reason: str | None = None,
    token: str | None = None,
) -> Channel:
    """Creates a new channel in the guild. type picks the channel kind
    (text, voice, category, forum, ...); leave it unset for an ordinary
    text channel."""
    payload = _client.payload(
        name=name,
        type=type,
        topic=topic,
        bitrate=bitrate,
        user_limit=user_limit,
        rate_limit_per_user=rate_limit_per_user,
        position=position,
        permission_overwrites=permission_overwrites,
        parent_id=parent_id,
        nsfw=nsfw,
        rtc_region=rtc_region,
        video_quality_mode=video_quality_mode,
        default_auto_archive_duration=default_auto_archive_duration,
        default_reaction_emoji=default_reaction_emoji,
        available_tags=available_tags,
        default_sort_order=default_sort_order,
        default_forum_layout=default_forum_layout,
        default_thread_rate_limit_per_user=default_thread_rate_limit_per_user,
        flags=flags,
    )
    data = await _client.request("POST", f"/guilds/{guild_id}/channels", payload, token=token, reason=reason)
    return Channel(data)


async def edit_guild_channel_positions(guild_id: str, positions: Any, *, token: str | None = None) -> None:
    """positions is a list of {"id": channel_id, "position": int, ...} dicts,
    per Discord's Modify Guild Channel Positions body. Not audit-logged by
    Discord, unlike every other mutating endpoint in this module."""
    await _client.request("PATCH", f"/guilds/{guild_id}/channels", positions, token=token)
