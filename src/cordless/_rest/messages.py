"""Message and reaction REST endpoints (Discord API v10).

Cordless.send_message/edit_message/delete_message (app.py) are the shipped
public names for the create/edit/delete endpoints; they delegate here. Reach
the full field set (replies, polls, stickers, retained attachments) through
channel.send() / message.edit() rather than calling create_message/
edit_channel_message directly.
"""

import urllib.parse

from .._payload import _FLAG_UI_KIT, _contains_uikit, _validate_content_length, _validate_uikit
from ..models import Message, User
from . import _client
from ._client import UNSET
from .models import MessageSearchResult


def _quote_emoji(emoji):
    # Discord's reaction routes take a bare unicode emoji or `name:id` for a
    # custom one, URL-encoded into the path.
    return urllib.parse.quote(emoji)


def _to_dicts(components):
    return [c.to_dict() if hasattr(c, "to_dict") else c for c in components]


def _has_value(x):
    # an actual value to send, as opposed to UNSET (omit) or None (clear).
    return x is not UNSET and x is not None


def _or_none(x):
    return None if x is UNSET else x


async def fetch_channel_messages(channel_id, *, around=None, before=None, after=None, limit=None, token=None):
    """around/before/after are mutually exclusive; each anchors the page on a
    different message id."""
    qs = _client.query_string(around=around, before=before, after=after, limit=limit)
    data = await _client.request_json("GET", f"/channels/{channel_id}/messages{qs}", token=token)
    return [Message(m) for m in data]


async def fetch_message(channel_id, message_id, *, token=None):
    """The full `Message`. For a page of recent messages use fetch_channel_messages."""
    data = await _client.request("GET", f"/channels/{channel_id}/messages/{message_id}", token=token)
    return Message(data)


async def create_message(
    channel_id,
    *,
    content=None,
    embeds=None,
    components=None,
    files=None,
    tts=None,
    nonce=None,
    allowed_mentions=None,
    message_reference=None,
    sticker_ids=None,
    flags=None,
    enforce_nonce=None,
    poll=None,
    token=None,
):
    """The raw Create Message endpoint. channel.send() wraps it with the
    conveniences most callers want."""
    is_uikit = _contains_uikit(components)
    if is_uikit:
        _validate_uikit(content, embeds, components)
    else:
        _validate_content_length(content)

    payload = _client.compact(
        content=content,
        embeds=_to_dicts(embeds) if embeds is not None else None,
        components=_to_dicts(components) if components is not None else None,
        tts=tts,
        nonce=nonce,
        allowed_mentions=allowed_mentions,
        message_reference=message_reference,
        sticker_ids=sticker_ids,
        enforce_nonce=enforce_nonce,
        poll=poll,
    )
    computed_flags = (flags or 0) | (_FLAG_UI_KIT if is_uikit else 0)
    if computed_flags:
        payload["flags"] = computed_flags

    data = await _client.request("POST", f"/channels/{channel_id}/messages", payload, files=files, token=token)
    return Message(data)


async def crosspost_message(channel_id, message_id, *, token=None):
    """Announcement channels only. Returns the crossposted `Message`."""
    data = await _client.request("POST", f"/channels/{channel_id}/messages/{message_id}/crosspost", token=token)
    return Message(data)


async def edit_channel_message(
    channel_id,
    message_id,
    *,
    content=UNSET,
    embeds=UNSET,
    components=UNSET,
    files=None,
    allowed_mentions=UNSET,
    flags=None,
    attachments=UNSET,
    token=None,
):
    """Pass None for content/embeds/allowed_mentions/attachments to clear them;
    omit them to leave them untouched. flags is a plain bitfield, so it takes
    the omit-unless-set convention rather than None-clears."""
    has_uikit = _has_value(components) and _contains_uikit(components)
    if has_uikit:
        # only an explicit content/embeds in the same call conflicts with
        # Components v2; leaving them untouched (UNSET) does not.
        _validate_uikit(_or_none(content), _or_none(embeds), components)
    elif content is not UNSET:
        _validate_content_length(content)

    if flags is not None or has_uikit:
        computed_flags = (flags or 0) | (_FLAG_UI_KIT if has_uikit else 0)
    else:
        computed_flags = UNSET

    payload = _client.payload(
        content=content,
        embeds=_to_dicts(embeds) if _has_value(embeds) else embeds,
        components=_to_dicts(components) if _has_value(components) else components,
        allowed_mentions=allowed_mentions,
        flags=computed_flags,
        attachments=attachments,
    )
    data = await _client.request(
        "PATCH", f"/channels/{channel_id}/messages/{message_id}", payload, files=files, token=token
    )
    return Message(data)


async def delete_channel_message(channel_id, message_id, *, token=None):
    """Anyone else's message needs MANAGE_MESSAGES."""
    await _client.request("DELETE", f"/channels/{channel_id}/messages/{message_id}", token=token)


