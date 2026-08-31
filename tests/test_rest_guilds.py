"""_rest/guilds.py: guild management REST endpoints, plus their bot.<verb>()
and Guild object-method delegation."""

import json
import os
from asyncio import run
from unittest.mock import patch

from conftest import BOT_ENV, FakeDiscordResponse, send_patch

from cordless._rest import guilds
from cordless._rest.models import (
    Ban,
    BulkBanResult,
    GuildOnboarding,
    GuildWidget,
    GuildWidgetSettings,
    IncidentsData,
    Integration,
    Invite,
    VoiceRegion,
    WelcomeScreen,
)
from cordless.app import Cordless
from cordless.models import Guild

_GUILD_PAYLOAD = {"id": "10", "name": "shiv's server"}
_BAN_PAYLOAD = {"reason": "spam", "user": {"id": "55", "username": "shiv"}}
_INTEGRATION_PAYLOAD = {"id": "99", "name": "twitch", "type": "twitch", "enabled": True}
_REGION_PAYLOAD = {"id": "us-east", "name": "US East", "optimal": True, "deprecated": False, "custom": False}
_WIDGET_SETTINGS_PAYLOAD = {"enabled": True, "channel_id": "20"}
_WIDGET_PAYLOAD = {"id": "10", "name": "shiv's server", "instant_invite": None, "channels": [], "members": []}
_INVITE_PAYLOAD = {"code": "abc123", "guild_id": "10"}
_WELCOME_SCREEN_PAYLOAD = {"description": "welcome", "welcome_channels": []}
_ONBOARDING_PAYLOAD = {"guild_id": "10", "prompts": [], "default_channel_ids": [], "enabled": True, "mode": 0}
_INCIDENTS_PAYLOAD = {"invites_disabled_until": None, "dms_disabled_until": None}
_BULK_BAN_PAYLOAD = {"banned_users": ["1", "2"], "failed_users": []}


# --- fetch_guild / fetch_guild_preview / edit_guild ---


def test_fetch_guild_returns_guild():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_GUILD_PAYLOAD)]) as urlopen:
        result = run(guilds.fetch_guild("10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10"
    assert isinstance(result, Guild)


def test_fetch_guild_with_counts_adds_query_string():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_GUILD_PAYLOAD)]) as urlopen:
        run(guilds.fetch_guild("10", with_counts=True))

    assert urlopen.call_args.args[0].full_url.endswith("?with_counts=true")


def test_fetch_guild_preview_returns_guild():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_GUILD_PAYLOAD)]) as urlopen:
        result = run(guilds.fetch_guild_preview("10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/preview"
    assert isinstance(result, Guild)


def test_edit_guild_only_sends_fields_that_were_set():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_GUILD_PAYLOAD)]) as urlopen:
        result = run(guilds.edit_guild("10", name="renamed", afk_timeout=300))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10"
    assert req.get_method() == "PATCH"
    assert json.loads(req.data) == {"name": "renamed", "afk_timeout": 300}
    assert isinstance(result, Guild)


# --- bans ---


def test_fetch_guild_bans_returns_ban_list():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_BAN_PAYLOAD])]) as urlopen:
        result = run(guilds.fetch_guild_bans("10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/bans"
    assert result == [Ban(_BAN_PAYLOAD)]
    assert result[0].user is not None
    assert result[0].user.username == "shiv"


def test_fetch_guild_bans_passes_limit_and_before():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([])]) as urlopen:
        run(guilds.fetch_guild_bans("10", limit=5, before="90"))

    url = urlopen.call_args.args[0].full_url
    assert "limit=5" in url
    assert "before=90" in url


def test_fetch_guild_bans_passes_after():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([])]) as urlopen:
        run(guilds.fetch_guild_bans("10", after="10"))

    assert "after=10" in urlopen.call_args.args[0].full_url


