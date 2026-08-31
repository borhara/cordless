"""_rest/channels.py: channel REST endpoints, plus their bot.<verb>_channel()
and Channel/Guild/Message object-method delegation."""

import json
import os
from asyncio import run
from unittest.mock import patch

from conftest import BOT_ENV, FakeDiscordResponse, send_patch

from cordless._rest import channels
from cordless._rest.models import FollowedChannel, Invite, MessagePin
from cordless.app import Cordless
from cordless.models import Channel, Guild, Message

_CHANNEL_PAYLOAD = {
    "id": "20",
    "guild_id": "10",
    "name": "general",
    "type": 0,
    "position": 0,
}

_INVITE_PAYLOAD = {"code": "abc123", "guild_id": "10", "channel_id": "20", "uses": 0}

_FOLLOWED_PAYLOAD = {"channel_id": "20", "webhook_id": "99"}

_MESSAGE_PAYLOAD = {"id": "1", "channel_id": "20", "content": "shiv was here"}

_PIN_PAYLOAD = {"pinned_at": "2024-01-01T00:00:00Z", "message": _MESSAGE_PAYLOAD}


# --- fetch_channel / edit_channel / delete_channel ---


def test_fetch_channel_returns_channel():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_CHANNEL_PAYLOAD)]) as urlopen:
        result = run(channels.fetch_channel("20"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20"
    assert urlopen.call_args.args[0].get_method() == "GET"
    assert isinstance(result, Channel)
    assert result.name == "general"


def test_edit_channel_only_sends_fields_that_were_set():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_CHANNEL_PAYLOAD)]) as urlopen:
        run(channels.edit_channel("20", name="renamed", nsfw=True))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20"
    assert req.get_method() == "PATCH"
    assert json.loads(req.data) == {"name": "renamed", "nsfw": True}


def test_edit_channel_supports_thread_only_fields():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_CHANNEL_PAYLOAD)]) as urlopen:
        run(channels.edit_channel("20", archived=True, locked=True))

    body = json.loads(urlopen.call_args.args[0].data)
    assert body == {"archived": True, "locked": True}


def test_delete_channel_returns_the_deleted_channel():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_CHANNEL_PAYLOAD)]) as urlopen:
        result = run(channels.delete_channel("20"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20"
    assert req.get_method() == "DELETE"
    assert isinstance(result, Channel)


# --- permission overwrites ---


def test_edit_channel_permissions_puts_type_and_bitfields():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(channels.edit_channel_permissions("20", "55", type=0, allow="1024", deny="2048"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/permissions/55"
    assert req.get_method() == "PUT"
    assert json.loads(req.data) == {"type": 0, "allow": "1024", "deny": "2048"}


def test_delete_channel_permission_deletes_overwrite():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(channels.delete_channel_permission("20", "55"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/permissions/55"
    assert req.get_method() == "DELETE"


# --- invites ---


def test_fetch_channel_invites_returns_invite_list():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_INVITE_PAYLOAD])]) as urlopen:
        result = run(channels.fetch_channel_invites("20"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/invites"
    assert result == [Invite(_INVITE_PAYLOAD)]
    assert result[0].url == "https://discord.gg/abc123"


def test_create_channel_invite_posts_expected_fields():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_INVITE_PAYLOAD)]) as urlopen:
        result = run(channels.create_channel_invite("20", max_age=3600, max_uses=5, temporary=True))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/invites"
    assert json.loads(req.data) == {"max_age": 3600, "max_uses": 5, "temporary": True}
    assert isinstance(result, Invite)


def test_create_channel_invite_omits_unset_fields():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_INVITE_PAYLOAD)]) as urlopen:
        run(channels.create_channel_invite("20"))

    assert json.loads(urlopen.call_args.args[0].data) == {}


# --- follow announcement ---


