"""Webhook support: URL parsing, payload building, and the execute/edit/delete/manage flows."""

import json
from unittest.mock import patch

import pytest
from conftest import FakeDiscordResponse

import cordless.webhook
from cordless.app import Cordless

# --- parse_webhook_url ---


def test_parses_standard_webhook_url():
    webhook_id, token = cordless.webhook.parse_webhook_url("https://discord.com/api/webhooks/123/abc-def")
    assert webhook_id == "123"
    assert token == "abc-def"


def test_parses_legacy_discordapp_host():
    webhook_id, token = cordless.webhook.parse_webhook_url("https://discordapp.com/api/webhooks/123/abc-def")
    assert webhook_id == "123"
    assert token == "abc-def"


def test_parses_versioned_api_path():
    webhook_id, token = cordless.webhook.parse_webhook_url("https://discord.com/api/v10/webhooks/123/abc-def")
    assert webhook_id == "123"
    assert token == "abc-def"


def test_invalid_url_raises():
    with pytest.raises(ValueError):
        cordless.webhook.parse_webhook_url("https://example.com/not-a-webhook")


# --- build_payload ---


def test_build_payload_content_only():
    assert cordless.webhook.build_payload("hi", None, None) == {"content": "hi"}


def test_build_payload_includes_embeds_and_components():
    payload = cordless.webhook.build_payload(None, [{"title": "t"}], [{"type": 1, "components": []}])
    assert payload["embeds"] == [{"title": "t"}]
    assert payload["components"] == [{"type": 1, "components": []}]


def test_build_payload_sets_uikit_flag_for_components_v2():
    payload = cordless.webhook.build_payload(None, None, [{"type": 17, "components": []}])
    assert payload["flags"] == 32768


def test_build_payload_no_flag_for_plain_action_row():
    payload = cordless.webhook.build_payload(None, None, [{"type": 1, "components": []}])
    assert "flags" not in payload


def test_build_payload_webhook_only_fields_omitted_by_default():
    payload = cordless.webhook.build_payload("hi", None, None)
    assert "username" not in payload
    assert "avatar_url" not in payload
    assert "tts" not in payload


def test_build_payload_includes_username_avatar_tts():
    payload = cordless.webhook.build_payload("hi", None, None, username="bot", avatar_url="https://x/a.png", tts=True)
    assert payload["username"] == "bot"
    assert payload["avatar_url"] == "https://x/a.png"
    assert payload["tts"] is True


# --- module-level HTTP calls (mocked HTTPSConnection) ---


class FakeHTTPSConnection:
    requests = []
    responses = []

    def __init__(self, host, timeout=None):
        self.host = host
        self.timeout = timeout

    def request(self, method, url, body, headers):
        FakeHTTPSConnection.requests.append(
            {"method": method, "url": url, "body": body, "headers": headers, "timeout": self.timeout}
        )

    def getresponse(self):
        status, body = FakeHTTPSConnection.responses.pop(0) if FakeHTTPSConnection.responses else (200, b"{}")
        return type("R", (), {"status": status, "read": lambda self: body})()

    def close(self):
        pass


@pytest.fixture
def fake_conn(monkeypatch):
    FakeHTTPSConnection.requests = []
    FakeHTTPSConnection.responses = []
    monkeypatch.setattr(cordless.webhook, "HTTPSConnection", FakeHTTPSConnection)
    return FakeHTTPSConnection


def test_execute_posts_to_webhook_url(fake_conn):
    cordless.webhook.execute("123", "abc", {"content": "hi"})
    req = fake_conn.requests[0]
    assert req["method"] == "POST"
    assert req["url"] == "/api/v10/webhooks/123/abc"
    assert json.loads(req["body"]) == {"content": "hi"}
    assert req["headers"]["Content-Type"] == "application/json"


def test_execute_wait_and_thread_id_become_query_params(fake_conn):
    cordless.webhook.execute("123", "abc", {"content": "hi"}, wait=True, thread_id="456")
    assert fake_conn.requests[0]["url"] == "/api/v10/webhooks/123/abc?wait=true&thread_id=456"


