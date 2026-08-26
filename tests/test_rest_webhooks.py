"""_rest/webhooks.py: bot-token webhook REST endpoints, plus their bot.<verb>()
and Channel/Guild/Webhook object-method delegation. The token-authenticated
side (execute, edit/delete message, slack/github compatible) lives in
cordless.webhook instead and is tested in test_webhook.py."""

import json
import os
from asyncio import run
from unittest.mock import patch

from conftest import FakeDiscordResponse

from cordless._rest import webhooks
from cordless._rest.models import Webhook
from cordless.app import Cordless
from cordless.models import Channel, Guild

_ENV = {"DISCORD_BOT_TOKEN": "tok"}

_WEBHOOK_PAYLOAD = {"id": "99", "name": "shiv's alerts", "channel_id": "20", "token": "wh-tok"}


def _urlopen(responses):
    return patch("cordless._rest._client.urllib.request.urlopen", side_effect=responses)


# --- _rest/webhooks.py (bot token) ---


def test_fetch_channel_webhooks_returns_webhook_list():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_WEBHOOK_PAYLOAD])]) as urlopen:
        result = run(webhooks.fetch_channel_webhooks("20"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/webhooks"
    assert result == [Webhook(_WEBHOOK_PAYLOAD)]


def test_fetch_guild_webhooks_returns_webhook_list():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_WEBHOOK_PAYLOAD])]) as urlopen:
        result = run(webhooks.fetch_guild_webhooks("10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/webhooks"
    assert result == [Webhook(_WEBHOOK_PAYLOAD)]


def test_fetch_webhook_returns_single_webhook():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_WEBHOOK_PAYLOAD)]) as urlopen:
        result = run(webhooks.fetch_webhook("99"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/webhooks/99"
    assert isinstance(result, Webhook)


def test_create_webhook_only_sends_fields_that_were_set():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_WEBHOOK_PAYLOAD)]) as urlopen:
        result = run(webhooks.create_webhook("20", "shiv's alerts"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/webhooks"
    assert json.loads(req.data) == {"name": "shiv's alerts"}
    assert isinstance(result, Webhook)


def test_create_webhook_sends_audit_log_reason():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_WEBHOOK_PAYLOAD)]) as urlopen:
        run(webhooks.create_webhook("20", "shiv's alerts", reason="rebranding"))

    assert urlopen.call_args.args[0].get_header("X-audit-log-reason") == "rebranding"


def test_edit_webhook_only_sends_fields_that_were_set():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_WEBHOOK_PAYLOAD)]) as urlopen:
        result = run(webhooks.edit_webhook("99", name="renamed"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/webhooks/99"
    assert json.loads(req.data) == {"name": "renamed"}
    assert isinstance(result, Webhook)


def test_edit_webhook_can_move_channel():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_WEBHOOK_PAYLOAD)]) as urlopen:
        run(webhooks.edit_webhook("99", channel_id="30"))

    assert json.loads(urlopen.call_args.args[0].data) == {"channel_id": "30"}


def test_edit_webhook_sends_audit_log_reason():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_WEBHOOK_PAYLOAD)]) as urlopen:
        run(webhooks.edit_webhook("99", name="renamed", reason="rebranding"))

    assert urlopen.call_args.args[0].get_header("X-audit-log-reason") == "rebranding"


def test_delete_webhook_deletes_webhook():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(webhooks.delete_webhook("99"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/webhooks/99"
    assert req.get_method() == "DELETE"


def test_delete_webhook_sends_audit_log_reason():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(webhooks.delete_webhook("99", reason="compromised"))

    assert urlopen.call_args.args[0].get_header("X-audit-log-reason") == "compromised"


# --- bot.<verb>() delegation ---


def test_bot_fetch_channel_webhooks_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_WEBHOOK_PAYLOAD])]):
        assert run(bot.fetch_channel_webhooks("20")) == [Webhook(_WEBHOOK_PAYLOAD)]


def test_bot_fetch_guild_webhooks_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_WEBHOOK_PAYLOAD])]):
        assert run(bot.fetch_guild_webhooks("10")) == [Webhook(_WEBHOOK_PAYLOAD)]


def test_bot_fetch_webhook_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_WEBHOOK_PAYLOAD)]):
        assert isinstance(run(bot.fetch_webhook("99")), Webhook)


