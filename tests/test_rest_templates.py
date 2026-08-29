"""_rest/templates.py: guild template REST endpoints, plus their
bot.<verb>() and Guild/GuildTemplate object-method delegation."""

import json
import os
from asyncio import run
from unittest.mock import patch

from conftest import FakeDiscordResponse

from cordless._rest import templates
from cordless._rest.models import GuildTemplate
from cordless.app import Cordless
from cordless.models import Guild, User

_ENV = {"DISCORD_BOT_TOKEN": "tok"}

_TEMPLATE_PAYLOAD = {
    "code": "abc123",
    "name": "shiv's template",
    "description": "",
    "usage_count": 0,
    "creator_id": "55",
    "creator": {"id": "55", "username": "shiv"},
    "source_guild_id": "10",
    "serialized_source_guild": {"name": "shiv's guild"},
    "is_dirty": None,
}


def _urlopen(responses):
    return patch("cordless._rest._client._send", side_effect=responses)


# --- _rest/templates.py ---


def test_fetch_template_returns_template():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_TEMPLATE_PAYLOAD)]) as urlopen:
        result = run(templates.fetch_template("abc123"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/templates/abc123"
    assert isinstance(result, GuildTemplate)


def test_fetch_guild_templates_returns_template_list():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_TEMPLATE_PAYLOAD])]) as urlopen:
        result = run(templates.fetch_guild_templates("10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/templates"
    assert result == [GuildTemplate(_TEMPLATE_PAYLOAD)]


def test_create_guild_template_posts_required_and_optional_fields():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_TEMPLATE_PAYLOAD)]) as urlopen:
        result = run(templates.create_guild_template("10", "shiv's template", description="a template"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/templates"
    assert json.loads(req.data) == {"name": "shiv's template", "description": "a template"}
    assert isinstance(result, GuildTemplate)


def test_sync_guild_template_syncs_template():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_TEMPLATE_PAYLOAD)]) as urlopen:
        result = run(templates.sync_guild_template("10", "abc123"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/templates/abc123"
    assert req.get_method() == "PUT"
    assert isinstance(result, GuildTemplate)


def test_edit_guild_template_only_sends_fields_that_were_set():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_TEMPLATE_PAYLOAD)]) as urlopen:
        result = run(templates.edit_guild_template("10", "abc123", name="new name"))

    assert json.loads(urlopen.call_args.args[0].data) == {"name": "new name"}
    assert isinstance(result, GuildTemplate)


def test_delete_guild_template_returns_deleted_template():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_TEMPLATE_PAYLOAD)]) as urlopen:
        result = run(templates.delete_guild_template("10", "abc123"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/templates/abc123"
    assert req.get_method() == "DELETE"
    assert isinstance(result, GuildTemplate)


# --- bot.<verb>() delegation ---


def test_bot_fetch_template_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_TEMPLATE_PAYLOAD)]):
        assert isinstance(run(bot.fetch_template("abc123")), GuildTemplate)


def test_bot_fetch_guild_templates_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_TEMPLATE_PAYLOAD])]):
        assert run(bot.fetch_guild_templates("10")) == [GuildTemplate(_TEMPLATE_PAYLOAD)]


def test_bot_create_guild_template_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_TEMPLATE_PAYLOAD)]):
        assert isinstance(run(bot.create_guild_template("10", "shiv's template")), GuildTemplate)


def test_bot_sync_guild_template_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_TEMPLATE_PAYLOAD)]):
        assert isinstance(run(bot.sync_guild_template("10", "abc123")), GuildTemplate)


def test_bot_edit_guild_template_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_TEMPLATE_PAYLOAD)]):
        assert isinstance(run(bot.edit_guild_template("10", "abc123", name="new name")), GuildTemplate)


def test_bot_delete_guild_template_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_TEMPLATE_PAYLOAD)]) as urlopen:
        run(bot.delete_guild_template("10", "abc123"))
    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/templates/abc123"


# --- guild.*() object-method delegation ---


def test_guild_fetch_templates_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_TEMPLATE_PAYLOAD])]) as urlopen:
        result = run(guild.fetch_templates())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/templates"
    assert result == [GuildTemplate(_TEMPLATE_PAYLOAD)]


def test_guild_create_template_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_TEMPLATE_PAYLOAD)]) as urlopen:
        result = run(guild.create_template("shiv's template"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/templates"
    assert isinstance(result, GuildTemplate)


# --- template.*() object-method delegation ---


def test_template_creator_returns_user():
    template = GuildTemplate(_TEMPLATE_PAYLOAD)
    assert isinstance(template.creator, User)
    assert template.creator.username == "shiv"


def test_template_sync_delegates_to_rest_module():
    template = GuildTemplate(_TEMPLATE_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_TEMPLATE_PAYLOAD)]) as urlopen:
        result = run(template.sync())

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/templates/abc123"
    assert req.get_method() == "PUT"
    assert isinstance(result, GuildTemplate)


def test_template_edit_delegates_to_rest_module():
    template = GuildTemplate(_TEMPLATE_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_TEMPLATE_PAYLOAD)]) as urlopen:
        result = run(template.edit(name="new name"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/templates/abc123"
    assert json.loads(req.data) == {"name": "new name"}
    assert isinstance(result, GuildTemplate)


def test_template_delete_delegates_to_rest_module():
    template = GuildTemplate(_TEMPLATE_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_TEMPLATE_PAYLOAD)]) as urlopen:
        result = run(template.delete())

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/templates/abc123"
    assert req.get_method() == "DELETE"
    assert isinstance(result, GuildTemplate)