def test_execute_with_files_sends_multipart(fake_conn):
    cordless.webhook.execute("123", "abc", {"content": "hi"}, files=[("a.png", b"png-bytes")])
    req = fake_conn.requests[0]
    assert req["headers"]["Content-Type"].startswith("multipart/form-data")
    assert b"png-bytes" in req["body"]


def test_edit_message_patches_message_path(fake_conn):
    cordless.webhook.edit_message("123", "abc", "999", {"content": "edited"})
    req = fake_conn.requests[0]
    assert req["method"] == "PATCH"
    assert req["url"] == "/api/v10/webhooks/123/abc/messages/999"
    assert json.loads(req["body"]) == {"content": "edited"}


def test_edit_message_default_original(fake_conn):
    cordless.webhook.edit_message("123", "abc", "@original", {"content": "edited"})
    assert fake_conn.requests[0]["url"] == "/api/v10/webhooks/123/abc/messages/@original"


def test_delete_message_deletes_message_path(fake_conn):
    cordless.webhook.delete_message("123", "abc", "999")
    req = fake_conn.requests[0]
    assert req["method"] == "DELETE"
    assert req["url"] == "/api/v10/webhooks/123/abc/messages/999"


def test_delete_webhook_deletes_webhook_path(fake_conn):
    cordless.webhook.delete_webhook("123", "abc")
    req = fake_conn.requests[0]
    assert req["method"] == "DELETE"
    assert req["url"] == "/api/v10/webhooks/123/abc"


def test_non_2xx_status_raises(fake_conn):
    fake_conn.responses = [(404, b'{"message": "Unknown Webhook"}')]
    with pytest.raises(RuntimeError, match="Discord API error 404.*Unknown Webhook"):
        cordless.webhook.execute("123", "abc", {"content": "hi"})


# --- Cordless.execute_webhook / edit_webhook_message / delete_webhook_message ---


@pytest.fixture
def webhook_calls(monkeypatch):
    calls = {}
    monkeypatch.setattr(
        cordless.webhook, "execute", lambda *a: calls.setdefault("execute", []).append(a) or (200, b"{}")
    )
    monkeypatch.setattr(
        cordless.webhook,
        "edit_message",
        lambda *a: calls.setdefault("edit_message", []).append(a) or (200, b"{}"),
    )
    monkeypatch.setattr(
        cordless.webhook,
        "delete_message",
        lambda *a: calls.setdefault("delete_message", []).append(a) or (204, b""),
    )
    monkeypatch.setattr(
        cordless.webhook, "delete_webhook", lambda *a: calls.setdefault("delete_webhook", []).append(a) or (204, b"")
    )
    return calls


def test_execute_webhook_parses_full_url(webhook_calls):
    import asyncio

    bot = Cordless()
    asyncio.run(bot.execute_webhook("https://discord.com/api/webhooks/123/abc", content="hi"))

    webhook_id, webhook_token, payload, files, wait, thread_id = webhook_calls["execute"][0]
    assert (webhook_id, webhook_token) == ("123", "abc")
    assert payload["content"] == "hi"


def test_execute_webhook_accepts_id_and_token(webhook_calls):
    import asyncio

    bot = Cordless()
    asyncio.run(bot.execute_webhook("123", "abc", content="hi"))

    webhook_id, webhook_token, payload, files, wait, thread_id = webhook_calls["execute"][0]
    assert (webhook_id, webhook_token) == ("123", "abc")


def test_edit_webhook_message_parses_full_url(webhook_calls):
    import asyncio

    bot = Cordless()
    asyncio.run(bot.edit_webhook_message("https://discord.com/api/webhooks/123/abc", content="edited"))

    webhook_id, webhook_token, message_id, payload, files = webhook_calls["edit_message"][0]
    assert (webhook_id, webhook_token, message_id) == ("123", "abc", "@original")
    assert payload["content"] == "edited"


