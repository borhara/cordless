"""_rest/stage_instances.py: stage instance REST endpoints, plus their
bot.<verb>() and Channel/StageInstance object-method delegation."""

import json
import os
from asyncio import run
from unittest.mock import patch

from conftest import BOT_ENV, FakeDiscordResponse, send_patch

from cordless._rest import stage_instances
from cordless._rest.models import StageInstance
from cordless.app import Cordless
from cordless.models import Channel

_STAGE_PAYLOAD = {
    "id": "1",
    "guild_id": "10",
    "channel_id": "20",
    "topic": "shiv's stage",
    "privacy_level": 2,
}


# --- _rest/stage_instances.py ---


def test_create_stage_instance_posts_required_and_optional_fields():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_STAGE_PAYLOAD)]) as urlopen:
        result = run(stage_instances.create_stage_instance("20", "shiv's stage", privacy_level=2))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/stage-instances"
    assert json.loads(req.data) == {"channel_id": "20", "topic": "shiv's stage", "privacy_level": 2}
    assert isinstance(result, StageInstance)


def test_fetch_stage_instance_returns_stage_instance():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_STAGE_PAYLOAD)]) as urlopen:
        result = run(stage_instances.fetch_stage_instance("20"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/stage-instances/20"
    assert isinstance(result, StageInstance)


def test_edit_stage_instance_only_sends_fields_that_were_set():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_STAGE_PAYLOAD)]) as urlopen:
        result = run(stage_instances.edit_stage_instance("20", topic="new topic"))

    assert json.loads(urlopen.call_args.args[0].data) == {"topic": "new topic"}
    assert isinstance(result, StageInstance)


def test_delete_stage_instance_deletes_stage():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(stage_instances.delete_stage_instance("20"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/stage-instances/20"
    assert req.get_method() == "DELETE"


# --- bot.<verb>() delegation ---


def test_bot_create_stage_instance_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_STAGE_PAYLOAD)]):
        assert isinstance(run(bot.create_stage_instance("20", "shiv's stage")), StageInstance)


def test_bot_fetch_stage_instance_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_STAGE_PAYLOAD)]):
        assert isinstance(run(bot.fetch_stage_instance("20")), StageInstance)


def test_bot_edit_stage_instance_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_STAGE_PAYLOAD)]):
        assert isinstance(run(bot.edit_stage_instance("20", topic="new topic")), StageInstance)


def test_bot_delete_stage_instance_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(bot.delete_stage_instance("20"))
    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/stage-instances/20"


# --- channel.*() object-method delegation ---


def test_channel_create_stage_instance_delegates_to_rest_module():
    channel = Channel({"id": "20"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_STAGE_PAYLOAD)]) as urlopen:
        result = run(channel.create_stage_instance("shiv's stage"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/stage-instances"
    assert json.loads(req.data) == {"channel_id": "20", "topic": "shiv's stage"}
    assert isinstance(result, StageInstance)


def test_channel_fetch_stage_instance_delegates_to_rest_module():
    channel = Channel({"id": "20"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_STAGE_PAYLOAD)]) as urlopen:
        result = run(channel.fetch_stage_instance())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/stage-instances/20"
    assert isinstance(result, StageInstance)


# --- stage_instance.*() object-method delegation ---


def test_stage_instance_edit_delegates_to_rest_module():
    stage = StageInstance(_STAGE_PAYLOAD)
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_STAGE_PAYLOAD)]) as urlopen:
        result = run(stage.edit(topic="new topic"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/stage-instances/20"
    assert json.loads(req.data) == {"topic": "new topic"}
    assert isinstance(result, StageInstance)


def test_stage_instance_delete_delegates_to_rest_module():
    stage = StageInstance(_STAGE_PAYLOAD)
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(stage.delete())

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/stage-instances/20"
    assert req.get_method() == "DELETE"
