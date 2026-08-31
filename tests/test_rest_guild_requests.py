"""_rest/guild_requests.py: guild join request REST endpoints, plus their
bot.<verb>() and GuildJoinRequest object-method delegation."""

import json
import os
from asyncio import run
from unittest.mock import patch

from conftest import BOT_ENV, FakeDiscordResponse, send_patch

from cordless._rest import guild_requests
from cordless._rest.models import GuildJoinRequest
from cordless.app import Cordless

_REQUEST_PAYLOAD = {
    "id": "1",
    "guild_id": "10",
    "user_id": "55",
    "created_at": "2024-01-01T00:00:00Z",
    "application_status": "SUBMITTED",
}


# --- _rest/guild_requests.py ---


def test_fetch_guild_join_requests_returns_request_list():
    payload = {"total": 1, "guild_join_requests": [_REQUEST_PAYLOAD]}
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]) as urlopen:
        result = run(guild_requests.fetch_guild_join_requests("10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/requests"
    assert result == [GuildJoinRequest(_REQUEST_PAYLOAD)]


def test_fetch_guild_join_requests_passes_query_params():
    payload = {"total": 0, "guild_join_requests": []}
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]) as urlopen:
        run(guild_requests.fetch_guild_join_requests("10", status="SUBMITTED", limit=5))

    url = urlopen.call_args.args[0].full_url
    assert "status=SUBMITTED" in url
    assert "limit=5" in url


def test_edit_guild_join_request_approves():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_REQUEST_PAYLOAD)]) as urlopen:
        result = run(guild_requests.edit_guild_join_request("10", "1", "APPROVED"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/requests/1"
    assert req.get_method() == "PATCH"
    assert json.loads(req.data) == {"action": "APPROVED"}
    assert isinstance(result, GuildJoinRequest)


def test_edit_guild_join_request_rejects_with_reason():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_REQUEST_PAYLOAD)]) as urlopen:
        run(guild_requests.edit_guild_join_request("10", "1", "REJECTED", rejection_reason="not a fit"))

    assert json.loads(urlopen.call_args.args[0].data) == {"action": "REJECTED", "rejection_reason": "not a fit"}


# --- bot.<verb>() delegation ---


def test_bot_fetch_guild_join_requests_delegates_to_rest_module():
    bot = Cordless()
    payload = {"total": 1, "guild_join_requests": [_REQUEST_PAYLOAD]}
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]):
        assert run(bot.fetch_guild_join_requests("10")) == [GuildJoinRequest(_REQUEST_PAYLOAD)]


def test_bot_edit_guild_join_request_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_REQUEST_PAYLOAD)]):
        assert isinstance(run(bot.edit_guild_join_request("10", "1", "APPROVED")), GuildJoinRequest)


# --- request.*() object-method delegation ---


def test_request_user_is_none_when_absent():
    request = GuildJoinRequest(_REQUEST_PAYLOAD)
    assert request.user is None


def test_request_user_returns_user_when_present():
    request = GuildJoinRequest(dict(_REQUEST_PAYLOAD, user={"id": "55", "username": "shiv"}))
    assert request.user.username == "shiv"


def test_request_approve_delegates_to_rest_module():
    request = GuildJoinRequest(_REQUEST_PAYLOAD)
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_REQUEST_PAYLOAD)]) as urlopen:
        result = run(request.approve())

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/requests/1"
    assert json.loads(req.data) == {"action": "APPROVED"}
    assert isinstance(result, GuildJoinRequest)


def test_request_reject_delegates_to_rest_module():
    request = GuildJoinRequest(_REQUEST_PAYLOAD)
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_REQUEST_PAYLOAD)]) as urlopen:
        result = run(request.reject(rejection_reason="not a fit"))

    req = urlopen.call_args.args[0]
    assert json.loads(req.data) == {"action": "REJECTED", "rejection_reason": "not a fit"}
    assert isinstance(result, GuildJoinRequest)
