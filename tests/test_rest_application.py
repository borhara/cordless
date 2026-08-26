"""_rest/application.py: application REST endpoints, plus their bot.<verb>()
and Application object-method delegation."""

import json
import os
from asyncio import run
from unittest.mock import patch

from conftest import FakeDiscordResponse

from cordless._rest import application
from cordless._rest.models import Application
from cordless.app import Cordless

_ENV = {"DISCORD_BOT_TOKEN": "tok"}

_APPLICATION_PAYLOAD = {"id": "3", "name": "shiv's bot", "bot_public": True, "flags": 0}


def _urlopen(responses):
    return patch("cordless._rest._client.urllib.request.urlopen", side_effect=responses)


# --- _rest/application.py ---


def test_fetch_current_application_returns_application():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_APPLICATION_PAYLOAD)]) as urlopen:
        result = run(application.fetch_current_application())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/applications/@me"
    assert isinstance(result, Application)


def test_edit_current_application_only_sends_fields_that_were_set():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_APPLICATION_PAYLOAD)]) as urlopen:
        result = run(application.edit_current_application(description="a shiv original", tags=["fun", "utility"]))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/applications/@me"
    assert req.get_method() == "PATCH"
    assert json.loads(req.data) == {"description": "a shiv original", "tags": ["fun", "utility"]}
    assert isinstance(result, Application)


# --- bot.<verb>() delegation ---


def test_bot_fetch_application_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_APPLICATION_PAYLOAD)]):
        assert isinstance(run(bot.fetch_application()), Application)


def test_bot_edit_application_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_APPLICATION_PAYLOAD)]):
        assert isinstance(run(bot.edit_application(description="a shiv original")), Application)


# --- application.*() object-method delegation ---


def test_application_edit_delegates_to_rest_module():
    app = Application(_APPLICATION_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_APPLICATION_PAYLOAD)]) as urlopen:
        result = run(app.edit(description="a shiv original"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/applications/@me"
    assert json.loads(req.data) == {"description": "a shiv original"}
    assert isinstance(result, Application)
