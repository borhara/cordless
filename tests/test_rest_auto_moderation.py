"""_rest/auto_moderation.py: auto moderation REST endpoints, plus their
bot.<verb>() and Guild/AutoModerationRule object-method delegation."""

import json
import os
from asyncio import run
from unittest.mock import patch

from conftest import FakeDiscordResponse

from cordless._rest import auto_moderation
from cordless._rest.models import AutoModerationRule
from cordless.app import Cordless
from cordless.models import Guild

_ENV = {"DISCORD_BOT_TOKEN": "tok"}

_RULE_PAYLOAD = {
    "id": "1",
    "guild_id": "10",
    "name": "shiv's keyword filter",
    "creator_id": "55",
    "event_type": 1,
    "trigger_type": 1,
    "trigger_metadata": {"keyword_filter": ["badword"]},
    "actions": [{"type": 1}],
    "enabled": True,
    "exempt_roles": [],
    "exempt_channels": [],
}


def _urlopen(responses):
    return patch("cordless._rest._client._send", side_effect=responses)


# --- _rest/auto_moderation.py ---


def test_fetch_auto_moderation_rules_returns_rule_list():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_RULE_PAYLOAD])]) as urlopen:
        result = run(auto_moderation.fetch_auto_moderation_rules("10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/auto-moderation/rules"
    assert result == [AutoModerationRule(_RULE_PAYLOAD)]


def test_fetch_auto_moderation_rule_returns_single_rule():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_RULE_PAYLOAD)]) as urlopen:
        result = run(auto_moderation.fetch_auto_moderation_rule("10", "1"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/auto-moderation/rules/1"
    assert isinstance(result, AutoModerationRule)


def test_create_auto_moderation_rule_posts_required_and_optional_fields():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_RULE_PAYLOAD)]) as urlopen:
        result = run(
            auto_moderation.create_auto_moderation_rule(
                "10",
                "shiv's keyword filter",
                1,
                1,
                [{"type": 1}],
                trigger_metadata={"keyword_filter": ["badword"]},
                exempt_roles=["20"],
            )
        )

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/auto-moderation/rules"
    assert json.loads(req.data) == {
        "name": "shiv's keyword filter",
        "event_type": 1,
        "trigger_type": 1,
        "trigger_metadata": {"keyword_filter": ["badword"]},
        "actions": [{"type": 1}],
        "exempt_roles": ["20"],
    }
    assert isinstance(result, AutoModerationRule)


def test_edit_auto_moderation_rule_only_sends_fields_that_were_set():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_RULE_PAYLOAD)]) as urlopen:
        result = run(auto_moderation.edit_auto_moderation_rule("10", "1", enabled=False))

    assert json.loads(urlopen.call_args.args[0].data) == {"enabled": False}
    assert isinstance(result, AutoModerationRule)


def test_delete_auto_moderation_rule_deletes_rule():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(auto_moderation.delete_auto_moderation_rule("10", "1"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/auto-moderation/rules/1"
    assert req.get_method() == "DELETE"


# --- bot.<verb>() delegation ---


def test_bot_fetch_auto_moderation_rules_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_RULE_PAYLOAD])]):
        assert run(bot.fetch_auto_moderation_rules("10")) == [AutoModerationRule(_RULE_PAYLOAD)]


def test_bot_fetch_auto_moderation_rule_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_RULE_PAYLOAD)]):
        assert isinstance(run(bot.fetch_auto_moderation_rule("10", "1")), AutoModerationRule)


def test_bot_create_auto_moderation_rule_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_RULE_PAYLOAD)]):
        result = run(bot.create_auto_moderation_rule("10", "shiv's keyword filter", 1, 1, [{"type": 1}]))

    assert isinstance(result, AutoModerationRule)


def test_bot_edit_auto_moderation_rule_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_RULE_PAYLOAD)]):
        assert isinstance(run(bot.edit_auto_moderation_rule("10", "1", enabled=False)), AutoModerationRule)


def test_bot_delete_auto_moderation_rule_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(bot.delete_auto_moderation_rule("10", "1"))
    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/auto-moderation/rules/1"


# --- guild.*() object-method delegation ---


def test_guild_fetch_auto_moderation_rules_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_RULE_PAYLOAD])]) as urlopen:
        result = run(guild.fetch_auto_moderation_rules())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/auto-moderation/rules"
    assert result == [AutoModerationRule(_RULE_PAYLOAD)]


def test_guild_fetch_auto_moderation_rule_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_RULE_PAYLOAD)]):
        assert isinstance(run(guild.fetch_auto_moderation_rule("1")), AutoModerationRule)


def test_guild_create_auto_moderation_rule_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_RULE_PAYLOAD)]) as urlopen:
        result = run(guild.create_auto_moderation_rule("shiv's keyword filter", 1, 1, [{"type": 1}]))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/auto-moderation/rules"
    assert isinstance(result, AutoModerationRule)


# --- rule.*() object-method delegation ---


def test_rule_edit_delegates_to_rest_module():
    rule = AutoModerationRule(_RULE_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_RULE_PAYLOAD)]) as urlopen:
        result = run(rule.edit(enabled=False))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/auto-moderation/rules/1"
    assert json.loads(req.data) == {"enabled": False}
    assert isinstance(result, AutoModerationRule)


def test_rule_delete_delegates_to_rest_module():
    rule = AutoModerationRule(_RULE_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(rule.delete())

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/auto-moderation/rules/1"
    assert req.get_method() == "DELETE"
