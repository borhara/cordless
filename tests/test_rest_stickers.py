"""_rest/stickers.py: sticker REST endpoints, plus their bot.<verb>() and
Guild/Sticker object-method delegation."""

import json
import os
from asyncio import run
from unittest.mock import patch

import pytest
from conftest import FakeDiscordResponse

from cordless._rest import stickers
from cordless._rest.models import Sticker, StickerPack
from cordless.app import Cordless
from cordless.models import Guild

_ENV = {"DISCORD_BOT_TOKEN": "tok"}

_STICKER_PAYLOAD = {"id": "1", "name": "shiv_wave", "type": 2, "format_type": 1, "guild_id": "10"}
_PACK_PAYLOAD = {"id": "99", "name": "Official Pack", "stickers": [_STICKER_PAYLOAD], "sku_id": "1"}


def _urlopen(responses):
    return patch("cordless._rest._client.urllib.request.urlopen", side_effect=responses)


def test_fetch_sticker_returns_single_sticker():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_STICKER_PAYLOAD)]) as urlopen:
        result = run(stickers.fetch_sticker("1"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/stickers/1"
    assert isinstance(result, Sticker)


def test_fetch_sticker_packs_unwraps_sticker_packs_key():
    payload = {"sticker_packs": [_PACK_PAYLOAD]}
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(payload)]) as urlopen:
        result = run(stickers.fetch_sticker_packs())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/sticker-packs"
    assert len(result) == 1
    assert isinstance(result[0], StickerPack)
    assert result[0].stickers == [Sticker(_STICKER_PAYLOAD)]


def test_fetch_sticker_pack_returns_single_pack():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_PACK_PAYLOAD)]) as urlopen:
        result = run(stickers.fetch_sticker_pack("99"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/sticker-packs/99"
    assert isinstance(result, StickerPack)


def test_fetch_guild_stickers_returns_sticker_list():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_STICKER_PAYLOAD])]) as urlopen:
        result = run(stickers.fetch_guild_stickers("10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/stickers"
    assert result == [Sticker(_STICKER_PAYLOAD)]


def test_fetch_guild_sticker_returns_single_sticker():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_STICKER_PAYLOAD)]) as urlopen:
        result = run(stickers.fetch_guild_sticker("10", "1"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/stickers/1"
    assert isinstance(result, Sticker)


def test_create_guild_sticker_sends_plain_multipart_form():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_STICKER_PAYLOAD)]) as urlopen:
        result = run(stickers.create_guild_sticker("10", "shiv_wave", "shiv waving", "wave", "wave.png", b"png-bytes"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/stickers"
    assert req.get_header("Content-type").startswith("multipart/form-data; boundary=")
    assert b'name="name"' in req.data
    assert b"shiv_wave" in req.data
    assert b'name="description"' in req.data
    assert b"shiv waving" in req.data
    assert b'name="tags"' in req.data
    assert b'name="file"; filename="wave.png"' in req.data
    assert b"png-bytes" in req.data
    # not the message-attachment convention this endpoint doesn't use
    assert b"payload_json" not in req.data
    assert isinstance(result, Sticker)


def test_edit_guild_sticker_only_sends_fields_that_were_set():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_STICKER_PAYLOAD)]) as urlopen:
        run(stickers.edit_guild_sticker("10", "1", name="renamed"))

    assert json.loads(urlopen.call_args.args[0].data) == {"name": "renamed"}


def test_delete_guild_sticker_deletes_sticker():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(stickers.delete_guild_sticker("10", "1"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/stickers/1"
    assert req.get_method() == "DELETE"


# --- bot.<verb>() delegation ---


def test_bot_fetch_sticker_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_STICKER_PAYLOAD)]):
        assert isinstance(run(bot.fetch_sticker("1")), Sticker)


def test_bot_fetch_sticker_packs_delegates_to_rest_module():
    bot = Cordless()
    payload = {"sticker_packs": [_PACK_PAYLOAD]}
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(payload)]):
        assert len(run(bot.fetch_sticker_packs())) == 1


def test_bot_fetch_sticker_pack_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_PACK_PAYLOAD)]):
        assert isinstance(run(bot.fetch_sticker_pack("99")), StickerPack)


def test_bot_fetch_guild_stickers_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_STICKER_PAYLOAD])]):
        assert run(bot.fetch_guild_stickers("10")) == [Sticker(_STICKER_PAYLOAD)]


def test_bot_fetch_guild_sticker_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_STICKER_PAYLOAD)]):
        assert isinstance(run(bot.fetch_guild_sticker("10", "1")), Sticker)


def test_bot_create_guild_sticker_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_STICKER_PAYLOAD)]):
        result = run(bot.create_guild_sticker("10", "shiv_wave", "shiv waving", "wave", "wave.png", b"png-bytes"))

    assert isinstance(result, Sticker)


def test_bot_edit_guild_sticker_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_STICKER_PAYLOAD)]):
        assert isinstance(run(bot.edit_guild_sticker("10", "1", name="renamed")), Sticker)


def test_bot_delete_guild_sticker_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(bot.delete_guild_sticker("10", "1"))
    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/stickers/1"


# --- guild.*() object-method delegation ---


def test_guild_fetch_stickers_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_STICKER_PAYLOAD])]) as urlopen:
        result = run(guild.fetch_stickers())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/stickers"
    assert result == [Sticker(_STICKER_PAYLOAD)]


def test_guild_fetch_sticker_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_STICKER_PAYLOAD)]):
        assert isinstance(run(guild.fetch_sticker("1")), Sticker)


def test_guild_create_sticker_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_STICKER_PAYLOAD)]) as urlopen:
        result = run(guild.create_sticker("shiv_wave", "shiv waving", "wave", "wave.png", b"png-bytes"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/stickers"
    assert isinstance(result, Sticker)


# --- sticker.*() object-method delegation ---


def test_sticker_edit_delegates_to_rest_module():
    sticker = Sticker(_STICKER_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_STICKER_PAYLOAD)]) as urlopen:
        result = run(sticker.edit(name="renamed"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/stickers/1"
    assert json.loads(req.data) == {"name": "renamed"}
    assert isinstance(result, Sticker)


def test_sticker_delete_delegates_to_rest_module():
    sticker = Sticker(_STICKER_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(sticker.delete())

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/stickers/1"
    assert req.get_method() == "DELETE"


def test_sticker_edit_on_pack_sticker_raises_value_error():
    sticker = Sticker({"id": "1", "name": "official_wave"})
    with pytest.raises(ValueError, match="sticker pack"):
        run(sticker.edit(name="renamed"))


def test_sticker_delete_on_pack_sticker_raises_value_error():
    sticker = Sticker({"id": "1", "name": "official_wave"})
    with pytest.raises(ValueError, match="sticker pack"):
        run(sticker.delete())
