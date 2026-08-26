"""_rest/application_commands.py: application command REST endpoints, plus
their bot.<verb>() and ApplicationCommand object-method delegation."""

import json
import os
from asyncio import run
from unittest.mock import patch

from conftest import FakeDiscordResponse

from cordless._rest import application_commands
from cordless._rest.models import ApplicationCommand, GuildApplicationCommandPermissions
from cordless.app import Cordless

_ENV = {"DISCORD_BOT_TOKEN": "tok"}

_GLOBAL_COMMAND_PAYLOAD = {"id": "1", "application_id": "3", "name": "shiv-cmd", "description": "shiv's command"}
_GUILD_COMMAND_PAYLOAD = {
    "id": "2",
    "application_id": "3",
    "guild_id": "10",
    "name": "shiv-guild-cmd",
    "description": "shiv's guild command",
}
_PERMISSIONS_PAYLOAD = {"id": "2", "application_id": "3", "guild_id": "10", "permissions": []}


def _urlopen(responses):
    return patch("cordless._rest._client._send", side_effect=responses)


# --- global commands ---


def test_fetch_global_commands_returns_command_list():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_GLOBAL_COMMAND_PAYLOAD])]) as urlopen:
        result = run(application_commands.fetch_global_commands("3"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/applications/3/commands"
    assert result == [ApplicationCommand(_GLOBAL_COMMAND_PAYLOAD)]


def test_fetch_global_commands_with_localizations_adds_query_string():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([])]) as urlopen:
        run(application_commands.fetch_global_commands("3", with_localizations=True))

    assert urlopen.call_args.args[0].full_url.endswith("?with_localizations=true")


def test_create_global_command_posts_required_and_optional_fields():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_GLOBAL_COMMAND_PAYLOAD)]) as urlopen:
        result = run(application_commands.create_global_command("3", "shiv-cmd", description="shiv's command"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/applications/3/commands"
    assert json.loads(req.data) == {"name": "shiv-cmd", "description": "shiv's command"}
    assert isinstance(result, ApplicationCommand)


def test_fetch_global_command_returns_single_command():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_GLOBAL_COMMAND_PAYLOAD)]) as urlopen:
        result = run(application_commands.fetch_global_command("3", "1"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/applications/3/commands/1"
    assert isinstance(result, ApplicationCommand)


def test_edit_global_command_only_sends_fields_that_were_set():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_GLOBAL_COMMAND_PAYLOAD)]) as urlopen:
        result = run(application_commands.edit_global_command("3", "1", description="new description"))

    assert json.loads(urlopen.call_args.args[0].data) == {"description": "new description"}
    assert isinstance(result, ApplicationCommand)


def test_delete_global_command_deletes_command():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(application_commands.delete_global_command("3", "1"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/applications/3/commands/1"
    assert req.get_method() == "DELETE"


def test_bulk_overwrite_global_commands_puts_command_list():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_GLOBAL_COMMAND_PAYLOAD])]) as urlopen:
        result = run(application_commands.bulk_overwrite_global_commands("3", [{"name": "shiv-cmd"}]))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/applications/3/commands"
    assert req.get_method() == "PUT"
    assert json.loads(req.data) == [{"name": "shiv-cmd"}]
    assert result == [ApplicationCommand(_GLOBAL_COMMAND_PAYLOAD)]


# --- guild commands ---


def test_fetch_guild_commands_returns_command_list():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_GUILD_COMMAND_PAYLOAD])]) as urlopen:
        result = run(application_commands.fetch_guild_commands("3", "10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/applications/3/guilds/10/commands"
    assert result == [ApplicationCommand(_GUILD_COMMAND_PAYLOAD)]


def test_create_guild_command_posts_required_and_optional_fields():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_GUILD_COMMAND_PAYLOAD)]) as urlopen:
        result = run(application_commands.create_guild_command("3", "10", "shiv-guild-cmd"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/applications/3/guilds/10/commands"
    assert json.loads(req.data) == {"name": "shiv-guild-cmd"}
    assert isinstance(result, ApplicationCommand)


def test_fetch_guild_command_returns_single_command():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_GUILD_COMMAND_PAYLOAD)]) as urlopen:
        result = run(application_commands.fetch_guild_command("3", "10", "2"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/applications/3/guilds/10/commands/2"
    assert isinstance(result, ApplicationCommand)


def test_edit_guild_command_only_sends_fields_that_were_set():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_GUILD_COMMAND_PAYLOAD)]) as urlopen:
        result = run(application_commands.edit_guild_command("3", "10", "2", name="new-name"))

    assert json.loads(urlopen.call_args.args[0].data) == {"name": "new-name"}
    assert isinstance(result, ApplicationCommand)


def test_delete_guild_command_deletes_command():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(application_commands.delete_guild_command("3", "10", "2"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/applications/3/guilds/10/commands/2"
    assert req.get_method() == "DELETE"


def test_bulk_overwrite_guild_commands_puts_command_list():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_GUILD_COMMAND_PAYLOAD])]) as urlopen:
        result = run(application_commands.bulk_overwrite_guild_commands("3", "10", [{"name": "shiv-guild-cmd"}]))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/applications/3/guilds/10/commands"
    assert req.get_method() == "PUT"
    assert result == [ApplicationCommand(_GUILD_COMMAND_PAYLOAD)]


# --- permissions ---


