"""_rest/invites.py: standalone invite REST endpoints, plus their bot.<verb>()
and Invite object-method delegation."""

import os
from asyncio import run
from unittest.mock import patch

from conftest import FakeDiscordResponse

from cordless._rest import invites
from cordless._rest.models import Invite, TargetUsersJobStatus
from cordless.app import Cordless

_ENV = {"DISCORD_BOT_TOKEN": "tok"}

_INVITE_PAYLOAD = {"code": "shivs-server", "guild_id": "10", "channel_id": "20"}
_JOB_STATUS_PAYLOAD = {
    "status": "COMPLETED",
    "total_users": 3,
    "processed_users": 3,
    "created_at": "2024-01-01T00:00:00Z",
    "completed_at": "2024-01-01T00:01:00Z",
    "error_message": None,
}


class _RawResponse:
    """Unlike FakeDiscordResponse, doesn't JSON-encode its body - for
    endpoints that answer with raw CSV instead of JSON."""

    def __init__(self, body):
        self._body = body
        self.headers = {}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


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


def test_fetch_invite_target_users_returns_raw_csv():
    with patch.dict(os.environ, _ENV), _urlopen([_RawResponse(b"user_id\n55\n")]) as urlopen:
        result = run(invites.fetch_invite_target_users("shivs-server"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/invites/shivs-server/target-users"
    assert result == "user_id\n55\n"


def test_edit_invite_target_users_uploads_csv_file():
    with patch.dict(os.environ, _ENV), _urlopen([_RawResponse(b"")]) as urlopen:
        run(invites.edit_invite_target_users("shivs-server", "users.csv", b"user_id\n55\n"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/invites/shivs-server/target-users"
    assert req.get_method() == "PUT"
    assert req.get_header("Content-type").startswith("multipart/form-data; boundary=")
    assert b'name="target_users_file"; filename="users.csv"' in req.data
    assert b"user_id\n55\n" in req.data


def test_fetch_invite_target_users_job_status_returns_status():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_JOB_STATUS_PAYLOAD)]) as urlopen:
        result = run(invites.fetch_invite_target_users_job_status("shivs-server"))

    assert (
        urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/invites/shivs-server/target-users/job-status"
    )
    assert isinstance(result, TargetUsersJobStatus)


def test_bot_fetch_invite_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_INVITE_PAYLOAD)]):
        assert isinstance(run(bot.fetch_invite("shivs-server")), Invite)


def test_bot_delete_invite_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_INVITE_PAYLOAD)]) as urlopen:
        run(bot.delete_invite("shivs-server"))

    assert urlopen.call_args.args[0].get_method() == "DELETE"


def test_bot_fetch_invite_target_users_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([_RawResponse(b"user_id\n55\n")]):
        assert run(bot.fetch_invite_target_users("shivs-server")) == "user_id\n55\n"


def test_bot_edit_invite_target_users_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([_RawResponse(b"")]) as urlopen:
        run(bot.edit_invite_target_users("shivs-server", "users.csv", b"user_id\n55\n"))

    assert urlopen.call_args.args[0].get_method() == "PUT"


def test_bot_fetch_invite_target_users_job_status_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_JOB_STATUS_PAYLOAD)]):
        assert isinstance(run(bot.fetch_invite_target_users_job_status("shivs-server")), TargetUsersJobStatus)


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


def test_invite_fetch_target_users_delegates_to_rest_module():
    invite = Invite(_INVITE_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([_RawResponse(b"user_id\n55\n")]) as urlopen:
        result = run(invite.fetch_target_users())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/invites/shivs-server/target-users"
    assert result == "user_id\n55\n"


def test_invite_edit_target_users_delegates_to_rest_module():
    invite = Invite(_INVITE_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([_RawResponse(b"")]) as urlopen:
        run(invite.edit_target_users("users.csv", b"user_id\n55\n"))

    assert urlopen.call_args.args[0].get_method() == "PUT"


def test_invite_fetch_target_users_job_status_delegates_to_rest_module():
    invite = Invite(_INVITE_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_JOB_STATUS_PAYLOAD)]) as urlopen:
        result = run(invite.fetch_target_users_job_status())

    assert (
        urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/invites/shivs-server/target-users/job-status"
    )
    assert isinstance(result, TargetUsersJobStatus)