def test_bot_edit_webhook_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_WEBHOOK_PAYLOAD)]) as urlopen:
        result = run(bot.edit_webhook("99", name="renamed"))

    assert json.loads(urlopen.call_args.args[0].data) == {"name": "renamed"}
    assert isinstance(result, Webhook)


# --- channel.*()/guild.*() object-method delegation ---


def test_channel_fetch_webhooks_delegates_to_rest_module():
    channel = Channel({"id": "20"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_WEBHOOK_PAYLOAD])]) as urlopen:
        result = run(channel.fetch_webhooks())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/webhooks"
    assert result == [Webhook(_WEBHOOK_PAYLOAD)]


def test_guild_fetch_webhooks_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_WEBHOOK_PAYLOAD])]) as urlopen:
        result = run(guild.fetch_webhooks())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/webhooks"
    assert result == [Webhook(_WEBHOOK_PAYLOAD)]


# --- webhook.*() object-method delegation (bot-token half) ---


def test_webhook_edit_delegates_to_rest_module():
    webhook = Webhook(_WEBHOOK_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_WEBHOOK_PAYLOAD)]) as urlopen:
        result = run(webhook.edit(name="renamed"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/webhooks/99"
    assert json.loads(req.data) == {"name": "renamed"}
    assert isinstance(result, Webhook)


def test_webhook_delete_delegates_to_rest_module():
    webhook = Webhook(_WEBHOOK_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(webhook.delete())

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/webhooks/99"
    assert req.get_method() == "DELETE"


# --- webhook.*() object-method delegation (token half, via cordless.webhook) ---


def test_webhook_execute_delegates_to_webhook_module(monkeypatch):
    import cordless.webhook as _webhook_module

    calls = []
    monkeypatch.setattr(
        _webhook_module, "execute", lambda *a: calls.append(a) or (200, json.dumps({"id": "msg-1"}).encode())
    )

    webhook = Webhook(_WEBHOOK_PAYLOAD)
    result = run(webhook.execute(content="hi", wait=True))

    webhook_id, webhook_token, payload, files, wait, thread_id = calls[0]
    assert (webhook_id, webhook_token) == ("99", "wh-tok")
    assert payload["content"] == "hi"
    assert result == {"id": "msg-1"}


def test_webhook_execute_without_wait_returns_none(monkeypatch):
    import cordless.webhook as _webhook_module

    monkeypatch.setattr(_webhook_module, "execute", lambda *a: (204, b""))

    webhook = Webhook(_WEBHOOK_PAYLOAD)
    result = run(webhook.execute(content="hi"))

    assert result is None


def test_webhook_fetch_message_delegates_to_webhook_module(monkeypatch):
    import cordless.webhook as _webhook_module

    calls = []
    monkeypatch.setattr(
        _webhook_module, "get_message", lambda *a: calls.append(a) or (200, json.dumps({"id": "msg-1"}).encode())
    )

    webhook = Webhook(_WEBHOOK_PAYLOAD)
    result = run(webhook.fetch_message("msg-1"))

    assert calls[0] == ("99", "wh-tok", "msg-1")
    assert result == {"id": "msg-1"}


def test_webhook_edit_message_delegates_to_webhook_module(monkeypatch):
    import cordless.webhook as _webhook_module

    calls = []
    monkeypatch.setattr(_webhook_module, "edit_message", lambda *a: calls.append(a) or (200, b"{}"))

    webhook = Webhook(_WEBHOOK_PAYLOAD)
    run(webhook.edit_message("msg-1", content="edited"))

    webhook_id, webhook_token, message_id, payload, files = calls[0]
    assert (webhook_id, webhook_token, message_id) == ("99", "wh-tok", "msg-1")
    assert payload["content"] == "edited"


def test_webhook_delete_message_delegates_to_webhook_module(monkeypatch):
    import cordless.webhook as _webhook_module

    calls = []
    monkeypatch.setattr(_webhook_module, "delete_message", lambda *a: calls.append(a) or (204, b""))

    webhook = Webhook(_WEBHOOK_PAYLOAD)
    run(webhook.delete_message("msg-1"))

    assert calls[0] == ("99", "wh-tok", "msg-1")