def test_fetch_guild_command_permissions_returns_permission_list():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_PERMISSIONS_PAYLOAD])]) as urlopen:
        result = run(application_commands.fetch_guild_command_permissions("3", "10"))

    assert (
        urlopen.call_args.args[0].full_url
        == "https://discord.com/api/v10/applications/3/guilds/10/commands/permissions"
    )
    assert result == [GuildApplicationCommandPermissions(_PERMISSIONS_PAYLOAD)]


def test_fetch_command_permissions_returns_single_permissions_object():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_PERMISSIONS_PAYLOAD)]) as urlopen:
        result = run(application_commands.fetch_command_permissions("3", "10", "2"))

    url = urlopen.call_args.args[0].full_url
    assert url == "https://discord.com/api/v10/applications/3/guilds/10/commands/2/permissions"
    assert isinstance(result, GuildApplicationCommandPermissions)


# --- bot.<verb>() delegation ---


def test_bot_fetch_global_commands_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_GLOBAL_COMMAND_PAYLOAD])]):
        assert run(bot.fetch_global_commands("3")) == [ApplicationCommand(_GLOBAL_COMMAND_PAYLOAD)]


def test_bot_create_global_command_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_GLOBAL_COMMAND_PAYLOAD)]):
        assert isinstance(run(bot.create_global_command("3", "shiv-cmd")), ApplicationCommand)


def test_bot_fetch_global_command_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_GLOBAL_COMMAND_PAYLOAD)]):
        assert isinstance(run(bot.fetch_global_command("3", "1")), ApplicationCommand)


def test_bot_edit_global_command_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_GLOBAL_COMMAND_PAYLOAD)]):
        assert isinstance(run(bot.edit_global_command("3", "1", name="new-name")), ApplicationCommand)


def test_bot_delete_global_command_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(bot.delete_global_command("3", "1"))
    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/applications/3/commands/1"


def test_bot_bulk_overwrite_global_commands_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_GLOBAL_COMMAND_PAYLOAD])]):
        result = run(bot.bulk_overwrite_global_commands("3", [{"name": "shiv-cmd"}]))
    assert result == [ApplicationCommand(_GLOBAL_COMMAND_PAYLOAD)]


def test_bot_fetch_guild_commands_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_GUILD_COMMAND_PAYLOAD])]):
        assert run(bot.fetch_guild_commands("3", "10")) == [ApplicationCommand(_GUILD_COMMAND_PAYLOAD)]


def test_bot_create_guild_command_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_GUILD_COMMAND_PAYLOAD)]):
        assert isinstance(run(bot.create_guild_command("3", "10", "shiv-guild-cmd")), ApplicationCommand)


def test_bot_fetch_guild_command_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_GUILD_COMMAND_PAYLOAD)]):
        assert isinstance(run(bot.fetch_guild_command("3", "10", "2")), ApplicationCommand)


def test_bot_edit_guild_command_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_GUILD_COMMAND_PAYLOAD)]):
        assert isinstance(run(bot.edit_guild_command("3", "10", "2", name="new-name")), ApplicationCommand)


def test_bot_delete_guild_command_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(bot.delete_guild_command("3", "10", "2"))
    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/applications/3/guilds/10/commands/2"


def test_bot_bulk_overwrite_guild_commands_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_GUILD_COMMAND_PAYLOAD])]):
        result = run(bot.bulk_overwrite_guild_commands("3", "10", [{"name": "shiv-guild-cmd"}]))
    assert result == [ApplicationCommand(_GUILD_COMMAND_PAYLOAD)]


def test_bot_fetch_guild_command_permissions_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_PERMISSIONS_PAYLOAD])]):
        result = run(bot.fetch_guild_command_permissions("3", "10"))
    assert result == [GuildApplicationCommandPermissions(_PERMISSIONS_PAYLOAD)]


def test_bot_fetch_command_permissions_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_PERMISSIONS_PAYLOAD)]):
        assert isinstance(run(bot.fetch_command_permissions("3", "10", "2")), GuildApplicationCommandPermissions)


# --- command.*() object-method delegation ---


def test_global_command_edit_delegates_to_global_edit():
    command = ApplicationCommand(_GLOBAL_COMMAND_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_GLOBAL_COMMAND_PAYLOAD)]) as urlopen:
        result = run(command.edit(name="new-name"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/applications/3/commands/1"
    assert json.loads(req.data) == {"name": "new-name"}
    assert isinstance(result, ApplicationCommand)


def test_guild_command_edit_delegates_to_guild_edit():
    command = ApplicationCommand(_GUILD_COMMAND_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_GUILD_COMMAND_PAYLOAD)]) as urlopen:
        result = run(command.edit(name="new-name"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/applications/3/guilds/10/commands/2"
    assert isinstance(result, ApplicationCommand)


def test_global_command_delete_delegates_to_global_delete():
    command = ApplicationCommand(_GLOBAL_COMMAND_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(command.delete())

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/applications/3/commands/1"
    assert req.get_method() == "DELETE"


def test_guild_command_delete_delegates_to_guild_delete():
    command = ApplicationCommand(_GUILD_COMMAND_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(command.delete())

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/applications/3/guilds/10/commands/2"
    assert req.get_method() == "DELETE"


def test_guild_command_fetch_permissions_delegates_to_rest_module():
    command = ApplicationCommand(_GUILD_COMMAND_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_PERMISSIONS_PAYLOAD)]) as urlopen:
        result = run(command.fetch_permissions())

    url = urlopen.call_args.args[0].full_url
    assert url == "https://discord.com/api/v10/applications/3/guilds/10/commands/2/permissions"
    assert isinstance(result, GuildApplicationCommandPermissions)
