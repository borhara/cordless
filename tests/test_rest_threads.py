"""_rest/threads.py: thread REST endpoints, plus their bot.<verb>_thread() and
Channel/Thread object-method delegation."""

import json
import os
from asyncio import run
from unittest.mock import patch

from conftest import BOT_ENV, FakeDiscordResponse, send_patch

from cordless._rest import threads
from cordless._rest.models import Thread, ThreadMember
from cordless.app import Cordless
from cordless.models import Channel, Guild

_THREAD_PAYLOAD = {
    "id": "1",
    "guild_id": "10",
    "parent_id": "20",
    "owner_id": "30",
    "name": "discussion",
    "type": 11,
    "message_count": 2,
    "member_count": 3,
    "thread_metadata": {"archived": False, "locked": False},
    "rate_limit_per_user": 0,
}


# --- Thread/ThreadMember expose unknown fields ---


def test_thread_exposes_a_field_not_declared_anywhere_in_cordless():
    """Thread used to filter to a fixed dataclass field set, silently
    dropping anything Discord added later. It should behave like every
    other resource and expose whatever the API actually sends."""
    thread = Thread({**_THREAD_PAYLOAD, "total_message_sent": 42})
    assert thread.total_message_sent == 42


def test_thread_member_exposes_a_field_not_declared_anywhere_in_cordless():
    member = ThreadMember({"id": "1", "user_id": "55", "member": {"nick": "shiv"}})
    assert member.member == {"nick": "shiv"}


# --- start_thread_from_message ---


def test_start_thread_from_message_posts_expected_path_and_payload():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_THREAD_PAYLOAD)]) as urlopen:
        result = run(threads.start_thread_from_message("20", "99", "discussion", auto_archive_duration=1440))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/messages/99/threads"
    assert req.get_method() == "POST"
    assert req.data == b'{"name": "discussion", "auto_archive_duration": 1440}'
    assert isinstance(result, Thread)
    assert result.id == "1"
    assert result.mention == "<#1>"
    assert result.archived is False
    assert result.locked is False


def test_start_thread_from_message_omits_auto_archive_duration_by_default():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_THREAD_PAYLOAD)]) as urlopen:
        run(threads.start_thread_from_message("20", "99", "discussion"))

    assert urlopen.call_args.args[0].data == b'{"name": "discussion"}'


# --- start_thread_without_message ---


def test_start_thread_without_message_defaults_to_private_thread_type():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_THREAD_PAYLOAD)]) as urlopen:
        result = run(threads.start_thread_without_message("20", "discussion"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/threads"
    assert req.data == b'{"name": "discussion", "type": 11}'
    assert isinstance(result, Thread)


def test_start_thread_without_message_passes_invitable():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_THREAD_PAYLOAD)]) as urlopen:
        run(threads.start_thread_without_message("20", "discussion", invitable=False))

    assert urlopen.call_args.args[0].data == b'{"name": "discussion", "type": 11, "invitable": false}'


# --- start_thread_from_forum ---


def test_start_thread_from_forum_posts_expected_path_and_payload():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_THREAD_PAYLOAD)]) as urlopen:
        result = run(threads.start_thread_from_forum("20", "discussion", message="first post"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/threads"
    assert req.get_method() == "POST"
    assert req.data == b'{"name": "discussion", "message": {"content": "first post"}}'
    # regression check: this used to be declared async without awaiting
    # anything, so calling it synchronously (as the bot.* wrapper did back
    # then) handed back an unawaited coroutine instead of a Thread
    assert isinstance(result, Thread)


def test_start_thread_from_forum_passes_applied_tags_and_auto_archive_duration():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_THREAD_PAYLOAD)]) as urlopen:
        run(
            threads.start_thread_from_forum(
                "20", "discussion", message="first post", applied_tags=["tag1"], auto_archive_duration=1440
            )
        )

    body = json.loads(urlopen.call_args.args[0].data)
    assert body["applied_tags"] == ["tag1"]
    assert body["auto_archive_duration"] == 1440


def test_start_thread_from_forum_omits_rate_limit_per_user_when_unset():
    """Leaving it unset should fall back to the forum channel's own
    default_thread_rate_limit_per_user, not silently send 0 (no slowmode)."""
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_THREAD_PAYLOAD)]) as urlopen:
        run(threads.start_thread_from_forum("20", "discussion", message="first post"))

    assert "rate_limit_per_user" not in json.loads(urlopen.call_args.args[0].data)