def test_fetch_guild_ban_returns_single_ban():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_BAN_PAYLOAD)]) as urlopen:
        result = run(guilds.fetch_guild_ban("10", "55"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/bans/55"
    assert result == Ban(_BAN_PAYLOAD)


def test_create_guild_ban_puts_delete_message_seconds():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(guilds.create_guild_ban("10", "55", delete_message_seconds=3600))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/bans/55"
    assert req.get_method() == "PUT"
    assert json.loads(req.data) == {"delete_message_seconds": 3600}


def test_remove_guild_ban_deletes_ban():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(guilds.remove_guild_ban("10", "55"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/bans/55"
    assert req.get_method() == "DELETE"


def test_bulk_guild_ban_posts_user_ids():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_BULK_BAN_PAYLOAD)]) as urlopen:
        result = run(guilds.bulk_guild_ban("10", ["1", "2"], delete_message_seconds=60))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/bulk-ban"
    assert json.loads(req.data) == {"user_ids": ["1", "2"], "delete_message_seconds": 60}
    assert isinstance(result, BulkBanResult)
    assert result.banned_users == ["1", "2"]


# --- prune ---


def test_fetch_guild_prune_count_returns_pruned_int():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse({"pruned": 12})]) as urlopen:
        result = run(guilds.fetch_guild_prune_count("10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/prune"
    assert result == 12


def test_fetch_guild_prune_count_passes_days_and_include_roles():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse({"pruned": 0})]) as urlopen:
        run(guilds.fetch_guild_prune_count("10", days=14, include_roles=["1", "2"]))

    url = urlopen.call_args.args[0].full_url
    assert "days=14" in url
    assert "include_roles=1%2C2" in url or "include_roles=1,2" in url


def test_begin_guild_prune_posts_and_returns_pruned_int():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse({"pruned": 5})]) as urlopen:
        result = run(guilds.begin_guild_prune("10", days=7, compute_prune_count=True))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/prune"
    assert req.get_method() == "POST"
    assert json.loads(req.data) == {"days": 7, "compute_prune_count": True}
    assert result == 5


# --- voice regions / invites / integrations ---


def test_fetch_guild_voice_regions_returns_region_list():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_REGION_PAYLOAD])]) as urlopen:
        result = run(guilds.fetch_guild_voice_regions("10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/regions"
    assert result == [VoiceRegion(_REGION_PAYLOAD)]


def test_fetch_guild_invites_returns_invite_list():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_INVITE_PAYLOAD])]) as urlopen:
        result = run(guilds.fetch_guild_invites("10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/invites"
    assert result == [Invite(_INVITE_PAYLOAD)]


def test_fetch_guild_integrations_returns_integration_list():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_INTEGRATION_PAYLOAD])]) as urlopen:
        result = run(guilds.fetch_guild_integrations("10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/integrations"
    assert result == [Integration(_INTEGRATION_PAYLOAD)]


def test_delete_guild_integration_deletes_integration():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(guilds.delete_guild_integration("10", "99"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/integrations/99"
    assert req.get_method() == "DELETE"


# --- widget ---


def test_fetch_guild_widget_settings_returns_settings():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_WIDGET_SETTINGS_PAYLOAD)]) as urlopen:
        result = run(guilds.fetch_guild_widget_settings("10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/widget"
    assert isinstance(result, GuildWidgetSettings)
    assert result.enabled is True


def test_edit_guild_widget_patches_fields():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_WIDGET_SETTINGS_PAYLOAD)]) as urlopen:
        result = run(guilds.edit_guild_widget("10", enabled=True, channel_id="20"))

    req = urlopen.call_args.args[0]
    assert req.get_method() == "PATCH"
    assert json.loads(req.data) == {"enabled": True, "channel_id": "20"}
    assert isinstance(result, GuildWidgetSettings)


def test_fetch_guild_widget_returns_widget():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_WIDGET_PAYLOAD)]) as urlopen:
        result = run(guilds.fetch_guild_widget("10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/widget.json"
    assert isinstance(result, GuildWidget)


def test_fetch_guild_vanity_url_returns_partial_invite():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_INVITE_PAYLOAD)]) as urlopen:
        result = run(guilds.fetch_guild_vanity_url("10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/vanity-url"
    assert isinstance(result, Invite)


def test_guild_widget_image_url_builds_url_without_a_request():
    guild = Guild({"id": "10"})
    assert guild.widget_image_url() == "https://discord.com/api/guilds/10/widget.png?style=shield"
    assert guild.widget_image_url("banner2") == "https://discord.com/api/guilds/10/widget.png?style=banner2"


# --- welcome screen / onboarding / incident actions ---


def test_fetch_guild_welcome_screen_returns_screen():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_WELCOME_SCREEN_PAYLOAD)]) as urlopen:
        result = run(guilds.fetch_guild_welcome_screen("10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/welcome-screen"
    assert isinstance(result, WelcomeScreen)


def test_edit_guild_welcome_screen_patches_fields():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_WELCOME_SCREEN_PAYLOAD)]) as urlopen:
        result = run(guilds.edit_guild_welcome_screen("10", enabled=True, description="hey"))

    req = urlopen.call_args.args[0]
    assert req.get_method() == "PATCH"
    assert json.loads(req.data) == {"enabled": True, "description": "hey"}
    assert isinstance(result, WelcomeScreen)


