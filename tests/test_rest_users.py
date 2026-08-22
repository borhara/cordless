"""_rest/users.py: user REST endpoints, plus their bot.<verb>() and
User/Guild object-method delegation."""

import json
import os
from asyncio import run
from unittest.mock import patch

from conftest import FakeDiscordResponse

from cordless._rest import users
from cordless.app import Cordless
from cordless.models import Channel, Guild, Member, User

_ENV = {"DISCORD_BOT_TOKEN": "tok"}

_USER_PAYLOAD = {"id": "55", "username": "shiv"}
_GUILD_PAYLOAD = {"id": "10", "name": "shiv's guild"}
_MEMBER_PAYLOAD = {"nick": "shiv"}
_CHANNEL_PAYLOAD = {"id": "20", "type": 1}


def _urlopen(responses):
    return patch("cordless._rest._client.urllib.request.urlopen", side_effect=responses)


# --- _rest/users.py ---


def test_fetch_current_user_returns_user():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_USER_PAYLOAD)]) as urlopen:
        result = run(users.fetch_current_user())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/users/@me"
    assert isinstance(result, User)


def test_fetch_user_returns_user():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_USER_PAYLOAD)]) as urlopen:
        result = run(users.fetch_user("55"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/users/55"
    assert isinstance(result, User)


def test_edit_current_user_only_sends_fields_that_were_set():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_USER_PAYLOAD)]) as urlopen:
        result = run(users.edit_current_user(username="new name"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/users/@me"
    assert json.loads(req.data) == {"username": "new name"}
    assert isinstance(result, User)


def test_fetch_current_user_guilds_returns_guild_list():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_GUILD_PAYLOAD])]) as urlopen:
        result = run(users.fetch_current_user_guilds())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/users/@me/guilds"
    assert result == [Guild(_GUILD_PAYLOAD)]


def test_fetch_current_user_guilds_passes_query_params():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([])]) as urlopen:
        run(users.fetch_current_user_guilds(before="90", after="10", limit=5, with_counts=True))

    url = urlopen.call_args.args[0].full_url
    assert "before=90" in url
    assert "after=10" in url
    assert "limit=5" in url
    assert "with_counts=true" in url


def test_fetch_current_user_guild_member_returns_member_with_guild_id():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MEMBER_PAYLOAD)]) as urlopen:
        result = run(users.fetch_current_user_guild_member("10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/users/@me/guilds/10/member"
    assert isinstance(result, Member)
    assert result.guild_id == "10"


def test_leave_guild_leaves_guild():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(users.leave_guild("10"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/users/@me/guilds/10"
    assert req.get_method() == "DELETE"


def test_create_dm_returns_channel():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_CHANNEL_PAYLOAD)]) as urlopen:
        result = run(users.create_dm("55"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/users/@me/channels"
    assert json.loads(req.data) == {"recipient_id": "55"}
    assert isinstance(result, Channel)


# --- bot.<verb>() delegation ---


def test_bot_fetch_current_user_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_USER_PAYLOAD)]):
        assert isinstance(run(bot.fetch_current_user()), User)


def test_bot_fetch_user_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_USER_PAYLOAD)]):
        assert isinstance(run(bot.fetch_user("55")), User)


def test_bot_edit_current_user_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_USER_PAYLOAD)]):
        assert isinstance(run(bot.edit_current_user(username="new name")), User)


def test_bot_fetch_current_user_guilds_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_GUILD_PAYLOAD])]):
        assert run(bot.fetch_current_user_guilds()) == [Guild(_GUILD_PAYLOAD)]


def test_bot_fetch_current_user_guild_member_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MEMBER_PAYLOAD)]):
        assert isinstance(run(bot.fetch_current_user_guild_member("10")), Member)


def test_bot_leave_guild_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(bot.leave_guild("10"))
    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/users/@me/guilds/10"


def test_bot_create_dm_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_CHANNEL_PAYLOAD)]):
        assert isinstance(run(bot.create_dm("55")), Channel)


# --- user.*() object-method delegation ---


def test_user_fetch_delegates_to_rest_module():
    user = User(_USER_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_USER_PAYLOAD)]) as urlopen:
        result = run(user.fetch())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/users/55"
    assert isinstance(result, User)


def test_user_create_dm_delegates_to_rest_module():
    user = User(_USER_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_CHANNEL_PAYLOAD)]) as urlopen:
        result = run(user.create_dm())

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/users/@me/channels"
    assert json.loads(req.data) == {"recipient_id": "55"}
    assert isinstance(result, Channel)


# --- guild.*() object-method delegation ---


def test_guild_fetch_current_member_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MEMBER_PAYLOAD)]) as urlopen:
        result = run(guild.fetch_current_member())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/users/@me/guilds/10/member"
    assert isinstance(result, Member)


def test_guild_leave_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(guild.leave())

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/users/@me/guilds/10"
    assert req.get_method() == "DELETE"
