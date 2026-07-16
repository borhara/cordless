"""_rest/threads.py: thread REST endpoints, plus their bot.<verb>_thread() delegation."""

import os
from unittest.mock import patch

from conftest import FakeDiscordResponse

from cordless._rest import threads
from cordless._rest.models import Thread, ThreadMember
from cordless.app import Cordless

_ENV = {"DISCORD_BOT_TOKEN": "tok"}

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


def _urlopen(responses):
    return patch("cordless._rest._client.urllib.request.urlopen", side_effect=responses)


# --- start_thread_from_message ---


def test_start_thread_from_message_posts_expected_path_and_payload():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_THREAD_PAYLOAD)]) as urlopen:
        result = threads.start_thread_from_message("20", "99", "discussion", auto_archive_duration=1440)

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/messages/99/threads"
    assert req.get_method() == "POST"
    assert req.data == b'{"name": "discussion", "auto_archive_duration": 1440}'
    assert isinstance(result, Thread)
    assert result.id == "1"
    assert result.mention == "<#1>"
    assert result.archived is False


def test_start_thread_from_message_omits_auto_archive_duration_by_default():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_THREAD_PAYLOAD)]) as urlopen:
        threads.start_thread_from_message("20", "99", "discussion")

    assert urlopen.call_args.args[0].data == b'{"name": "discussion"}'


# --- start_thread_without_message ---


def test_start_thread_without_message_defaults_to_private_thread_type():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_THREAD_PAYLOAD)]) as urlopen:
        result = threads.start_thread_without_message("20", "discussion")

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/threads"
    assert req.data == b'{"name": "discussion", "type": 11}'
    assert isinstance(result, Thread)


def test_start_thread_without_message_passes_invitable():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_THREAD_PAYLOAD)]) as urlopen:
        threads.start_thread_without_message("20", "discussion", invitable=False)

    assert urlopen.call_args.args[0].data == b'{"name": "discussion", "type": 11, "invitable": false}'


# --- join/leave/add/remove thread member ---


def test_join_thread_puts_at_me():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        threads.join_thread("20")

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/thread-members/@me"
    assert req.get_method() == "PUT"


def test_leave_thread_deletes_at_me():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        threads.leave_thread("20")

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/thread-members/@me"
    assert req.get_method() == "DELETE"


def test_add_thread_member_puts_user_id():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        threads.add_thread_member("20", "55")

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/thread-members/55"


def test_remove_thread_member_deletes_user_id():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        threads.remove_thread_member("20", "55")

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/thread-members/55"
    assert req.get_method() == "DELETE"


# --- fetch_thread_members ---


def test_fetch_thread_members_returns_thread_member_list():
    payload = [{"id": "1", "user_id": "55", "join_timestamp": "t", "flags": 0}]
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(payload)]) as urlopen:
        result = threads.fetch_thread_members("20")

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/thread-members"
    assert result == [ThreadMember(id="1", user_id="55", join_timestamp="t", flags=0)]


def test_fetch_thread_members_with_member_flag_adds_query_string():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([])]) as urlopen:
        threads.fetch_thread_members("20", with_member=True)

    assert urlopen.call_args.args[0].full_url.endswith("?with_member=true")


# --- fetch_public_archived_threads ---


def test_fetch_public_archived_threads_returns_thread_list():
    payload = {"threads": [_THREAD_PAYLOAD], "members": [], "has_more": False}
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(payload)]) as urlopen:
        result = threads.fetch_public_archived_threads("20")

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/threads/archived/public"
    assert result == [Thread.from_dict(_THREAD_PAYLOAD)]


def test_fetch_public_archived_threads_passes_before_and_limit():
    payload = {"threads": [], "members": [], "has_more": False}
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(payload)]) as urlopen:
        threads.fetch_public_archived_threads("20", before="2024-01-01T00:00:00Z", limit=5)

    url = urlopen.call_args.args[0].full_url
    assert "before=2024-01-01T00%3A00%3A00Z" in url or "before=2024-01-01T00:00:00Z" in url
    assert "limit=5" in url


# --- bot.<verb>_thread() delegation ---


def test_bot_start_thread_from_message_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_THREAD_PAYLOAD)]):
        result = bot.start_thread_from_message("20", "99", "discussion")

    assert isinstance(result, Thread)
    assert result.name == "discussion"


def test_bot_fetch_public_archived_threads_delegates_to_rest_module():
    bot = Cordless()
    payload = {"threads": [_THREAD_PAYLOAD], "members": [], "has_more": False}
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(payload)]):
        result = bot.fetch_public_archived_threads("20")

    assert result == [Thread.from_dict(_THREAD_PAYLOAD)]