def test_start_thread_from_forum_passes_explicit_zero_rate_limit_per_user():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_THREAD_PAYLOAD)]) as urlopen:
        run(threads.start_thread_from_forum("20", "discussion", message="first post", rate_limit_per_user=0))

    assert json.loads(urlopen.call_args.args[0].data)["rate_limit_per_user"] == 0


def test_bot_start_thread_from_forum_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_THREAD_PAYLOAD)]):
        result = run(bot.start_thread_from_forum("20", "discussion", message="first post"))

    assert isinstance(result, Thread)
    assert result.name == "discussion"


# --- join/leave/add/remove thread member ---


def test_join_thread_puts_at_me():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(threads.join_thread("20"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/thread-members/@me"
    assert req.get_method() == "PUT"


def test_leave_thread_deletes_at_me():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(threads.leave_thread("20"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/thread-members/@me"
    assert req.get_method() == "DELETE"


def test_add_thread_member_puts_user_id():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(threads.add_thread_member("20", "55"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/thread-members/55"


def test_remove_thread_member_deletes_user_id():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(threads.remove_thread_member("20", "55"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/thread-members/55"
    assert req.get_method() == "DELETE"


# --- fetch_thread_members ---


def test_fetch_thread_members_returns_thread_member_list():
    payload = [{"id": "1", "user_id": "55", "join_timestamp": "t", "flags": 0}]
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]) as urlopen:
        result = run(threads.fetch_thread_members("20"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/thread-members"
    assert result == [ThreadMember({"id": "1", "user_id": "55", "join_timestamp": "t", "flags": 0})]


def test_fetch_thread_members_with_member_flag_adds_query_string():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([])]) as urlopen:
        run(threads.fetch_thread_members("20", with_member=True))

    assert urlopen.call_args.args[0].full_url.endswith("?with_member=true")


def test_fetch_thread_members_passes_after_and_limit():
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([])]) as urlopen:
        run(threads.fetch_thread_members("20", with_member=True, after="90", limit=50))

    url = urlopen.call_args.args[0].full_url
    assert "after=90" in url
    assert "limit=50" in url


# --- fetch_public_archived_threads ---


def test_fetch_public_archived_threads_returns_thread_list():
    payload = {"threads": [_THREAD_PAYLOAD], "members": [], "has_more": False}
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]) as urlopen:
        result = run(threads.fetch_public_archived_threads("20"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/threads/archived/public"
    assert result == [Thread(_THREAD_PAYLOAD)]


def test_fetch_public_archived_threads_passes_before_and_limit():
    payload = {"threads": [], "members": [], "has_more": False}
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]) as urlopen:
        run(threads.fetch_public_archived_threads("20", before="2024-01-01T00:00:00Z", limit=5))

    url = urlopen.call_args.args[0].full_url
    assert "before=2024-01-01T00%3A00%3A00Z" in url or "before=2024-01-01T00:00:00Z" in url
    assert "limit=5" in url


# --- bot.<verb>_thread() delegation ---


def test_bot_start_thread_from_message_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_THREAD_PAYLOAD)]):
        result = run(bot.start_thread_from_message("20", "99", "discussion"))

    assert isinstance(result, Thread)
    assert result.name == "discussion"


def test_bot_fetch_public_archived_threads_delegates_to_rest_module():
    bot = Cordless()
    payload = {"threads": [_THREAD_PAYLOAD], "members": [], "has_more": False}
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]):
        result = run(bot.fetch_public_archived_threads("20"))

    assert result == [Thread(_THREAD_PAYLOAD)]


# --- channel.*/thread.* object-method delegation ---


def test_channel_start_thread_without_message_delegates_to_rest_module():
    channel = Channel({"id": "20", "name": "general"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_THREAD_PAYLOAD)]) as urlopen:
        result = run(channel.start_thread_without_message("discussion"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/threads"
    assert isinstance(result, Thread)


def test_channel_start_thread_from_message_delegates_to_rest_module():
    channel = Channel({"id": "20", "name": "general"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_THREAD_PAYLOAD)]) as urlopen:
        result = run(channel.start_thread_from_message("99", "discussion"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/messages/99/threads"
    assert isinstance(result, Thread)


def test_channel_start_thread_from_forum_delegates_to_rest_module():
    channel = Channel({"id": "20", "name": "forum"})
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_THREAD_PAYLOAD)]):
        result = run(channel.start_thread_from_forum("discussion", message="first post"))

    assert isinstance(result, Thread)