def test_fetch_guild_onboarding_returns_onboarding():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_ONBOARDING_PAYLOAD)]) as urlopen:
        result = run(guilds.fetch_guild_onboarding("10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/onboarding"
    assert isinstance(result, GuildOnboarding)


def test_edit_guild_onboarding_puts_fields():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_ONBOARDING_PAYLOAD)]) as urlopen:
        result = run(guilds.edit_guild_onboarding("10", enabled=True, mode=1))

    req = urlopen.call_args.args[0]
    assert req.get_method() == "PUT"
    assert json.loads(req.data) == {"enabled": True, "mode": 1}
    assert isinstance(result, GuildOnboarding)


def test_edit_guild_incident_actions_puts_fields():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_INCIDENTS_PAYLOAD)]) as urlopen:
        result = run(guilds.edit_guild_incident_actions("10", dms_disabled_until="2024-01-01T00:00:00Z"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/incident-actions"
    assert req.get_method() == "PUT"
    assert json.loads(req.data) == {"dms_disabled_until": "2024-01-01T00:00:00Z"}
    assert isinstance(result, IncidentsData)


# --- bot.<verb>() delegation (every mixin method) ---


def test_bot_fetch_guild_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_GUILD_PAYLOAD)]):
        assert isinstance(run(bot.fetch_guild("10")), Guild)


def test_bot_fetch_guild_preview_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_GUILD_PAYLOAD)]):
        assert isinstance(run(bot.fetch_guild_preview("10")), Guild)


def test_bot_edit_guild_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_GUILD_PAYLOAD)]):
        assert isinstance(run(bot.edit_guild("10", name="renamed")), Guild)


def test_bot_fetch_guild_bans_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_BAN_PAYLOAD])]):
        assert run(bot.fetch_guild_bans("10")) == [Ban(_BAN_PAYLOAD)]


def test_bot_fetch_guild_ban_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_BAN_PAYLOAD)]):
        assert run(bot.fetch_guild_ban("10", "55")) == Ban(_BAN_PAYLOAD)


def test_bot_create_guild_ban_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(bot.create_guild_ban("10", "55"))
    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/bans/55"


def test_bot_remove_guild_ban_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(bot.remove_guild_ban("10", "55"))
    assert urlopen.call_args.args[0].get_method() == "DELETE"


def test_bot_bulk_guild_ban_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_BULK_BAN_PAYLOAD)]):
        assert isinstance(run(bot.bulk_guild_ban("10", ["1", "2"])), BulkBanResult)


def test_bot_fetch_guild_prune_count_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse({"pruned": 3})]):
        assert run(bot.fetch_guild_prune_count("10")) == 3


def test_bot_begin_guild_prune_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse({"pruned": 3})]):
        assert run(bot.begin_guild_prune("10")) == 3


def test_bot_fetch_guild_voice_regions_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_REGION_PAYLOAD])]):
        assert run(bot.fetch_guild_voice_regions("10")) == [VoiceRegion(_REGION_PAYLOAD)]


def test_bot_fetch_guild_invites_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_INVITE_PAYLOAD])]):
        assert run(bot.fetch_guild_invites("10")) == [Invite(_INVITE_PAYLOAD)]


def test_bot_fetch_guild_integrations_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_INTEGRATION_PAYLOAD])]):
        assert run(bot.fetch_guild_integrations("10")) == [Integration(_INTEGRATION_PAYLOAD)]


def test_bot_delete_guild_integration_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(bot.delete_guild_integration("10", "99"))
    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/integrations/99"


def test_bot_fetch_guild_widget_settings_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_WIDGET_SETTINGS_PAYLOAD)]):
        assert isinstance(run(bot.fetch_guild_widget_settings("10")), GuildWidgetSettings)


def test_bot_edit_guild_widget_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_WIDGET_SETTINGS_PAYLOAD)]):
        assert isinstance(run(bot.edit_guild_widget("10", enabled=True)), GuildWidgetSettings)


def test_bot_fetch_guild_widget_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_WIDGET_PAYLOAD)]):
        assert isinstance(run(bot.fetch_guild_widget("10")), GuildWidget)


def test_bot_fetch_guild_vanity_url_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_INVITE_PAYLOAD)]):
        assert isinstance(run(bot.fetch_guild_vanity_url("10")), Invite)


def test_bot_fetch_guild_welcome_screen_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_WELCOME_SCREEN_PAYLOAD)]):
        assert isinstance(run(bot.fetch_guild_welcome_screen("10")), WelcomeScreen)


