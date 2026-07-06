from unittest.mock import patch

import pytest
from conftest import FakeDiscordResponse

from cordless.app import Cordless, option
from cordless.register import sync_commands

# --- command_definitions ---


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

    defs = bot.router.command_definitions()
    assert {"name": "ping", "description": "Replies with pong", "type": 1, "options": []} in defs
    assert any(d["name"] == "echo" and d["options"][0]["name"] == "text" for d in defs)


def test_context_menu_definitions_have_no_description_or_options():
    bot = Cordless()

    @bot.user_command("Inspect User")
    async def inspect(ctx):
        pass

    @bot.message_command("Bookmark")
    async def bookmark(ctx):
        pass

    defs = {d["name"]: d for d in bot.router.command_definitions()}
    assert defs["Inspect User"] == {"name": "Inspect User", "type": 2}
    assert defs["Bookmark"] == {"name": "Bookmark", "type": 3}


# --- option() helper ---


def test_option_defaults_to_string_type():
    assert option("text", "A text option")["type"] == 3


def test_option_type_aliases():
    assert option("n", type="integer")["type"] == 4
    assert option("b", type="boolean")["type"] == 5
    assert option("u", type="user")["type"] == 6
    assert option("c", type="channel")["type"] == 7
    assert option("r", type="role")["type"] == 8
    assert option("x", type="number")["type"] == 10
    assert option("a", type="attachment")["type"] == 11


def test_option_required():
    o = option("msg", required=True)
    assert o["required"] is True
    assert "required" not in option("msg")  # absent when False


def test_option_autocomplete():
    o = option("q", autocomplete=True)
    assert o["autocomplete"] is True


def test_option_choices():
    choices = [{"name": "Red", "value": "red"}]
    assert option("color", choices=choices)["choices"] == choices


def test_option_min_max_value():
    o = option("n", type="integer", min_value=1, max_value=10)
    assert o["min_value"] == 1
    assert o["max_value"] == 10


def test_option_min_max_length():
    o = option("text", min_length=2, max_length=100)
    assert o["min_length"] == 2
    assert o["max_length"] == 100


def test_option_raises_for_unknown_type_alias():
    with pytest.raises(ValueError, match="strnig"):
        option("x", type="strnig")


def test_option_omits_unused_keys():
    o = option("text", "desc")
    assert "required" not in o
    assert "autocomplete" not in o
    assert "choices" not in o
    assert "min_value" not in o


# --- sync_commands ---


def test_sync_commands_resolves_app_id_from_bot_token_and_hits_global_endpoint():
    responses = [FakeDiscordResponse({"id": "app-id"}), FakeDiscordResponse([{"id": "1"}])]

    with patch("cordless.register.urllib.request.urlopen", side_effect=responses) as urlopen:
        result = sync_commands([{"name": "ping", "description": "x", "type": 1, "options": []}], bot_token="bot-token")

    lookup, put = (call.args[0] for call in urlopen.call_args_list)
    assert lookup.full_url == "https://discord.com/api/v10/oauth2/applications/@me"
    assert lookup.get_header("Authorization") == "Bot bot-token"
    assert put.full_url == "https://discord.com/api/v10/applications/app-id/commands"
    assert put.get_header("Authorization") == "Bot bot-token"
    assert result == [{"id": "1"}]


def test_sync_commands_scopes_to_guild():
    responses = [FakeDiscordResponse({"id": "app-id"}), FakeDiscordResponse([])]

    with patch("cordless.register.urllib.request.urlopen", side_effect=responses) as urlopen:
        sync_commands([], guild_id="guild-id", bot_token="bot-token")

    put = urlopen.call_args_list[1].args[0]
    assert put.full_url == "https://discord.com/api/v10/applications/app-id/guilds/guild-id/commands"


def test_sync_commands_via_client_credentials():
    responses = [FakeDiscordResponse({"access_token": "bearer-tok"}), FakeDiscordResponse([{"id": "1"}])]

    with patch("cordless.register.urllib.request.urlopen", side_effect=responses) as urlopen:
        result = sync_commands([], client_id="client-id", client_secret="client-secret")

    token_req, put = (call.args[0] for call in urlopen.call_args_list)
    assert token_req.full_url == "https://discord.com/api/v10/oauth2/token"
    assert token_req.get_header("Authorization") == f"Basic {_basic('client-id', 'client-secret')}"
    assert put.full_url == "https://discord.com/api/v10/applications/client-id/commands"
    assert put.get_header("Authorization") == "Bearer bearer-tok"
    assert result == [{"id": "1"}]


def test_sync_commands_prefers_bot_token_over_client_credentials():
    responses = [FakeDiscordResponse({"id": "app-id"}), FakeDiscordResponse([])]

    with patch("cordless.register.urllib.request.urlopen", side_effect=responses) as urlopen:
        sync_commands([], bot_token="bot-token", client_id="client-id", client_secret="client-secret")

    assert urlopen.call_args_list[0].args[0].full_url == "https://discord.com/api/v10/oauth2/applications/@me"


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
