"""_rest/scheduled_events.py: guild scheduled event REST endpoints, plus
their bot.<verb>() and Guild/GuildScheduledEvent object-method delegation."""

import json
import os
from asyncio import run
from unittest.mock import patch

from conftest import BOT_ENV, FakeDiscordResponse, send_patch

from cordless._rest import scheduled_events
from cordless._rest.models import GuildScheduledEvent, GuildScheduledEventUser
from cordless.app import Cordless
from cordless.models import Guild, Member, User

_EVENT_PAYLOAD = {
    "id": "1",
    "guild_id": "10",
    "name": "shiv's game night",
    "privacy_level": 2,
    "scheduled_start_time": "2024-01-01T00:00:00Z",
    "status": 1,
    "entity_type": 3,
}
_EVENT_USER_PAYLOAD = {"guild_scheduled_event_id": "1", "user": {"id": "55", "username": "shiv"}}


# --- _rest/scheduled_events.py ---


def test_fetch_guild_scheduled_events_returns_event_list():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_EVENT_PAYLOAD])]) as urlopen:
        result = run(scheduled_events.fetch_guild_scheduled_events("10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/scheduled-events"
    assert result == [GuildScheduledEvent(_EVENT_PAYLOAD)]


def test_fetch_guild_scheduled_events_with_user_count_adds_query_string():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([])]) as urlopen:
        run(scheduled_events.fetch_guild_scheduled_events("10", with_user_count=True))

    assert urlopen.call_args.args[0].full_url.endswith("?with_user_count=true")


def test_create_guild_scheduled_event_posts_required_and_optional_fields():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_EVENT_PAYLOAD)]) as urlopen:
        result = run(
            scheduled_events.create_guild_scheduled_event(
                "10",
                "shiv's game night",
                2,
                "2024-01-01T00:00:00Z",
                3,
                entity_metadata={"location": "shiv's house"},
                scheduled_end_time="2024-01-01T02:00:00Z",
            )
        )

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/scheduled-events"
    assert json.loads(req.data) == {
        "name": "shiv's game night",
        "privacy_level": 2,
        "scheduled_start_time": "2024-01-01T00:00:00Z",
        "entity_type": 3,
        "entity_metadata": {"location": "shiv's house"},
        "scheduled_end_time": "2024-01-01T02:00:00Z",
    }
    assert isinstance(result, GuildScheduledEvent)


def test_fetch_guild_scheduled_event_returns_single_event():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_EVENT_PAYLOAD)]) as urlopen:
        result = run(scheduled_events.fetch_guild_scheduled_event("10", "1"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/scheduled-events/1"
    assert isinstance(result, GuildScheduledEvent)


def test_edit_guild_scheduled_event_only_sends_fields_that_were_set():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_EVENT_PAYLOAD)]) as urlopen:
        result = run(scheduled_events.edit_guild_scheduled_event("10", "1", status=2))

    assert json.loads(urlopen.call_args.args[0].data) == {"status": 2}
    assert isinstance(result, GuildScheduledEvent)


def test_edit_guild_scheduled_event_can_clear_channel_id_for_external():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_EVENT_PAYLOAD)]) as urlopen:
        run(scheduled_events.edit_guild_scheduled_event("10", "1", channel_id=None, entity_type=3))

    assert json.loads(urlopen.call_args.args[0].data) == {"channel_id": None, "entity_type": 3}


def test_delete_guild_scheduled_event_deletes_event():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(scheduled_events.delete_guild_scheduled_event("10", "1"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/scheduled-events/1"
    assert req.get_method() == "DELETE"


def test_fetch_guild_scheduled_event_users_returns_user_list():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_EVENT_USER_PAYLOAD])]) as urlopen:
        result = run(scheduled_events.fetch_guild_scheduled_event_users("10", "1"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/scheduled-events/1/users"
    assert result == [GuildScheduledEventUser(dict(_EVENT_USER_PAYLOAD, guild_id="10"))]
    assert result[0].user is not None
    assert result[0].user.username == "shiv"


def test_fetch_guild_scheduled_event_users_passes_query_params():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([])]) as urlopen:
        run(scheduled_events.fetch_guild_scheduled_event_users("10", "1", limit=5, with_member=True, before="90"))

    url = urlopen.call_args.args[0].full_url
    assert "limit=5" in url
    assert "with_member=true" in url
    assert "before=90" in url


# --- bot.<verb>() delegation ---