def test_bot_edit_guild_welcome_screen_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_WELCOME_SCREEN_PAYLOAD)]):
        assert isinstance(run(bot.edit_guild_welcome_screen("10", enabled=True)), WelcomeScreen)


def test_bot_fetch_guild_onboarding_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_ONBOARDING_PAYLOAD)]):
        assert isinstance(run(bot.fetch_guild_onboarding("10")), GuildOnboarding)


def test_bot_edit_guild_onboarding_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_ONBOARDING_PAYLOAD)]):
        assert isinstance(run(bot.edit_guild_onboarding("10", enabled=True)), GuildOnboarding)


def test_bot_edit_guild_incident_actions_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_INCIDENTS_PAYLOAD)]):
        assert isinstance(run(bot.edit_guild_incident_actions("10")), IncidentsData)


# --- guild.*() object-method delegation (every new method) ---


def test_guild_fetch_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_GUILD_PAYLOAD)]) as urlopen:
        result = run(guild.fetch())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10"
    assert isinstance(result, Guild)


def test_guild_fetch_preview_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_GUILD_PAYLOAD)]):
        assert isinstance(run(guild.fetch_preview()), Guild)


def test_guild_edit_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_GUILD_PAYLOAD)]) as urlopen:
        result = run(guild.edit(name="renamed"))

    assert json.loads(urlopen.call_args.args[0].data) == {"name": "renamed"}
    assert isinstance(result, Guild)


def test_guild_fetch_bans_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_BAN_PAYLOAD])]):
        assert run(guild.fetch_bans()) == [Ban(_BAN_PAYLOAD)]


def test_guild_fetch_ban_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_BAN_PAYLOAD)]):
        assert run(guild.fetch_ban("55")) == Ban(_BAN_PAYLOAD)


def test_guild_ban_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(guild.ban("55"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/bans/55"
    assert req.get_method() == "PUT"


def test_guild_unban_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(guild.unban("55"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/bans/55"
    assert req.get_method() == "DELETE"


def test_guild_bulk_ban_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_BULK_BAN_PAYLOAD)]):
        assert isinstance(run(guild.bulk_ban(["1", "2"])), BulkBanResult)


def test_guild_fetch_prune_count_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse({"pruned": 8})]):
        assert run(guild.fetch_prune_count()) == 8


def test_guild_prune_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse({"pruned": 8})]):
        assert run(guild.prune()) == 8


def test_guild_fetch_voice_regions_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_REGION_PAYLOAD])]):
        assert run(guild.fetch_voice_regions()) == [VoiceRegion(_REGION_PAYLOAD)]


def test_guild_fetch_invites_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_INVITE_PAYLOAD])]):
        assert run(guild.fetch_invites()) == [Invite(_INVITE_PAYLOAD)]


def test_guild_fetch_integrations_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_INTEGRATION_PAYLOAD])]):
        assert run(guild.fetch_integrations()) == [Integration(_INTEGRATION_PAYLOAD)]


def test_guild_delete_integration_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(guild.delete_integration("99"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/integrations/99"


def test_guild_fetch_widget_settings_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_WIDGET_SETTINGS_PAYLOAD)]):
        assert isinstance(run(guild.fetch_widget_settings()), GuildWidgetSettings)


def test_guild_edit_widget_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_WIDGET_SETTINGS_PAYLOAD)]):
        assert isinstance(run(guild.edit_widget(enabled=False)), GuildWidgetSettings)


def test_guild_fetch_widget_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_WIDGET_PAYLOAD)]):
        assert isinstance(run(guild.fetch_widget()), GuildWidget)


def test_guild_fetch_vanity_url_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_INVITE_PAYLOAD)]):
        assert isinstance(run(guild.fetch_vanity_url()), Invite)


def test_guild_fetch_welcome_screen_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_WELCOME_SCREEN_PAYLOAD)]):
        assert isinstance(run(guild.fetch_welcome_screen()), WelcomeScreen)


def test_guild_edit_welcome_screen_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_WELCOME_SCREEN_PAYLOAD)]):
        assert isinstance(run(guild.edit_welcome_screen(enabled=True)), WelcomeScreen)


def test_guild_fetch_onboarding_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_ONBOARDING_PAYLOAD)]):
        assert isinstance(run(guild.fetch_onboarding()), GuildOnboarding)


def test_guild_edit_onboarding_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_ONBOARDING_PAYLOAD)]):
        assert isinstance(run(guild.edit_onboarding(enabled=True)), GuildOnboarding)


def test_guild_edit_incident_actions_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_INCIDENTS_PAYLOAD)]):
        assert isinstance(run(guild.edit_incident_actions()), IncidentsData)
