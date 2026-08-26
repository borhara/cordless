"""_rest/voice.py: voice REST endpoints, plus their bot.<verb>() and Guild
object-method delegation."""

import json
import os
from asyncio import run
from unittest.mock import patch

from conftest import FakeDiscordResponse

from cordless._rest import voice
from cordless._rest.models import VoiceRegion, VoiceState
from cordless.app import Cordless
from cordless.models import Guild

_ENV = {"DISCORD_BOT_TOKEN": "tok"}

_REGION_PAYLOAD = {"id": "us-east", "name": "US East", "optimal": True, "deprecated": False, "custom": False}
_VOICE_STATE_PAYLOAD = {
    "guild_id": "10",
    "channel_id": "20",
    "user_id": "55",
    "session_id": "abc",
    "deaf": False,
    "mute": False,
    "self_deaf": False,
    "self_mute": False,
    "suppress": False,
}


def _urlopen(responses):
    return patch("cordless._rest._client.urllib.request.urlopen", side_effect=responses)


# --- _rest/voice.py ---


def test_fetch_voice_regions_returns_region_list():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_REGION_PAYLOAD])]) as urlopen:
        result = run(voice.fetch_voice_regions())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/voice/regions"
    assert result == [VoiceRegion(_REGION_PAYLOAD)]


def test_fetch_current_user_voice_state_returns_voice_state():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_VOICE_STATE_PAYLOAD)]) as urlopen:
        result = run(voice.fetch_current_user_voice_state("10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/voice-states/@me"
    assert isinstance(result, VoiceState)


def test_fetch_user_voice_state_returns_voice_state():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_VOICE_STATE_PAYLOAD)]) as urlopen:
        result = run(voice.fetch_user_voice_state("10", "55"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/voice-states/55"
    assert isinstance(result, VoiceState)


def test_edit_current_user_voice_state_only_sends_fields_that_were_set():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(voice.edit_current_user_voice_state("10", request_to_speak_timestamp="2026-01-01T00:00:00+00:00"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/voice-states/@me"
    assert json.loads(req.data) == {"request_to_speak_timestamp": "2026-01-01T00:00:00+00:00"}


def test_edit_user_voice_state_only_sends_fields_that_were_set():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(voice.edit_user_voice_state("10", "55", suppress=False))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/voice-states/55"
    assert json.loads(req.data) == {"suppress": False}


# --- bot.<verb>() delegation ---


def test_bot_fetch_voice_regions_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_REGION_PAYLOAD])]):
        assert run(bot.fetch_voice_regions()) == [VoiceRegion(_REGION_PAYLOAD)]


def test_bot_fetch_guild_current_voice_state_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_VOICE_STATE_PAYLOAD)]):
        assert isinstance(run(bot.fetch_guild_current_voice_state("10")), VoiceState)


def test_bot_fetch_guild_member_voice_state_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_VOICE_STATE_PAYLOAD)]):
        assert isinstance(run(bot.fetch_guild_member_voice_state("10", "55")), VoiceState)


def test_bot_edit_guild_current_voice_state_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(bot.edit_guild_current_voice_state("10", channel_id="20"))
    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/voice-states/@me"


def test_bot_edit_guild_member_voice_state_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(bot.edit_guild_member_voice_state("10", "55", suppress=True))
    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/voice-states/55"


# --- guild.*() object-method delegation ---


def test_guild_fetch_voice_state_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_VOICE_STATE_PAYLOAD)]) as urlopen:
        result = run(guild.fetch_voice_state())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/voice-states/@me"
    assert isinstance(result, VoiceState)


def test_guild_fetch_member_voice_state_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_VOICE_STATE_PAYLOAD)]) as urlopen:
        result = run(guild.fetch_member_voice_state("55"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/voice-states/55"
    assert isinstance(result, VoiceState)


def test_guild_edit_voice_state_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(guild.edit_voice_state(channel_id="20"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/voice-states/@me"
    assert json.loads(req.data) == {"channel_id": "20"}


def test_guild_edit_member_voice_state_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(guild.edit_member_voice_state("55", suppress=False))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/voice-states/55"
    assert json.loads(req.data) == {"suppress": False}
