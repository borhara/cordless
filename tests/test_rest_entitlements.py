"""_rest/entitlements.py and _rest/skus.py: entitlement/SKU REST endpoints,
plus their bot.<verb>() and Entitlement object-method delegation."""

import json
import os
from asyncio import run
from unittest.mock import patch

from conftest import FakeDiscordResponse

from cordless._rest import entitlements, skus
from cordless._rest.models import SKU, Entitlement
from cordless.app import Cordless

_ENV = {"DISCORD_BOT_TOKEN": "tok"}

_ENTITLEMENT_PAYLOAD = {
    "id": "1",
    "sku_id": "2",
    "application_id": "3",
    "user_id": "55",
    "type": 8,
    "deleted": False,
}
_SKU_PAYLOAD = {"id": "2", "type": 5, "application_id": "3", "name": "shiv's premium", "slug": "shiv-premium"}


def _urlopen(responses):
    return patch("cordless._rest._client._send", side_effect=responses)


# --- _rest/entitlements.py ---


def test_fetch_entitlements_returns_entitlement_list():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_ENTITLEMENT_PAYLOAD])]) as urlopen:
        result = run(entitlements.fetch_entitlements("3"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/applications/3/entitlements"
    assert result == [Entitlement(_ENTITLEMENT_PAYLOAD)]


def test_fetch_entitlements_passes_query_params():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([])]) as urlopen:
        run(
            entitlements.fetch_entitlements(
                "3",
                user_id="55",
                sku_ids=["2", "4"],
                before="90",
                after="10",
                limit=5,
                guild_id="10",
                exclude_ended=True,
                exclude_deleted=False,
            )
        )

    url = urlopen.call_args.args[0].full_url
    assert "user_id=55" in url
    assert "sku_ids=2%2C4" in url
    assert "before=90" in url
    assert "after=10" in url
    assert "limit=5" in url
    assert "guild_id=10" in url
    assert "exclude_ended=true" in url
    assert "exclude_deleted=false" in url


def test_fetch_entitlements_omits_bool_params_when_unset():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([])]) as urlopen:
        run(entitlements.fetch_entitlements("3"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/applications/3/entitlements"


def test_fetch_entitlement_returns_single_entitlement():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_ENTITLEMENT_PAYLOAD)]) as urlopen:
        result = run(entitlements.fetch_entitlement("3", "1"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/applications/3/entitlements/1"
    assert isinstance(result, Entitlement)


def test_consume_entitlement_consumes_it():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(entitlements.consume_entitlement("3", "1"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/applications/3/entitlements/1/consume"
    assert req.get_method() == "POST"


def test_create_test_entitlement_posts_required_fields():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_ENTITLEMENT_PAYLOAD)]) as urlopen:
        result = run(entitlements.create_test_entitlement("3", "2", "55", 2))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/applications/3/entitlements"
    assert json.loads(req.data) == {"sku_id": "2", "owner_id": "55", "owner_type": 2}
    assert isinstance(result, Entitlement)


def test_delete_test_entitlement_deletes_it():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(entitlements.delete_test_entitlement("3", "1"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/applications/3/entitlements/1"
    assert req.get_method() == "DELETE"


# --- _rest/skus.py ---


def test_fetch_skus_returns_sku_list():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_SKU_PAYLOAD])]) as urlopen:
        result = run(skus.fetch_skus("3"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/applications/3/skus"
    assert result == [SKU(_SKU_PAYLOAD)]


# --- bot.<verb>() delegation ---


def test_bot_fetch_entitlements_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_ENTITLEMENT_PAYLOAD])]):
        assert run(bot.fetch_entitlements("3")) == [Entitlement(_ENTITLEMENT_PAYLOAD)]


def test_bot_fetch_entitlement_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_ENTITLEMENT_PAYLOAD)]):
        assert isinstance(run(bot.fetch_entitlement("3", "1")), Entitlement)


def test_bot_consume_entitlement_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(bot.consume_entitlement("3", "1"))
    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/applications/3/entitlements/1/consume"


def test_bot_create_test_entitlement_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_ENTITLEMENT_PAYLOAD)]):
        assert isinstance(run(bot.create_test_entitlement("3", "2", "55", 2)), Entitlement)


def test_bot_delete_test_entitlement_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(bot.delete_test_entitlement("3", "1"))
    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/applications/3/entitlements/1"


def test_bot_fetch_skus_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_SKU_PAYLOAD])]):
        assert run(bot.fetch_skus("3")) == [SKU(_SKU_PAYLOAD)]


# --- entitlement.*() object-method delegation ---


def test_entitlement_consume_delegates_to_rest_module():
    entitlement = Entitlement(_ENTITLEMENT_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(entitlement.consume())

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/applications/3/entitlements/1/consume"
    assert req.get_method() == "POST"


def test_entitlement_delete_delegates_to_rest_module():
    entitlement = Entitlement(_ENTITLEMENT_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(entitlement.delete())

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/applications/3/entitlements/1"
    assert req.get_method() == "DELETE"
