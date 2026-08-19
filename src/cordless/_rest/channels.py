"""Channel REST endpoints (Discord API v10), plus the two guild-scoped
channel endpoints (create, list, reorder) that only make sense alongside
them."""

from ..models import Channel
from . import _client
from .models import FollowedChannel, Invite, MessagePin


def _payload(**fields):
    """Drop whatever field was left at its default None, so a call only sends
    what the caller actually set."""
    return {k: v for k, v in fields.items() if v is not None}


async def fetch_channel(channel_id, *, token=None):
    data = await _client.request("GET", f"/channels/{channel_id}", token=token)
    return Channel(data)


async def edit_channel(
    channel_id,
    *,
    name=None,
    icon=None,
    type=None,
    position=None,
    topic=None,
    nsfw=None,
    rate_limit_per_user=None,
    bitrate=None,
    user_limit=None,
    permission_overwrites=None,
    parent_id=None,
    rtc_region=None,
    video_quality_mode=None,
    default_auto_archive_duration=None,
    flags=None,
    available_tags=None,
    default_reaction_emoji=None,
    default_thread_rate_limit_per_user=None,
    default_sort_order=None,
    default_forum_layout=None,
    archived=None,
    auto_archive_duration=None,
    locked=None,
    invitable=None,
    applied_tags=None,
    token=None,
):
    """One endpoint covers group DMs, guild channels and threads alike -
    Discord just looks at which fields you actually send. Pass only the ones
    that apply to what channel_id happens to be."""
    payload = _payload(
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
    data = await _client.request("PATCH", f"/channels/{channel_id}", payload, token=token)
    return Channel(data)


async def delete_channel(channel_id, *, token=None):
    """Deletes a guild channel, closes a DM, or deletes a thread - returns
    the now-deleted channel object."""
    data = await _client.request("DELETE", f"/channels/{channel_id}", token=token)
    return Channel(data)


async def edit_channel_permissions(channel_id, overwrite_id, *, type, allow=None, deny=None, token=None):
    """`type` is 0 for a role overwrite, 1 for a member overwrite. `allow`/`deny`
    are permission bitfields as strings (see `Permissions`)."""
    payload = _payload(type=type, allow=allow, deny=deny)
    await _client.request("PUT", f"/channels/{channel_id}/permissions/{overwrite_id}", payload, token=token)


async def delete_channel_permission(channel_id, overwrite_id, *, token=None):
    await _client.request("DELETE", f"/channels/{channel_id}/permissions/{overwrite_id}", token=token)


async def fetch_channel_invites(channel_id, *, token=None):
    data = await _client.request("GET", f"/channels/{channel_id}/invites", token=token)
    assert data is not None, "GET always returns a body"
    return [Invite(i) for i in data]


async def create_channel_invite(
    channel_id,
    *,
    max_age=None,
    max_uses=None,
    temporary=None,
    unique=None,
    target_type=None,
    target_user_id=None,
    target_application_id=None,
    token=None,
):
    payload = _payload(
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


async def follow_announcement_channel(channel_id, webhook_channel_id, *, token=None):
    """Mirrors this announcement channel's future posts into webhook_channel_id.
    Returns the created webhook as a `FollowedChannel`."""
    data = await _client.request(
        "POST", f"/channels/{channel_id}/followers", {"webhook_channel_id": webhook_channel_id}, token=token
    )
    return FollowedChannel(data)


async def trigger_typing(channel_id, *, token=None):
    """Shows the typing indicator for ~10 seconds, or until a message is sent."""
    await _client.request("POST", f"/channels/{channel_id}/typing", token=token)


async def set_voice_channel_status(channel_id, status=None, *, token=None):
    """`status=None` clears it. Requires SET_VOICE_CHANNEL_STATUS, or SEND_MESSAGES
    plus CONNECT if you're the one currently connected."""
    await _client.request("PUT", f"/channels/{channel_id}/voice-status", {"status": status}, token=token)


async def add_group_dm_recipient(channel_id, user_id, access_token, *, nick=None, token=None):
    payload = _payload(access_token=access_token, nick=nick)
    await _client.request("PUT", f"/channels/{channel_id}/recipients/{user_id}", payload, token=token)


async def remove_group_dm_recipient(channel_id, user_id, *, token=None):
    await _client.request("DELETE", f"/channels/{channel_id}/recipients/{user_id}", token=token)


async def fetch_channel_pins(channel_id, *, before=None, limit=None, token=None):
    qs = _client.pagination_qs(before=before, limit=limit)
    data = await _client.request("GET", f"/channels/{channel_id}/messages/pins{qs}", token=token)
    assert data is not None, "GET always returns a body"
    return [MessagePin(p) for p in data["items"]]


async def pin_message(channel_id, message_id, *, token=None):
    await _client.request("PUT", f"/channels/{channel_id}/messages/pins/{message_id}", token=token)


async def unpin_message(channel_id, message_id, *, token=None):
    await _client.request("DELETE", f"/channels/{channel_id}/messages/pins/{message_id}", token=token)


# -- guild-scoped, but only ever meaningful alongside the channel endpoints above --


async def fetch_guild_channels(guild_id, *, token=None):
    data = await _client.request("GET", f"/guilds/{guild_id}/channels", token=token)
    assert data is not None, "GET always returns a body"
    return [Channel(c) for c in data]


async def create_guild_channel(
    guild_id,
    name,
    *,
    type=None,
    topic=None,
    bitrate=None,
    user_limit=None,
    rate_limit_per_user=None,
    position=None,
    permission_overwrites=None,
    parent_id=None,
    nsfw=None,
    rtc_region=None,
    video_quality_mode=None,
    default_auto_archive_duration=None,
    default_reaction_emoji=None,
    available_tags=None,
    default_sort_order=None,
    default_forum_layout=None,
    default_thread_rate_limit_per_user=None,
    flags=None,
    token=None,
):
    payload = _payload(
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
    data = await _client.request("POST", f"/guilds/{guild_id}/channels", payload, token=token)
    return Channel(data)


async def edit_guild_channel_positions(guild_id, positions, *, token=None):
    """positions is a list of {"id": channel_id, "position": int, ...} dicts,
    per Discord's Modify Guild Channel Positions body."""
    await _client.request("PATCH", f"/guilds/{guild_id}/channels", positions, token=token)