def test_channel_fetch_public_archived_threads_delegates_to_rest_module():
    channel = Channel({"id": "20", "name": "general"})
    payload = {"threads": [_THREAD_PAYLOAD], "members": [], "has_more": False}
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]) as urlopen:
        result = run(channel.fetch_public_archived_threads())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/threads/archived/public"
    assert result == [Thread(_THREAD_PAYLOAD)]


def test_thread_join_delegates_to_rest_module():
    thread = Thread(_THREAD_PAYLOAD)
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(thread.join())

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/1/thread-members/@me"
    assert req.get_method() == "PUT"


def test_thread_leave_delegates_to_rest_module():
    thread = Thread(_THREAD_PAYLOAD)
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(thread.leave())

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/1/thread-members/@me"
    assert req.get_method() == "DELETE"


def test_thread_add_member_delegates_to_rest_module():
    thread = Thread(_THREAD_PAYLOAD)
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(thread.add_member("55"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/1/thread-members/55"
    assert req.get_method() == "PUT"


def test_thread_remove_member_delegates_to_rest_module():
    thread = Thread(_THREAD_PAYLOAD)
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(thread.remove_member("55"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/1/thread-members/55"
    assert req.get_method() == "DELETE"


def test_thread_fetch_members_delegates_to_rest_module():
    thread = Thread(_THREAD_PAYLOAD)
    payload = [{"id": "1", "user_id": "55", "join_timestamp": "t", "flags": 0}]
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]) as urlopen:
        result = run(thread.fetch_members())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/1/thread-members"
    assert result == [ThreadMember({"id": "1", "user_id": "55", "join_timestamp": "t", "flags": 0})]


def test_thread_fetch_members_passes_after_and_limit():
    thread = Thread(_THREAD_PAYLOAD)
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse([])]) as urlopen:
        run(thread.fetch_members(with_member=True, after="90", limit=50))

    url = urlopen.call_args.args[0].full_url
    assert "after=90" in url
    assert "limit=50" in url


# --- fetch_thread_member (single) ---


def test_fetch_thread_member_returns_single_member():
    payload = {"id": "1", "user_id": "55", "join_timestamp": "t", "flags": 0}
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]) as urlopen:
        result = run(threads.fetch_thread_member("20", "55"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/thread-members/55"
    assert result == ThreadMember({"id": "1", "user_id": "55", "join_timestamp": "t", "flags": 0})


def test_fetch_thread_member_with_member_flag_adds_query_string():
    payload = {"id": "1", "user_id": "55", "join_timestamp": "t", "flags": 0}
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]) as urlopen:
        run(threads.fetch_thread_member("20", "55", with_member=True))

    assert urlopen.call_args.args[0].full_url.endswith("?with_member=true")


def test_thread_fetch_member_delegates_to_rest_module():
    thread = Thread(_THREAD_PAYLOAD)
    payload = {"id": "1", "user_id": "55", "join_timestamp": "t", "flags": 0}
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]) as urlopen:
        result = run(thread.fetch_member("55"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/1/thread-members/55"
    assert result == ThreadMember({"id": "1", "user_id": "55", "join_timestamp": "t", "flags": 0})


# --- fetch_private_archived_threads / fetch_joined_private_archived_threads ---


def test_fetch_private_archived_threads_returns_thread_list():
    payload = {"threads": [_THREAD_PAYLOAD], "members": [], "has_more": False}
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]) as urlopen:
        result = run(threads.fetch_private_archived_threads("20"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/threads/archived/private"
    assert result == [Thread(_THREAD_PAYLOAD)]


def test_fetch_joined_private_archived_threads_returns_thread_list():
    payload = {"threads": [_THREAD_PAYLOAD], "members": [], "has_more": False}
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]) as urlopen:
        result = run(threads.fetch_joined_private_archived_threads("20"))

    url = urlopen.call_args.args[0].full_url
    assert url == "https://discord.com/api/v10/channels/20/users/@me/threads/archived/private"
    assert result == [Thread(_THREAD_PAYLOAD)]