def test_delete_webhook_message_parses_full_url(webhook_calls):
    import asyncio

    bot = Cordless()
    asyncio.run(bot.delete_webhook_message("https://discord.com/api/webhooks/123/abc"))

    webhook_id, webhook_token, message_id = webhook_calls["delete_message"][0]
    assert (webhook_id, webhook_token, message_id) == ("123", "abc", "@original")


def test_delete_webhook_with_token_skips_bot_auth(webhook_calls):
    import asyncio

    bot = Cordless()
    asyncio.run(bot.delete_webhook("123", "abc"))

    assert webhook_calls["delete_webhook"][0] == ("123", "abc")


def test_execute_webhook_propagates_failure(monkeypatch):
    import asyncio

    def fail(*a):
        raise RuntimeError("Discord API error 404: Unknown Webhook")

    monkeypatch.setattr(cordless.webhook, "execute", fail)

    bot = Cordless()
    with pytest.raises(RuntimeError, match="404"):
        asyncio.run(bot.execute_webhook("123", "abc", content="hi"))


def test_execute_webhook_returns_message_when_wait(monkeypatch):
    import asyncio

    monkeypatch.setattr(
        cordless.webhook, "execute", lambda *a: (200, json.dumps({"id": "msg-1", "content": "hi"}).encode())
    )

    bot = Cordless()
    result = asyncio.run(bot.execute_webhook("123", "abc", content="hi", wait=True))

    assert result == {"id": "msg-1", "content": "hi"}


def test_execute_webhook_returns_none_without_wait(monkeypatch):
    import asyncio

    monkeypatch.setattr(cordless.webhook, "execute", lambda *a: (204, b""))

    bot = Cordless()
    result = asyncio.run(bot.execute_webhook("123", "abc", content="hi"))

    assert result is None


# --- Cordless.create_webhook / get_channel_webhooks / delete_webhook (bot-token) ---


def test_create_webhook_posts_to_channel_webhooks_endpoint():
    import asyncio
    import os

    os.environ["DISCORD_BOT_TOKEN"] = "bot-tok"
    responses = [FakeDiscordResponse({"id": "wh-1", "token": "wh-tok"})]

    bot = Cordless()
    with patch("urllib.request.urlopen", side_effect=responses) as urlopen:
        result = asyncio.run(bot.create_webhook("chan-1", "Alerts"))

    assert result == {"id": "wh-1", "token": "wh-tok"}
    req = urlopen.call_args_list[0].args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/chan-1/webhooks"
    assert req.get_header("Authorization") == "Bot bot-tok"
    assert json.loads(req.data) == {"name": "Alerts"}


def test_get_channel_webhooks_lists_channel_webhooks():
    import asyncio
    import os

    os.environ["DISCORD_BOT_TOKEN"] = "bot-tok"
    responses = [FakeDiscordResponse([{"id": "wh-1"}, {"id": "wh-2"}])]

    bot = Cordless()
    with patch("urllib.request.urlopen", side_effect=responses) as urlopen:
        result = asyncio.run(bot.get_channel_webhooks("chan-1"))

    assert result == [{"id": "wh-1"}, {"id": "wh-2"}]
    assert urlopen.call_args_list[0].args[0].full_url == "https://discord.com/api/v10/channels/chan-1/webhooks"


def test_delete_webhook_without_token_uses_bot_auth():
    import asyncio
    import os

    os.environ["DISCORD_BOT_TOKEN"] = "bot-tok"
    responses = [FakeDiscordResponse(None)]

    bot = Cordless()
    with patch("urllib.request.urlopen", side_effect=responses) as urlopen:
        asyncio.run(bot.delete_webhook("wh-1"))

    req = urlopen.call_args_list[0].args[0]
    assert req.full_url == "https://discord.com/api/v10/webhooks/wh-1"
    assert req.get_header("Authorization") == "Bot bot-tok"
