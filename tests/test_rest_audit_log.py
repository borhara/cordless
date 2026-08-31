"""_rest/audit_log.py: audit log REST endpoint, plus its bot.<verb>() and
Guild/AuditLog object-method delegation."""

import os
from asyncio import run
from unittest.mock import patch

from conftest import BOT_ENV, FakeDiscordResponse, send_patch

from cordless._rest import audit_log
from cordless._rest.models import (
    AuditLog,
    AuditLogEntry,
    AutoModerationRule,
    GuildScheduledEvent,
    Integration,
    Thread,
    Webhook,
)
from cordless.app import Cordless
from cordless.models import Guild, User

_AUDIT_LOG_PAYLOAD = {
    "application_commands": [],
    "audit_log_entries": [{"id": "1", "user_id": "55", "target_id": "20", "action_type": 1}],
    "auto_moderation_rules": [{"id": "2", "guild_id": "10", "name": "shiv's rule"}],
    "guild_scheduled_events": [{"id": "3", "guild_id": "10", "name": "shiv's event"}],
    "integrations": [{"id": "4", "name": "shiv's integration"}],
    "threads": [
        {"id": "5", "guild_id": "10", "parent_id": None, "owner_id": "55", "name": "shiv's thread", "type": 11}
    ],
    "users": [{"id": "55", "username": "shiv"}],
    "webhooks": [{"id": "6", "name": "shiv's webhook"}],
}


# --- _rest/audit_log.py ---


def test_fetch_audit_log_returns_audit_log():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_AUDIT_LOG_PAYLOAD)]) as urlopen:
        result = run(audit_log.fetch_audit_log("10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/audit-logs"
    assert isinstance(result, AuditLog)


def test_fetch_audit_log_passes_query_params():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_AUDIT_LOG_PAYLOAD)]) as urlopen:
        run(audit_log.fetch_audit_log("10", user_id="55", action_type=1, before="90", after="10", limit=5))

    url = urlopen.call_args.args[0].full_url
    assert "user_id=55" in url
    assert "action_type=1" in url
    assert "before=90" in url
    assert "after=10" in url
    assert "limit=5" in url


def test_fetch_audit_log_action_type_zero_is_included():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_AUDIT_LOG_PAYLOAD)]) as urlopen:
        run(audit_log.fetch_audit_log("10", action_type=0))

    assert "action_type=0" in urlopen.call_args.args[0].full_url


# --- bot.<verb>() delegation ---


def test_bot_fetch_audit_log_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_AUDIT_LOG_PAYLOAD)]):
        assert isinstance(run(bot.fetch_audit_log("10")), AuditLog)


# --- guild.*() object-method delegation ---


def test_guild_fetch_audit_log_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_AUDIT_LOG_PAYLOAD)]) as urlopen:
        result = run(guild.fetch_audit_log())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/audit-logs"
    assert isinstance(result, AuditLog)


# --- AuditLog wrapped-list properties ---


def test_audit_log_entries_wraps_entries():
    log = AuditLog(_AUDIT_LOG_PAYLOAD)
    assert log.entries == [AuditLogEntry(_AUDIT_LOG_PAYLOAD["audit_log_entries"][0])]


def test_audit_log_users_wraps_users():
    log = AuditLog(_AUDIT_LOG_PAYLOAD)
    assert log.users == [User(_AUDIT_LOG_PAYLOAD["users"][0])]


def test_audit_log_webhooks_wraps_webhooks():
    log = AuditLog(_AUDIT_LOG_PAYLOAD)
    assert log.webhooks == [Webhook(_AUDIT_LOG_PAYLOAD["webhooks"][0])]


def test_audit_log_integrations_wraps_integrations():
    log = AuditLog(_AUDIT_LOG_PAYLOAD)
    assert log.integrations == [Integration(_AUDIT_LOG_PAYLOAD["integrations"][0])]


def test_audit_log_threads_wraps_threads():
    log = AuditLog(_AUDIT_LOG_PAYLOAD)
    assert log.threads == [Thread(_AUDIT_LOG_PAYLOAD["threads"][0])]


def test_audit_log_auto_moderation_rules_wraps_rules():
    log = AuditLog(_AUDIT_LOG_PAYLOAD)
    assert log.auto_moderation_rules == [AutoModerationRule(_AUDIT_LOG_PAYLOAD["auto_moderation_rules"][0])]


def test_audit_log_guild_scheduled_events_wraps_events():
    log = AuditLog(_AUDIT_LOG_PAYLOAD)
    assert log.guild_scheduled_events == [GuildScheduledEvent(_AUDIT_LOG_PAYLOAD["guild_scheduled_events"][0])]