def test_follow_announcement_channel_posts_webhook_channel_id():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_FOLLOWED_PAYLOAD)]) as urlopen:
        result = run(channels.follow_announcement_channel("20", "30"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/followers"
    assert json.loads(req.data) == {"webhook_channel_id": "30"}
    assert isinstance(result, FollowedChannel)
    assert result.webhook_id == "99"


# --- typing / voice status ---


def test_trigger_typing_posts_to_typing_endpoint():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(channels.trigger_typing("20"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/typing"
    assert req.get_method() == "POST"


def test_set_voice_channel_status_puts_status():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(channels.set_voice_channel_status("20", "shiv is streaming"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/voice-status"
    assert req.get_method() == "PUT"
    assert json.loads(req.data) == {"status": "shiv is streaming"}


def test_set_voice_channel_status_clears_with_none():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(channels.set_voice_channel_status("20"))

    assert json.loads(urlopen.call_args.args[0].data) == {"status": None}


# --- group DM recipients ---


def test_add_group_dm_recipient_puts_access_token_and_nick():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(channels.add_group_dm_recipient("20", "55", "oauth-token", nick="shiv"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/recipients/55"
    assert json.loads(req.data) == {"access_token": "oauth-token", "nick": "shiv"}


def test_remove_group_dm_recipient_deletes_recipient():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(channels.remove_group_dm_recipient("20", "55"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/recipients/55"
    assert req.get_method() == "DELETE"


# --- pins ---


def test_fetch_channel_pins_returns_message_pin_list():
    with (
        patch.dict(os.environ, BOT_ENV),
        send_patch([FakeDiscordResponse({"items": [_PIN_PAYLOAD], "has_more": False})]),
    ):
        result = run(channels.fetch_channel_pins("20"))

    assert len(result) == 1
    assert isinstance(result[0], MessagePin)
    assert result[0].pinned_at == "2024-01-01T00:00:00Z"
    assert isinstance(result[0].message, Message)
    assert result[0].message.content == "shiv was here"


def test_fetch_channel_pins_passes_before_and_limit():
    payload = {"items": [], "has_more": False}
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]) as urlopen:
        run(channels.fetch_channel_pins("20", before="2024-01-01T00:00:00Z", limit=10))

    url = urlopen.call_args.args[0].full_url
    assert "before=2024-01-01T00" in url
    assert "limit=10" in url


def test_pin_message_puts_message_id():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(channels.pin_message("20", "99"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/messages/pins/99"
    assert req.get_method() == "PUT"


def test_unpin_message_deletes_message_id():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(channels.unpin_message("20", "99"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/messages/pins/99"
    assert req.get_method() == "DELETE"


# --- guild-scoped channel endpoints ---


def test_fetch_guild_channels_returns_channel_list():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_CHANNEL_PAYLOAD])]) as urlopen:
        result = run(channels.fetch_guild_channels("10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/channels"
    assert result == [Channel(_CHANNEL_PAYLOAD)]


def test_create_guild_channel_posts_name_and_type():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_CHANNEL_PAYLOAD)]) as urlopen:
        result = run(channels.create_guild_channel("10", "general", type=0))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/channels"
    assert json.loads(req.data) == {"name": "general", "type": 0}
    assert isinstance(result, Channel)


def test_create_guild_channel_supports_forum_specific_fields():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_CHANNEL_PAYLOAD)]) as urlopen:
        run(channels.create_guild_channel("10", "help-desk", type=15, default_sort_order=1))

    body = json.loads(urlopen.call_args.args[0].data)
    assert body == {"name": "help-desk", "type": 15, "default_sort_order": 1}


def test_edit_guild_channel_positions_sends_raw_list_body():
    positions = [{"id": "20", "position": 1}, {"id": "21", "position": 0}]
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(channels.edit_guild_channel_positions("10", positions))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/channels"
    assert req.get_method() == "PATCH"
    assert json.loads(req.data) == positions


# --- bot.<verb>() delegation ---


def test_bot_edit_channel_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_CHANNEL_PAYLOAD)]):
        result = run(bot.edit_channel("20", name="renamed"))

    assert isinstance(result, Channel)


def test_bot_create_guild_channel_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_CHANNEL_PAYLOAD)]):
        result = run(bot.create_guild_channel("10", "general"))

    assert isinstance(result, Channel)


# --- channel.*/guild.*/message.* object-method delegation ---


