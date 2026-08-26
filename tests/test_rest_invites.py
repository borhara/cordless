"""_rest/invites.py: standalone invite REST endpoints, plus their bot.<verb>()
and Invite object-method delegation."""

import os
from asyncio import run
from unittest.mock import patch

from conftest import FakeDiscordResponse

from cordless._rest import invites
from cordless._rest.models import Invite
from cordless.app import Cordless

_ENV = {"DISCORD_BOT_TOKEN": "tok"}

_INVITE_PAYLOAD = {"code": "shivs-server", "guild_id": "10", "channel_id": "20"}


def _urlopen(responses):
    return patch("cordless._rest._client._send", side_effect=responses)


def test_fetch_invite_returns_invite():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_INVITE_PAYLOAD)]) as urlopen:
        result = run(invites.fetch_invite("shivs-server"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/invites/shivs-server"
    assert isinstance(result, Invite)
    assert result.url == "https://discord.gg/shivs-server"


def test_fetch_invite_passes_with_counts_and_scheduled_event_id():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_INVITE_PAYLOAD)]) as urlopen:
        run(invites.fetch_invite("shivs-server", with_counts=True, guild_scheduled_event_id="90"))

    url = urlopen.call_args.args[0].full_url
    assert "with_counts=true" in url
    assert "guild_scheduled_event_id=90" in url


def test_delete_invite_deletes_and_returns_invite():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_INVITE_PAYLOAD)]) as urlopen:
        result = run(invites.delete_invite("shivs-server"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/invites/shivs-server"
    assert req.get_method() == "DELETE"
    assert isinstance(result, Invite)


def test_bot_fetch_invite_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_INVITE_PAYLOAD)]):
        assert isinstance(run(bot.fetch_invite("shivs-server")), Invite)


def test_bot_delete_invite_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_INVITE_PAYLOAD)]) as urlopen:
        run(bot.delete_invite("shivs-server"))

    assert urlopen.call_args.args[0].get_method() == "DELETE"


def test_invite_fetch_delegates_to_rest_module():
    invite = Invite(_INVITE_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_INVITE_PAYLOAD)]) as urlopen:
        result = run(invite.fetch())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/invites/shivs-server"
    assert isinstance(result, Invite)


def test_invite_delete_delegates_to_rest_module():
    invite = Invite(_INVITE_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_INVITE_PAYLOAD)]) as urlopen:
        result = run(invite.delete())

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/invites/shivs-server"
    assert req.get_method() == "DELETE"
    assert isinstance(result, Invite)
