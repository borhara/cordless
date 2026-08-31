"""_rest/soundboard.py: soundboard REST endpoints, plus their bot.<verb>()
and Channel/Guild/SoundboardSound object-method delegation."""

import json
import os
from asyncio import run
from unittest.mock import patch

import pytest
from conftest import BOT_ENV, FakeDiscordResponse, send_patch

from cordless._rest import soundboard
from cordless._rest.models import SoundboardSound
from cordless.app import Cordless
from cordless.models import Channel, Guild

_SOUND_PAYLOAD = {"sound_id": "1", "name": "shiv_horn", "volume": 1.0, "guild_id": "10"}


# --- _rest/soundboard.py ---


def test_send_soundboard_sound_posts_required_and_optional_fields():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(soundboard.send_soundboard_sound("20", "1", source_guild_id="99"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/send-soundboard-sound"
    assert json.loads(req.data) == {"sound_id": "1", "source_guild_id": "99"}


def test_fetch_default_soundboard_sounds_returns_sound_list():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_SOUND_PAYLOAD])]) as urlopen:
        result = run(soundboard.fetch_default_soundboard_sounds())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/soundboard-default-sounds"
    assert result == [SoundboardSound(_SOUND_PAYLOAD)]


def test_fetch_guild_soundboard_sounds_unwraps_items_key():
    payload = {"items": [_SOUND_PAYLOAD]}
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]) as urlopen:
        result = run(soundboard.fetch_guild_soundboard_sounds("10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/soundboard-sounds"
    assert result == [SoundboardSound(_SOUND_PAYLOAD)]


def test_fetch_guild_soundboard_sound_returns_single_sound():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_SOUND_PAYLOAD)]) as urlopen:
        result = run(soundboard.fetch_guild_soundboard_sound("10", "1"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/soundboard-sounds/1"
    assert isinstance(result, SoundboardSound)


def test_create_guild_soundboard_sound_sends_required_and_optional_fields():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_SOUND_PAYLOAD)]) as urlopen:
        result = run(
            soundboard.create_guild_soundboard_sound("10", "shiv_horn", "data:audio/mpeg;base64,abc", volume=0.5)
        )

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/soundboard-sounds"
    assert json.loads(req.data) == {"name": "shiv_horn", "sound": "data:audio/mpeg;base64,abc", "volume": 0.5}
    assert isinstance(result, SoundboardSound)


def test_edit_guild_soundboard_sound_only_sends_fields_that_were_set():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_SOUND_PAYLOAD)]) as urlopen:
        result = run(soundboard.edit_guild_soundboard_sound("10", "1", name="renamed"))

    assert json.loads(urlopen.call_args.args[0].data) == {"name": "renamed"}
    assert isinstance(result, SoundboardSound)


def test_delete_guild_soundboard_sound_deletes_sound():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(soundboard.delete_guild_soundboard_sound("10", "1"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/soundboard-sounds/1"
    assert req.get_method() == "DELETE"


# --- bot.<verb>() delegation ---


def test_bot_send_soundboard_sound_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(bot.send_soundboard_sound("20", "1"))
    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/send-soundboard-sound"


def test_bot_fetch_default_soundboard_sounds_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_SOUND_PAYLOAD])]):
        assert run(bot.fetch_default_soundboard_sounds()) == [SoundboardSound(_SOUND_PAYLOAD)]


def test_bot_fetch_guild_soundboard_sounds_delegates_to_rest_module():
    bot = Cordless()
    payload = {"items": [_SOUND_PAYLOAD]}
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]):
        assert run(bot.fetch_guild_soundboard_sounds("10")) == [SoundboardSound(_SOUND_PAYLOAD)]


def test_bot_fetch_guild_soundboard_sound_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_SOUND_PAYLOAD)]):
        assert isinstance(run(bot.fetch_guild_soundboard_sound("10", "1")), SoundboardSound)


def test_bot_create_guild_soundboard_sound_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_SOUND_PAYLOAD)]):
        result = run(bot.create_guild_soundboard_sound("10", "shiv_horn", "data:audio/mpeg;base64,abc"))

    assert isinstance(result, SoundboardSound)


def test_bot_edit_guild_soundboard_sound_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_SOUND_PAYLOAD)]):
        assert isinstance(run(bot.edit_guild_soundboard_sound("10", "1", name="renamed")), SoundboardSound)


def test_bot_delete_guild_soundboard_sound_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(bot.delete_guild_soundboard_sound("10", "1"))
    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/soundboard-sounds/1"


# --- channel.*()/guild.*() object-method delegation ---


def test_channel_send_soundboard_sound_delegates_to_rest_module():
    channel = Channel({"id": "20"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(channel.send_soundboard_sound("1"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/send-soundboard-sound"
    assert json.loads(req.data) == {"sound_id": "1"}


def test_guild_fetch_soundboard_sounds_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    payload = {"items": [_SOUND_PAYLOAD]}
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]) as urlopen:
        result = run(guild.fetch_soundboard_sounds())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/soundboard-sounds"
    assert result == [SoundboardSound(_SOUND_PAYLOAD)]


def test_guild_fetch_soundboard_sound_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_SOUND_PAYLOAD)]):
        assert isinstance(run(guild.fetch_soundboard_sound("1")), SoundboardSound)


def test_guild_create_soundboard_sound_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_SOUND_PAYLOAD)]) as urlopen:
        result = run(guild.create_soundboard_sound("shiv_horn", "data:audio/mpeg;base64,abc"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/soundboard-sounds"
    assert isinstance(result, SoundboardSound)


# --- soundboard_sound.*() object-method delegation ---


def test_soundboard_sound_edit_delegates_to_rest_module():
    sound = SoundboardSound(_SOUND_PAYLOAD)
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_SOUND_PAYLOAD)]) as urlopen:
        result = run(sound.edit(name="renamed"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/soundboard-sounds/1"
    assert json.loads(req.data) == {"name": "renamed"}
    assert isinstance(result, SoundboardSound)


def test_soundboard_sound_delete_delegates_to_rest_module():
    sound = SoundboardSound(_SOUND_PAYLOAD)
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(sound.delete())

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/soundboard-sounds/1"
    assert req.get_method() == "DELETE"


def test_soundboard_sound_edit_on_default_sound_raises_value_error():
    sound = SoundboardSound({"sound_id": "1", "name": "default_horn"})
    with pytest.raises(ValueError, match="default soundboard sound"):
        run(sound.edit(name="renamed"))


def test_soundboard_sound_delete_on_default_sound_raises_value_error():
    sound = SoundboardSound({"sound_id": "1", "name": "default_horn"})
    with pytest.raises(ValueError, match="default soundboard sound"):
        run(sound.delete())