def test_channel_fetch_delegates_to_rest_module():
    channel = Channel({"id": "20", "name": "general"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_CHANNEL_PAYLOAD)]) as urlopen:
        result = run(channel.fetch())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20"
    assert isinstance(result, Channel)


def test_channel_edit_delegates_to_rest_module():
    channel = Channel({"id": "20", "name": "general"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_CHANNEL_PAYLOAD)]) as urlopen:
        result = run(channel.edit(topic="new topic"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20"
    assert json.loads(req.data) == {"topic": "new topic"}
    assert isinstance(result, Channel)


def test_channel_delete_delegates_to_rest_module():
    channel = Channel({"id": "20", "name": "general"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_CHANNEL_PAYLOAD)]):
        result = run(channel.delete())

    assert isinstance(result, Channel)


def test_channel_set_permissions_delegates_to_rest_module():
    channel = Channel({"id": "20", "name": "general"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(channel.set_permissions("55", type=1, allow="1024"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/permissions/55"
    assert json.loads(req.data) == {"type": 1, "allow": "1024"}


def test_channel_delete_permission_delegates_to_rest_module():
    channel = Channel({"id": "20", "name": "general"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(channel.delete_permission("55"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/permissions/55"


def test_channel_fetch_invites_delegates_to_rest_module():
    channel = Channel({"id": "20", "name": "general"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_INVITE_PAYLOAD])]):
        result = run(channel.fetch_invites())

    assert result == [Invite(_INVITE_PAYLOAD)]


def test_channel_create_invite_delegates_to_rest_module():
    channel = Channel({"id": "20", "name": "general"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_INVITE_PAYLOAD)]):
        result = run(channel.create_invite(max_uses=1))

    assert isinstance(result, Invite)


def test_channel_follow_announcement_delegates_to_rest_module():
    channel = Channel({"id": "20", "name": "announcements"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_FOLLOWED_PAYLOAD)]):
        result = run(channel.follow_announcement("30"))

    assert isinstance(result, FollowedChannel)


def test_channel_trigger_typing_delegates_to_rest_module():
    channel = Channel({"id": "20", "name": "general"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(channel.trigger_typing())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/typing"


def test_channel_set_voice_status_delegates_to_rest_module():
    channel = Channel({"id": "20", "name": "General"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(channel.set_voice_status("shiv's stream"))

    assert json.loads(urlopen.call_args.args[0].data) == {"status": "shiv's stream"}


def test_channel_add_recipient_delegates_to_rest_module():
    channel = Channel({"id": "20", "name": "group dm"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(channel.add_recipient("55", "oauth-token"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/recipients/55"


def test_channel_remove_recipient_delegates_to_rest_module():
    channel = Channel({"id": "20", "name": "group dm"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(channel.remove_recipient("55"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/recipients/55"


def test_channel_fetch_pins_delegates_to_rest_module():
    channel = Channel({"id": "20", "name": "general"})
    payload = {"items": [_PIN_PAYLOAD], "has_more": False}
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]):
        result = run(channel.fetch_pins())

    assert len(result) == 1
    assert isinstance(result[0], MessagePin)


def test_channel_pin_message_delegates_to_rest_module():
    channel = Channel({"id": "20", "name": "general"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(channel.pin_message("99"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/messages/pins/99"


def test_channel_unpin_message_delegates_to_rest_module():
    channel = Channel({"id": "20", "name": "general"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(channel.unpin_message("99"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/messages/pins/99"
    assert req.get_method() == "DELETE"


def test_guild_create_channel_delegates_to_rest_module():
    guild = Guild({"id": "10", "name": "shiv's server"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_CHANNEL_PAYLOAD)]) as urlopen:
        result = run(guild.create_channel("general", type=0))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/channels"
    assert json.loads(req.data) == {"name": "general", "type": 0}
    assert isinstance(result, Channel)


def test_guild_fetch_channels_delegates_to_rest_module():
    guild = Guild({"id": "10", "name": "shiv's server"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_CHANNEL_PAYLOAD])]):
        result = run(guild.fetch_channels())

    assert result == [Channel(_CHANNEL_PAYLOAD)]


def test_guild_edit_channel_positions_delegates_to_rest_module():
    guild = Guild({"id": "10", "name": "shiv's server"})
    positions = [{"id": "20", "position": 1}]
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(guild.edit_channel_positions(positions))

    assert json.loads(urlopen.call_args.args[0].data) == positions


def test_message_pin_delegates_to_rest_module():
    message = Message(_MESSAGE_PAYLOAD)
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(message.pin())

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/messages/pins/1"
    assert req.get_method() == "PUT"


def test_message_unpin_delegates_to_rest_module():
    message = Message(_MESSAGE_PAYLOAD)
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(message.unpin())

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/messages/pins/1"
    assert req.get_method() == "DELETE"


# --- remaining bot.<verb>() delegation (one per mixin method not already exercised above) ---


def test_bot_fetch_channel_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_CHANNEL_PAYLOAD)]) as urlopen:
        result = run(bot.fetch_channel("20"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20"
    assert isinstance(result, Channel)


def test_bot_delete_channel_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_CHANNEL_PAYLOAD)]) as urlopen:
        result = run(bot.delete_channel("20"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20"
    assert req.get_method() == "DELETE"
    assert isinstance(result, Channel)


def test_bot_edit_channel_permissions_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(bot.edit_channel_permissions("20", "55", type=0, allow="1024"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/permissions/55"
    assert json.loads(req.data) == {"type": 0, "allow": "1024"}


def test_bot_delete_channel_permission_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(bot.delete_channel_permission("20", "55"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/permissions/55"
    assert req.get_method() == "DELETE"


def test_bot_fetch_channel_invites_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_INVITE_PAYLOAD])]):
        result = run(bot.fetch_channel_invites("20"))

    assert result == [Invite(_INVITE_PAYLOAD)]


def test_bot_create_channel_invite_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_INVITE_PAYLOAD)]):
        result = run(bot.create_channel_invite("20", max_uses=1))

    assert isinstance(result, Invite)


def test_bot_follow_announcement_channel_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_FOLLOWED_PAYLOAD)]) as urlopen:
        result = run(bot.follow_announcement_channel("20", "30"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/followers"
    assert json.loads(req.data) == {"webhook_channel_id": "30"}
    assert isinstance(result, FollowedChannel)


def test_bot_trigger_typing_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(bot.trigger_typing("20"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/typing"
    assert req.get_method() == "POST"


def test_bot_set_voice_channel_status_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(bot.set_voice_channel_status("20", "shiv is live"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/voice-status"
    assert json.loads(req.data) == {"status": "shiv is live"}


def test_bot_add_group_dm_recipient_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(bot.add_group_dm_recipient("20", "55", "oauth-token", nick="shiv"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/recipients/55"
    assert json.loads(req.data) == {"access_token": "oauth-token", "nick": "shiv"}


def test_bot_remove_group_dm_recipient_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(bot.remove_group_dm_recipient("20", "55"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/recipients/55"
    assert req.get_method() == "DELETE"


def test_bot_fetch_channel_pins_delegates_to_rest_module():
    bot = Cordless()
    payload = {"items": [_PIN_PAYLOAD], "has_more": False}
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]):
        result = run(bot.fetch_channel_pins("20"))

    assert len(result) == 1
    assert isinstance(result[0], MessagePin)


def test_bot_pin_message_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(bot.pin_message("20", "99"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/messages/pins/99"
    assert req.get_method() == "PUT"


def test_bot_unpin_message_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(bot.unpin_message("20", "99"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/messages/pins/99"
    assert req.get_method() == "DELETE"


def test_bot_fetch_guild_channels_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([_CHANNEL_PAYLOAD])]):
        result = run(bot.fetch_guild_channels("10"))

    assert result == [Channel(_CHANNEL_PAYLOAD)]


def test_bot_edit_guild_channel_positions_delegates_to_rest_module():
    bot = Cordless()
    positions = [{"id": "20", "position": 1}]
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(bot.edit_guild_channel_positions("10", positions))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/channels"
    assert json.loads(req.data) == positions
