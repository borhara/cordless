"""_rest/application.py: application REST endpoints, plus their bot.<verb>()
and Application object-method delegation."""

import json
import os
from asyncio import run
from unittest.mock import patch

from conftest import BOT_ENV, FakeDiscordResponse, send_patch

from cordless._rest import application
from cordless._rest.models import Application, ApplicationRoleConnectionMetadata
from cordless.app import Cordless

_APPLICATION_PAYLOAD = {"id": "3", "name": "shiv's bot", "bot_public": True, "flags": 0}
_METADATA_RECORD = {"type": 1, "key": "wins", "name": "Wins", "description": "Total wins"}


# --- _rest/application.py ---


def test_fetch_current_application_returns_application():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_APPLICATION_PAYLOAD)]) as urlopen:
        result = run(application.fetch_current_application())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/applications/@me"
    assert isinstance(result, Application)


def test_edit_current_application_only_sends_fields_that_were_set():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_APPLICATION_PAYLOAD)]) as urlopen:
        result = run(application.edit_current_application(description="a shiv original", tags=["fun", "utility"]))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/applications/@me"
    assert req.get_method() == "PATCH"
    assert json.loads(req.data) == {"description": "a shiv original", "tags": ["fun", "utility"]}
    assert isinstance(result, Application)


def test_fetch_application_role_connection_metadata_returns_records():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_METADATA_RECORD])]) as urlopen:
        result = run(application.fetch_application_role_connection_metadata("3"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/applications/3/role-connections/metadata"
    assert result == [ApplicationRoleConnectionMetadata(_METADATA_RECORD)]


def test_fetch_application_role_connection_metadata_handles_null_body():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]):
        assert run(application.fetch_application_role_connection_metadata("3")) == []


def test_edit_application_role_connection_metadata_sends_full_record_list():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_METADATA_RECORD])]) as urlopen:
        result = run(application.edit_application_role_connection_metadata("3", [_METADATA_RECORD]))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/applications/3/role-connections/metadata"
    assert req.get_method() == "PUT"
    assert json.loads(req.data) == [_METADATA_RECORD]
    assert result == [ApplicationRoleConnectionMetadata(_METADATA_RECORD)]


# --- bot.<verb>() delegation ---


def test_bot_fetch_application_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_APPLICATION_PAYLOAD)]):
        assert isinstance(run(bot.fetch_application()), Application)


def test_bot_edit_application_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_APPLICATION_PAYLOAD)]):
        assert isinstance(run(bot.edit_application(description="a shiv original")), Application)


def test_bot_fetch_application_role_connection_metadata_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_METADATA_RECORD])]):
        assert run(bot.fetch_application_role_connection_metadata("3")) == [
            ApplicationRoleConnectionMetadata(_METADATA_RECORD)
        ]


def test_bot_edit_application_role_connection_metadata_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_METADATA_RECORD])]):
        assert run(bot.edit_application_role_connection_metadata("3", [_METADATA_RECORD])) == [
            ApplicationRoleConnectionMetadata(_METADATA_RECORD)
        ]


# --- application.*() object-method delegation ---


def test_application_edit_delegates_to_rest_module():
    app = Application(_APPLICATION_PAYLOAD)
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_APPLICATION_PAYLOAD)]) as urlopen:
        result = run(app.edit(description="a shiv original"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/applications/@me"
    assert json.loads(req.data) == {"description": "a shiv original"}
    assert isinstance(result, Application)
