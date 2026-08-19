"""Bot-token webhook REST endpoints (Discord API v10).

The token-authenticated ones (Execute Webhook, Get/Edit/Delete Webhook
Message, Slack/GitHub-compatible execute, ...) live in cordless/webhook.py
instead, not here - that module is deliberately dependency-free (no _rest
import) so it stays cheap to import on the direct interaction-response path.
This module is the bot-token half: managing webhooks themselves rather than
firing messages through one."""

from . import _client
from ._client import UNSET
from .models import Webhook


async def fetch_channel_webhooks(channel_id, *, token=None):
    data = await _client.request("GET", f"/channels/{channel_id}/webhooks", token=token)
    assert data is not None, "GET always returns a body"
    return [Webhook(w) for w in data]


async def fetch_guild_webhooks(guild_id, *, token=None):
    data = await _client.request("GET", f"/guilds/{guild_id}/webhooks", token=token)
    assert data is not None, "GET always returns a body"
    return [Webhook(w) for w in data]


async def fetch_webhook(webhook_id, *, token=None):
    data = await _client.request("GET", f"/webhooks/{webhook_id}", token=token)
    return Webhook(data)


async def create_webhook(channel_id, name, *, avatar=UNSET, token=None):
    payload = _client.payload(name=name, avatar=avatar)
    data = await _client.request("POST", f"/channels/{channel_id}/webhooks", payload, token=token)
    return Webhook(data)


async def edit_webhook(webhook_id, *, name=UNSET, avatar=UNSET, channel_id=UNSET, token=None):
    payload = _client.payload(name=name, avatar=avatar, channel_id=channel_id)
    data = await _client.request("PATCH", f"/webhooks/{webhook_id}", payload, token=token)
    return Webhook(data)


async def delete_webhook(webhook_id, *, token=None):
    await _client.request("DELETE", f"/webhooks/{webhook_id}", token=token)