def test_bot_fetch_guild_scheduled_events_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_EVENT_PAYLOAD])]):
        assert run(bot.fetch_guild_scheduled_events("10")) == [GuildScheduledEvent(_EVENT_PAYLOAD)]


def test_bot_create_guild_scheduled_event_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_EVENT_PAYLOAD)]):
        result = run(bot.create_guild_scheduled_event("10", "shiv's game night", 2, "2024-01-01T00:00:00Z", 3))

    assert isinstance(result, GuildScheduledEvent)


def test_bot_fetch_guild_scheduled_event_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_EVENT_PAYLOAD)]):
        assert isinstance(run(bot.fetch_guild_scheduled_event("10", "1")), GuildScheduledEvent)


def test_bot_edit_guild_scheduled_event_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_EVENT_PAYLOAD)]):
        assert isinstance(run(bot.edit_guild_scheduled_event("10", "1", status=2)), GuildScheduledEvent)


def test_bot_delete_guild_scheduled_event_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(bot.delete_guild_scheduled_event("10", "1"))
    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/scheduled-events/1"


def test_bot_fetch_guild_scheduled_event_users_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_EVENT_USER_PAYLOAD])]):
        assert run(bot.fetch_guild_scheduled_event_users("10", "1")) == [
            GuildScheduledEventUser(dict(_EVENT_USER_PAYLOAD, guild_id="10"))
        ]


# --- guild.*() object-method delegation ---


def test_guild_fetch_scheduled_events_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_EVENT_PAYLOAD])]) as urlopen:
        result = run(guild.fetch_scheduled_events())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/scheduled-events"
    assert result == [GuildScheduledEvent(_EVENT_PAYLOAD)]


def test_guild_create_scheduled_event_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_EVENT_PAYLOAD)]) as urlopen:
        result = run(guild.create_scheduled_event("shiv's game night", 2, "2024-01-01T00:00:00Z", 3))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/scheduled-events"
    assert isinstance(result, GuildScheduledEvent)


def test_guild_fetch_scheduled_event_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_EVENT_PAYLOAD)]):
        assert isinstance(run(guild.fetch_scheduled_event("1")), GuildScheduledEvent)


# --- event.*() object-method delegation ---


def test_event_edit_delegates_to_rest_module():
    event = GuildScheduledEvent(_EVENT_PAYLOAD)
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_EVENT_PAYLOAD)]) as urlopen:
        result = run(event.edit(status=2))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/scheduled-events/1"
    assert json.loads(req.data) == {"status": 2}
    assert isinstance(result, GuildScheduledEvent)


def test_event_delete_delegates_to_rest_module():
    event = GuildScheduledEvent(_EVENT_PAYLOAD)
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(event.delete())

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/scheduled-events/1"
    assert req.get_method() == "DELETE"


def test_event_fetch_users_delegates_to_rest_module():
    event = GuildScheduledEvent(_EVENT_PAYLOAD)
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_EVENT_USER_PAYLOAD])]) as urlopen:
        result = run(event.fetch_users())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/scheduled-events/1/users"
    assert result == [GuildScheduledEventUser(dict(_EVENT_USER_PAYLOAD, guild_id="10"))]


def test_event_creator_is_none_when_absent():
    event = GuildScheduledEvent(_EVENT_PAYLOAD)
    assert event.creator is None


def test_event_creator_returns_user_when_present():
    event = GuildScheduledEvent(dict(_EVENT_PAYLOAD, creator={"id": "55", "username": "shiv"}))
    assert isinstance(event.creator, User)
    assert event.creator.username == "shiv"


def test_event_user_member_is_none_when_absent():
    event_user = GuildScheduledEventUser(_EVENT_USER_PAYLOAD)
    assert event_user.member is None


def test_event_user_member_returns_member_when_present():
    payload = dict(_EVENT_USER_PAYLOAD, member={"nick": "shiv"})
    event_user = GuildScheduledEventUser(payload)
    assert isinstance(event_user.member, Member)
    assert event_user.member.nick == "shiv"


def test_event_user_member_has_guild_id_stitched_in():
    """member.add_role()/kick()/etc. read guild_id straight off the member's
    own data, since Discord's member payload never carries it: fetch_guild_scheduled_event_users
    must stitch it in the same way fetch_guild_members does."""
    payload = dict(_EVENT_USER_PAYLOAD, guild_id="10", member={"nick": "shiv"})
    event_user = GuildScheduledEventUser(payload)
    assert event_user.member is not None
    assert event_user.member.guild_id == "10"


# --- exception.*() object-method delegation ---
