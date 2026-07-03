import json
from unittest.mock import patch

import pytest

from cordless.app import Cordless
from cordless.register import sync_commands


def test_command_definitions_reflect_registered_commands():
    bot = Cordless()

    @bot.command("ping", description="Replies with pong")
    async def ping(ctx):
        pass

    @bot.command(
        "echo",
        description="Echoes text back",
        options=[{"name": "text", "description": "Text to echo", "type": 3, "required": True}],
    )
    async def echo(ctx):
        pass

    definitions = bot.router.command_definitions()

    assert {"name": "ping", "description": "Replies with pong", "type": 1, "options": []} in definitions
    assert any(d["name"] == "echo" and d["options"][0]["name"] == "text" for d in definitions)


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def test_sync_commands_resolves_application_id_from_bot_token_and_hits_global_endpoint():
    responses = [_FakeResponse({"id": "app-id"}), _FakeResponse([{"id": "1"}])]

    with patch("cordless.register.urllib.request.urlopen", side_effect=responses) as urlopen:
        result = sync_commands(
            [{"name": "ping", "description": "x", "type": 1, "options": []}], bot_token="bot-token"
        )

    lookup_request, put_request = (call.args[0] for call in urlopen.call_args_list)

    assert lookup_request.full_url == "https://discord.com/api/v10/oauth2/applications/@me"
    assert lookup_request.get_header("Authorization") == "Bot bot-token"

    assert put_request.full_url == "https://discord.com/api/v10/applications/app-id/commands"
    assert put_request.get_header("Authorization") == "Bot bot-token"
    assert result == [{"id": "1"}]


def test_sync_commands_scopes_to_guild_when_provided():
    responses = [_FakeResponse({"id": "app-id"}), _FakeResponse([])]

    with patch("cordless.register.urllib.request.urlopen", side_effect=responses) as urlopen:
        sync_commands([], guild_id="guild-id", bot_token="bot-token")

    put_request = urlopen.call_args_list[1].args[0]

    assert put_request.full_url == "https://discord.com/api/v10/applications/app-id/guilds/guild-id/commands"


def test_sync_commands_via_client_credentials_skips_application_id_lookup():
    responses = [_FakeResponse({"access_token": "bearer-tok"}), _FakeResponse([{"id": "1"}])]

    with patch("cordless.register.urllib.request.urlopen", side_effect=responses) as urlopen:
        result = sync_commands([], client_id="client-id", client_secret="client-secret")

    token_request, put_request = (call.args[0] for call in urlopen.call_args_list)

    assert token_request.full_url == "https://discord.com/api/v10/oauth2/token"
    assert token_request.get_header("Authorization") == f"Basic {_basic('client-id', 'client-secret')}"
    assert token_request.data == b"grant_type=client_credentials&scope=applications.commands.update"

    assert put_request.full_url == "https://discord.com/api/v10/applications/client-id/commands"
    assert put_request.get_header("Authorization") == "Bearer bearer-tok"
    assert result == [{"id": "1"}]


def test_sync_commands_prefers_bot_token_when_both_provided():
    responses = [_FakeResponse({"id": "app-id"}), _FakeResponse([])]

    with patch("cordless.register.urllib.request.urlopen", side_effect=responses) as urlopen:
        sync_commands([], bot_token="bot-token", client_id="client-id", client_secret="client-secret")

    lookup_request = urlopen.call_args_list[0].args[0]
    assert lookup_request.full_url == "https://discord.com/api/v10/oauth2/applications/@me"


def test_sync_commands_requires_some_credentials():
    with pytest.raises(ValueError):
        sync_commands([])


def test_bot_sync_commands_delegates_to_register_module():
    bot = Cordless()

    @bot.command("ping")
    async def ping(ctx):
        pass

    with patch("cordless.app.sync_commands", return_value=[{"id": "1"}]) as mock_sync:
        result = bot.sync_commands(bot_token="bot-token", guild_id="guild-id")

    mock_sync.assert_called_once_with(
        bot.router.command_definitions(),
        guild_id="guild-id",
        bot_token="bot-token",
        client_id=None,
        client_secret=None,
    )
    assert result == [{"id": "1"}]


def _basic(client_id, client_secret):
    import base64

    return base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