async def bulk_delete_messages(channel_id, message_ids, *, token=None):
    """Guild channels only, and nothing older than two weeks. Requires
    MANAGE_MESSAGES."""
    await _client.request(
        "POST", f"/channels/{channel_id}/messages/bulk-delete", {"messages": message_ids}, token=token
    )


async def create_reaction(channel_id, message_id, emoji, *, token=None):
    """Needs ADD_REACTIONS unless someone has already reacted with this emoji."""
    path = f"/channels/{channel_id}/messages/{message_id}/reactions/{_quote_emoji(emoji)}/@me"
    await _client.request("PUT", path, token=token)


async def delete_own_reaction(channel_id, message_id, emoji, *, token=None):
    """Removes just the bot's own reaction; needs no permission."""
    path = f"/channels/{channel_id}/messages/{message_id}/reactions/{_quote_emoji(emoji)}/@me"
    await _client.request("DELETE", path, token=token)


async def delete_user_reaction(channel_id, message_id, emoji, user_id, *, token=None):
    """Requires MANAGE_MESSAGES."""
    path = f"/channels/{channel_id}/messages/{message_id}/reactions/{_quote_emoji(emoji)}/{user_id}"
    await _client.request("DELETE", path, token=token)


async def fetch_reactions(channel_id, message_id, emoji, *, type=None, after=None, limit=None, token=None):
    """type=1 selects super (burst) reactions instead of normal ones."""
    qs = _client.query_string(type=type, after=after, limit=limit)
    data = await _client.request_json(
        "GET", f"/channels/{channel_id}/messages/{message_id}/reactions/{_quote_emoji(emoji)}{qs}", token=token
    )
    return [User(u) for u in data]


async def delete_all_reactions(channel_id, message_id, *, token=None):
    """Requires MANAGE_MESSAGES."""
    await _client.request("DELETE", f"/channels/{channel_id}/messages/{message_id}/reactions", token=token)


async def delete_all_reactions_for_emoji(channel_id, message_id, emoji, *, token=None):
    """Requires MANAGE_MESSAGES. Leaves other emoji's reactions in place."""
    path = f"/channels/{channel_id}/messages/{message_id}/reactions/{_quote_emoji(emoji)}"
    await _client.request("DELETE", path, token=token)


async def fetch_poll_answer_voters(channel_id, message_id, answer_id, *, after=None, limit=None, token=None):
    """The `User` list that voted for one poll answer, paginated by user id."""
    qs = _client.query_string(after=after, limit=limit)
    path = f"/channels/{channel_id}/polls/{message_id}/answers/{answer_id}{qs}"
    data = await _client.request_json("GET", path, token=token)
    return [User(u) for u in data["users"]]


async def expire_poll(channel_id, message_id, *, token=None):
    """Ends the poll now rather than at its scheduled time. Returns the
    updated `Message`."""
    data = await _client.request("POST", f"/channels/{channel_id}/polls/{message_id}/expire", token=token)
    return Message(data)


def _array_qs(**fields):
    # Discord's array query params repeat the key (author_id=1&author_id=2)
    # rather than comma-joining.
    parts = []
    for key, value in fields.items():
        if value is None:
            continue
        values = value if isinstance(value, (list, tuple)) else [value]
        for v in values:
            if isinstance(v, bool):
                v = "true" if v else "false"
            parts.append(f"{key}={urllib.parse.quote(str(v))}")
    return _client.join_query_parts(parts)


async def search_guild_messages(
    guild_id,
    *,
    limit=None,
    offset=None,
    max_id=None,
    min_id=None,
    slop=None,
    content=None,
    channel_id=None,
    author_type=None,
    author_id=None,
    mentions=None,
    mentions_role_id=None,
    mention_everyone=None,
    replied_to_user_id=None,
    replied_to_message_id=None,
    pinned=None,
    has=None,
    embed_type=None,
    embed_provider=None,
    link_hostname=None,
    attachment_filename=None,
    attachment_extension=None,
    sort_by=None,
    sort_order=None,
    include_nsfw=None,
    token=None,
):
    """Preview endpoint. Requires READ_MESSAGE_HISTORY and, per your app's
    config, the MESSAGE_CONTENT intent. Results may come back empty while
    Discord is still indexing the guild. Any array field accepts a list."""
    qs = _array_qs(
        limit=limit,
        offset=offset,
        max_id=max_id,
        min_id=min_id,
        slop=slop,
        content=content,
        channel_id=channel_id,
        author_type=author_type,
        author_id=author_id,
        mentions=mentions,
        mentions_role_id=mentions_role_id,
        mention_everyone=mention_everyone,
        replied_to_user_id=replied_to_user_id,
        replied_to_message_id=replied_to_message_id,
        pinned=pinned,
        has=has,
        embed_type=embed_type,
        embed_provider=embed_provider,
        link_hostname=link_hostname,
        attachment_filename=attachment_filename,
        attachment_extension=attachment_extension,
        sort_by=sort_by,
        sort_order=sort_order,
        include_nsfw=include_nsfw,
    )
    data = await _client.request("GET", f"/guilds/{guild_id}/messages/search{qs}", token=token)
    return MessageSearchResult(data)
