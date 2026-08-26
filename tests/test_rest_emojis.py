"""_rest/emojis.py: guild and application emoji REST endpoints, plus their
bot.<verb>() and Guild/Emoji object-method delegation."""

import json
import os
from asyncio import run
from unittest.mock import patch

from conftest import FakeDiscordResponse

from cordless._rest import emojis
from cordless._rest.models import Emoji
from cordless.app import Cordless
from cordless.models import Guild

_ENV = {"DISCORD_BOT_TOKEN": "tok"}

_EMOJI_PAYLOAD = {"id": "1", "name": "shiv_dance", "animated": True}


def _urlopen(responses):
    return patch("cordless._rest._client._send", side_effect=responses)


# --- guild emojis ---


def test_fetch_guild_emojis_returns_emoji_list_with_guild_id_injected():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_EMOJI_PAYLOAD])]) as urlopen:
        result = run(emojis.fetch_guild_emojis("10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/emojis"
    assert len(result) == 1
    assert result[0]._data["guild_id"] == "10"


def test_fetch_guild_emoji_returns_single_emoji():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_EMOJI_PAYLOAD)]) as urlopen:
        result = run(emojis.fetch_guild_emoji("10", "1"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/emojis/1"
    assert isinstance(result, Emoji)


def test_create_guild_emoji_posts_name_image_and_roles():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_EMOJI_PAYLOAD)]) as urlopen:
        result = run(emojis.create_guild_emoji("10", "shiv_dance", "data:...", roles=["1"]))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/emojis"
    assert json.loads(req.data) == {"name": "shiv_dance", "image": "data:...", "roles": ["1"]}
    assert isinstance(result, Emoji)


def test_edit_guild_emoji_only_sends_fields_that_were_set():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_EMOJI_PAYLOAD)]) as urlopen:
        run(emojis.edit_guild_emoji("10", "1", name="renamed"))

    assert json.loads(urlopen.call_args.args[0].data) == {"name": "renamed"}


def test_delete_guild_emoji_deletes_emoji():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(emojis.delete_guild_emoji("10", "1"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/emojis/1"
    assert req.get_method() == "DELETE"


# --- application emojis ---


def test_fetch_application_emojis_unwraps_items_key():
    payload = {"items": [_EMOJI_PAYLOAD]}
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(payload)]) as urlopen:
        result = run(emojis.fetch_application_emojis("app-1"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/applications/app-1/emojis"
    assert len(result) == 1
    assert result[0]._data["application_id"] == "app-1"


def test_fetch_application_emoji_returns_single_emoji():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_EMOJI_PAYLOAD)]) as urlopen:
        result = run(emojis.fetch_application_emoji("app-1", "1"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/applications/app-1/emojis/1"
    assert isinstance(result, Emoji)


def test_create_application_emoji_posts_name_and_image():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_EMOJI_PAYLOAD)]) as urlopen:
        result = run(emojis.create_application_emoji("app-1", "shiv_dance", "data:..."))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/applications/app-1/emojis"
    assert json.loads(req.data) == {"name": "shiv_dance", "image": "data:..."}
    assert isinstance(result, Emoji)


def test_edit_application_emoji_patches_name():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_EMOJI_PAYLOAD)]) as urlopen:
        run(emojis.edit_application_emoji("app-1", "1", name="renamed"))

    assert json.loads(urlopen.call_args.args[0].data) == {"name": "renamed"}


def test_delete_application_emoji_deletes_emoji():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(emojis.delete_application_emoji("app-1", "1"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/applications/app-1/emojis/1"
    assert req.get_method() == "DELETE"


# --- bot.<verb>() delegation ---


def test_bot_fetch_guild_emojis_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_EMOJI_PAYLOAD])]):
        assert len(run(bot.fetch_guild_emojis("10"))) == 1


def test_bot_fetch_guild_emoji_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_EMOJI_PAYLOAD)]):
        assert isinstance(run(bot.fetch_guild_emoji("10", "1")), Emoji)


def test_bot_create_guild_emoji_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_EMOJI_PAYLOAD)]):
        assert isinstance(run(bot.create_guild_emoji("10", "shiv_dance", "data:...")), Emoji)


def test_bot_edit_guild_emoji_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_EMOJI_PAYLOAD)]):
        assert isinstance(run(bot.edit_guild_emoji("10", "1", name="renamed")), Emoji)


def test_bot_delete_guild_emoji_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(bot.delete_guild_emoji("10", "1"))
    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/emojis/1"


def test_bot_fetch_application_emojis_delegates_to_rest_module():
    bot = Cordless()
    payload = {"items": [_EMOJI_PAYLOAD]}
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(payload)]):
        assert len(run(bot.fetch_application_emojis("app-1"))) == 1


def test_bot_fetch_application_emoji_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_EMOJI_PAYLOAD)]):
        assert isinstance(run(bot.fetch_application_emoji("app-1", "1")), Emoji)


def test_bot_create_application_emoji_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_EMOJI_PAYLOAD)]):
        assert isinstance(run(bot.create_application_emoji("app-1", "shiv_dance", "data:...")), Emoji)


def test_bot_edit_application_emoji_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_EMOJI_PAYLOAD)]):
        assert isinstance(run(bot.edit_application_emoji("app-1", "1", name="renamed")), Emoji)


def test_bot_delete_application_emoji_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(bot.delete_application_emoji("app-1", "1"))
    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/applications/app-1/emojis/1"


# --- guild.*() object-method delegation ---


def test_guild_fetch_emojis_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_EMOJI_PAYLOAD])]) as urlopen:
        result = run(guild.fetch_emojis())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/emojis"
    assert len(result) == 1


def test_guild_fetch_emoji_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_EMOJI_PAYLOAD)]):
        assert isinstance(run(guild.fetch_emoji("1")), Emoji)


def test_guild_create_emoji_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_EMOJI_PAYLOAD)]) as urlopen:
        result = run(guild.create_emoji("shiv_dance", "data:..."))

    assert json.loads(urlopen.call_args.args[0].data) == {"name": "shiv_dance", "image": "data:..."}
    assert isinstance(result, Emoji)


# --- emoji.*() object-method delegation ---


def test_emoji_edit_uses_guild_scope_when_guild_id_present():
    emoji = Emoji(dict(_EMOJI_PAYLOAD, guild_id="10"))
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_EMOJI_PAYLOAD)]) as urlopen:
        result = run(emoji.edit(name="renamed"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/emojis/1"
    assert isinstance(result, Emoji)


def test_emoji_edit_uses_application_scope_when_no_guild_id():
    emoji = Emoji(dict(_EMOJI_PAYLOAD, application_id="app-1"))
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_EMOJI_PAYLOAD)]) as urlopen:
        result = run(emoji.edit(name="renamed"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/applications/app-1/emojis/1"
    assert isinstance(result, Emoji)


def test_emoji_delete_uses_guild_scope_when_guild_id_present():
    emoji = Emoji(dict(_EMOJI_PAYLOAD, guild_id="10"))
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(emoji.delete())

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/emojis/1"
    assert req.get_method() == "DELETE"


def test_emoji_delete_uses_application_scope_when_no_guild_id():
    emoji = Emoji(dict(_EMOJI_PAYLOAD, application_id="app-1"))
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(emoji.delete())

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/applications/app-1/emojis/1"
    assert req.get_method() == "DELETE"
