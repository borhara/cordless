"""Message and reaction REST endpoints (Discord API v10).

send_message/edit_message/delete_message on Cordless itself (app.py) already
own those names as its public, shipped surface - they delegate here rather
than duplicating the request logic, but there is deliberately no flat
bot.create_message()/bot.edit_message() alongside them, that would just be a
second, confusingly similar name for the same endpoint. The fuller feature
set (replies, polls, stickers, retained attachments, ...) is reached through
channel.send()/message.edit() instead.
"""

import urllib.parse

from ..context import _FLAG_UI_KIT, _contains_uikit, _validate_content_length
from ..models import Message, User
from . import _client
from ._client import UNSET
from .models import MessageSearchResult


def _quote_emoji(emoji):
    """Discord wants a unicode emoji, or name:id for a custom one, URL encoded."""
    return urllib.parse.quote(emoji)


def _to_dicts(components):
    return [c.to_dict() if hasattr(c, "to_dict") else c for c in components]


async def fetch_channel_messages(channel_id, *, around=None, before=None, after=None, limit=None, token=None):
    qs = _client.query_string(around=around, before=before, after=after, limit=limit)
    data = await _client.request("GET", f"/channels/{channel_id}/messages{qs}", token=token)
    assert data is not None, "GET always returns a body"
    return [Message(m) for m in data]


async def fetch_message(channel_id, message_id, *, token=None):
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
    _validate_content_length(content)
    payload = {}
    if content is not None:
        payload["content"] = content
    if embeds is not None:
        payload["embeds"] = _to_dicts(embeds)
    if components is not None:
        payload["components"] = _to_dicts(components)
    if tts is not None:
        payload["tts"] = tts
    if nonce is not None:
        payload["nonce"] = nonce
    if allowed_mentions is not None:
        payload["allowed_mentions"] = allowed_mentions
    if message_reference is not None:
        payload["message_reference"] = message_reference
    if sticker_ids is not None:
        payload["sticker_ids"] = sticker_ids
    if enforce_nonce is not None:
        payload["enforce_nonce"] = enforce_nonce
    if poll is not None:
        payload["poll"] = poll
    computed_flags = flags or 0
    if _contains_uikit(components):
        computed_flags |= _FLAG_UI_KIT
    if computed_flags:
        payload["flags"] = computed_flags

    data = await _client.request("POST", f"/channels/{channel_id}/messages", payload, files=files, token=token)
    return Message(data)


async def crosspost_message(channel_id, message_id, *, token=None):
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
    """content, embeds, allowed_mentions and attachments can be cleared by
    passing None. flags is a plain bitfield (0 and "leave untouched" have
    the same effect as each other), so it stays omit-unless-set rather than
    using the same None-clears convention as the others."""
    if content is not UNSET:
        _validate_content_length(content)
    has_uikit = components not in (UNSET, None) and _contains_uikit(components)
    if flags is not None or has_uikit:
        computed_flags = (flags or 0) | (_FLAG_UI_KIT if has_uikit else 0)
    else:
        computed_flags = UNSET
    payload = _client.payload(
        content=content,
        embeds=_to_dicts(embeds) if embeds not in (UNSET, None) else embeds,
        components=_to_dicts(components) if components not in (UNSET, None) else components,
        allowed_mentions=allowed_mentions,
        flags=computed_flags,
        attachments=attachments,
    )
    data = await _client.request(
        "PATCH", f"/channels/{channel_id}/messages/{message_id}", payload, files=files, token=token
    )
    return Message(data)


async def delete_channel_message(channel_id, message_id, *, token=None):
    await _client.request("DELETE", f"/channels/{channel_id}/messages/{message_id}", token=token)


async def bulk_delete_messages(channel_id, message_ids, *, token=None):
    """Only works on guild channels, and only for messages younger than
    two weeks."""
    await _client.request(
        "POST", f"/channels/{channel_id}/messages/bulk-delete", {"messages": message_ids}, token=token
    )


async def create_reaction(channel_id, message_id, emoji, *, token=None):
    path = f"/channels/{channel_id}/messages/{message_id}/reactions/{_quote_emoji(emoji)}/@me"
    await _client.request("PUT", path, token=token)


async def delete_own_reaction(channel_id, message_id, emoji, *, token=None):
    path = f"/channels/{channel_id}/messages/{message_id}/reactions/{_quote_emoji(emoji)}/@me"
    await _client.request("DELETE", path, token=token)


async def delete_user_reaction(channel_id, message_id, emoji, user_id, *, token=None):
    path = f"/channels/{channel_id}/messages/{message_id}/reactions/{_quote_emoji(emoji)}/{user_id}"
    await _client.request("DELETE", path, token=token)


async def fetch_reactions(channel_id, message_id, emoji, *, type=None, after=None, limit=None, token=None):
    qs = _client.query_string(type=type, after=after, limit=limit)
    data = await _client.request(
        "GET", f"/channels/{channel_id}/messages/{message_id}/reactions/{_quote_emoji(emoji)}{qs}", token=token
    )
    assert data is not None, "GET always returns a body"
    return [User(u) for u in data]


async def delete_all_reactions(channel_id, message_id, *, token=None):
    await _client.request("DELETE", f"/channels/{channel_id}/messages/{message_id}/reactions", token=token)


async def delete_all_reactions_for_emoji(channel_id, message_id, emoji, *, token=None):
    path = f"/channels/{channel_id}/messages/{message_id}/reactions/{_quote_emoji(emoji)}"
    await _client.request("DELETE", path, token=token)


def _array_qs(**fields):
    """Discord's array query params repeat the key per value
    (author_id=1&author_id=2), not a single comma-joined value."""
    parts = []
    for key, value in fields.items():
        if value is None:
            continue
        values = value if isinstance(value, (list, tuple)) else [value]
        for v in values:
            if isinstance(v, bool):
                v = "true" if v else "false"
            parts.append(f"{key}={urllib.parse.quote(str(v))}")
    return ("?" + "&".join(parts)) if parts else ""


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
    """Requires READ_MESSAGE_HISTORY and, depending on your app's config,
    the MESSAGE_CONTENT privileged intent. Any array field takes a list."""
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
