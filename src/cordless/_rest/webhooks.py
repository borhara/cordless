"""Bot-token webhook management (Discord API v10). Token-authenticated
webhook execution (execute, edit/delete message, Slack/GitHub) is in
cordless/webhook.py, kept dependency-free for the response path.
"""

from typing import Any

from . import _client
from ._client import UNSET
from .models import Webhook


async def fetch_channel_webhooks(channel_id: str, *, token: str | None = None) -> list[Webhook]:
    """Every `Webhook` on the channel. Requires MANAGE_WEBHOOKS."""
    data = await _client.request_json("GET", f"/channels/{channel_id}/webhooks", token=token)
    return [Webhook(w) for w in data]


async def fetch_guild_webhooks(guild_id: str, *, token: str | None = None) -> list[Webhook]:
    """Every `Webhook` in the guild. Requires MANAGE_WEBHOOKS."""
    data = await _client.request_json("GET", f"/guilds/{guild_id}/webhooks", token=token)
    return [Webhook(w) for w in data]


async def fetch_webhook(webhook_id: str, *, token: str | None = None) -> Webhook:
    """One `Webhook` by id, token included."""
    data = await _client.request("GET", f"/webhooks/{webhook_id}", token=token)
    return Webhook(data)


async def create_webhook(
    channel_id: str, name: str, *, avatar: Any = UNSET, reason: str | None = None, token: str | None = None
) -> Webhook:
    """Creates a new webhook on a channel. name can't be "clyde", Discord
    reserves that one."""
    payload = _client.payload(name=name, avatar=avatar)
    data = await _client.request("POST", f"/channels/{channel_id}/webhooks", payload, token=token, reason=reason)
    return Webhook(data)


async def edit_webhook(
    webhook_id: str,
    *,
    name: Any = UNSET,
    avatar: Any = UNSET,
    channel_id: Any = UNSET,
    reason: str | None = None,
    token: str | None = None,
) -> Webhook:
    """Requires MANAGE_WEBHOOKS; moving channels needs it on both."""
    payload = _client.payload(name=name, avatar=avatar, channel_id=channel_id)
    data = await _client.request("PATCH", f"/webhooks/{webhook_id}", payload, token=token, reason=reason)
    return Webhook(data)


async def delete_webhook(webhook_id: str, *, reason: str | None = None, token: str | None = None) -> None:
    """Requires MANAGE_WEBHOOKS."""
    await _client.request("DELETE", f"/webhooks/{webhook_id}", token=token, reason=reason)
