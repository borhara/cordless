import json
from unittest.mock import patch

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


def test_sync_commands_hits_global_endpoint_with_bot_auth():
    with patch("cordless.register.urllib.request.urlopen", return_value=_FakeResponse([{"id": "1"}])) as urlopen:
        result = sync_commands("app-id", "bot-token", [{"name": "ping", "description": "x", "type": 1, "options": []}])

    request = urlopen.call_args[0][0]

    assert request.full_url == "https://discord.com/api/v10/applications/app-id/commands"
    assert request.get_header("Authorization") == "Bot bot-token"
    assert result == [{"id": "1"}]


def test_sync_commands_scopes_to_guild_when_provided():
    with patch("cordless.register.urllib.request.urlopen", return_value=_FakeResponse([])) as urlopen:
        sync_commands("app-id", "bot-token", [], guild_id="guild-id")

    request = urlopen.call_args[0][0]

    assert request.full_url == "https://discord.com/api/v10/applications/app-id/guilds/guild-id/commands"


def test_bot_sync_commands_delegates_to_register_module():
    bot = Cordless()

    @bot.command("ping")
    async def ping(ctx):
        pass

    with patch("cordless.app.sync_commands", return_value=[{"id": "1"}]) as mock_sync:
        result = bot.sync_commands("app-id", "bot-token", guild_id="guild-id")

    mock_sync.assert_called_once_with("app-id", "bot-token", bot.router.command_definitions(), guild_id="guild-id")
    assert result == [{"id": "1"}]