def test_channel_fetch_private_archived_threads_delegates_to_rest_module():
    channel = Channel({"id": "20", "name": "general"})
    payload = {"threads": [_THREAD_PAYLOAD], "members": [], "has_more": False}
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]):
        result = run(channel.fetch_private_archived_threads())

    assert result == [Thread(_THREAD_PAYLOAD)]


def test_channel_fetch_joined_private_archived_threads_delegates_to_rest_module():
    channel = Channel({"id": "20", "name": "general"})
    payload = {"threads": [_THREAD_PAYLOAD], "members": [], "has_more": False}
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]):
        result = run(channel.fetch_joined_private_archived_threads())

    assert result == [Thread(_THREAD_PAYLOAD)]


# --- fetch_active_guild_threads ---


def test_fetch_active_guild_threads_returns_thread_list():
    payload = {"threads": [_THREAD_PAYLOAD], "members": []}
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]) as urlopen:
        result = run(threads.fetch_active_guild_threads("10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/threads/active"
    assert result == [Thread(_THREAD_PAYLOAD)]


def test_guild_fetch_active_threads_delegates_to_rest_module():
    guild = Guild({"id": "10", "name": "shiv's server"})
    payload = {"threads": [_THREAD_PAYLOAD], "members": []}
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]):
        result = run(guild.fetch_active_threads())

    assert result == [Thread(_THREAD_PAYLOAD)]


def test_bot_fetch_active_guild_threads_delegates_to_rest_module():
    bot = Cordless()
    payload = {"threads": [_THREAD_PAYLOAD], "members": []}
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]):
        result = run(bot.fetch_active_guild_threads("10"))

    assert result == [Thread(_THREAD_PAYLOAD)]


# --- remaining bot.<verb>_thread() delegation (one per mixin method not already exercised above) ---


def test_bot_start_thread_without_message_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(_THREAD_PAYLOAD)]):
        result = run(bot.start_thread_without_message("20", "discussion"))

    assert isinstance(result, Thread)


def test_bot_join_thread_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(bot.join_thread("20"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/thread-members/@me"


def test_bot_leave_thread_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(bot.leave_thread("20"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/thread-members/@me"
    assert req.get_method() == "DELETE"


def test_bot_add_thread_member_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(bot.add_thread_member("20", "55"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/thread-members/55"


def test_bot_remove_thread_member_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(None)]) as urlopen:
        run(bot.remove_thread_member("20", "55"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/thread-members/55"
    assert req.get_method() == "DELETE"


def test_bot_fetch_thread_member_delegates_to_rest_module():
    bot = Cordless()
    payload = {"id": "1", "user_id": "55", "join_timestamp": "t", "flags": 0}
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]):
        result = run(bot.fetch_thread_member("20", "55"))

    assert result == ThreadMember({"id": "1", "user_id": "55", "join_timestamp": "t", "flags": 0})


def test_bot_fetch_thread_members_delegates_to_rest_module():
    bot = Cordless()
    payload = [{"id": "1", "user_id": "55", "join_timestamp": "t", "flags": 0}]
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]):
        result = run(bot.fetch_thread_members("20"))

    assert result == [ThreadMember({"id": "1", "user_id": "55", "join_timestamp": "t", "flags": 0})]


def test_bot_fetch_private_archived_threads_delegates_to_rest_module():
    bot = Cordless()
    payload = {"threads": [_THREAD_PAYLOAD], "members": [], "has_more": False}
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]) as urlopen:
        result = run(bot.fetch_private_archived_threads("20"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/threads/archived/private"
    assert result == [Thread(_THREAD_PAYLOAD)]


def test_bot_fetch_joined_private_archived_threads_delegates_to_rest_module():
    bot = Cordless()
    payload = {"threads": [_THREAD_PAYLOAD], "members": [], "has_more": False}
    with patch.dict(os.environ, BOT_ENV), send_patch([FakeDiscordResponse(payload)]) as urlopen:
        result = run(bot.fetch_joined_private_archived_threads("20"))

    url = urlopen.call_args.args[0].full_url
    assert url == "https://discord.com/api/v10/channels/20/users/@me/threads/archived/private"
    assert result == [Thread(_THREAD_PAYLOAD)]
