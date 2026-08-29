"""_rest/messages.py: message and reaction REST endpoints, plus their
bot.<verb>() and Channel/Guild/Message object-method delegation."""

import json
import os
from asyncio import run
from unittest.mock import patch

from conftest import FakeDiscordResponse

from cordless._rest import messages
from cordless._rest.models import MessageSearchResult
from cordless.app import Cordless
from cordless.models import Channel, Guild, Message, User

_ENV = {"DISCORD_BOT_TOKEN": "tok"}

_MESSAGE_PAYLOAD = {"id": "1", "channel_id": "20", "content": "shiv was here"}
_USER_PAYLOAD = {"id": "55", "username": "shiv"}


def _urlopen(responses):
    return patch("cordless._rest._client._send", side_effect=responses)


# --- fetch_channel_messages / fetch_message ---


def test_fetch_channel_messages_returns_message_list():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_MESSAGE_PAYLOAD])]) as urlopen:
        result = run(messages.fetch_channel_messages("20"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/messages"
    assert result == [Message(_MESSAGE_PAYLOAD)]


def test_fetch_channel_messages_passes_around_before_after_limit():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([])]) as urlopen:
        run(messages.fetch_channel_messages("20", before="90", limit=10))

    url = urlopen.call_args.args[0].full_url
    assert "before=90" in url
    assert "limit=10" in url


def test_fetch_message_returns_single_message():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MESSAGE_PAYLOAD)]) as urlopen:
        result = run(messages.fetch_message("20", "1"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/messages/1"
    assert isinstance(result, Message)


# --- create_message ---


def test_create_message_posts_content():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MESSAGE_PAYLOAD)]) as urlopen:
        result = run(messages.create_message("20", content="shiv says hi"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/messages"
    assert json.loads(req.data) == {"content": "shiv says hi"}
    assert isinstance(result, Message)


def test_create_message_sets_components_v2_flag():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MESSAGE_PAYLOAD)]) as urlopen:
        run(messages.create_message("20", components=[{"type": 17, "components": []}]))

    body = json.loads(urlopen.call_args.args[0].data)
    assert body["flags"] & 32768


def test_create_message_supports_reply_via_message_reference():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MESSAGE_PAYLOAD)]) as urlopen:
        run(messages.create_message("20", content="reply", message_reference={"message_id": "5"}))

    body = json.loads(urlopen.call_args.args[0].data)
    assert body["message_reference"] == {"message_id": "5"}


def test_create_message_passes_embeds_nonce_allowed_mentions_enforce_nonce():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MESSAGE_PAYLOAD)]) as urlopen:
        run(
            messages.create_message(
                "20",
                embeds=[{"title": "hi"}],
                nonce="shiv-1",
                allowed_mentions={"parse": []},
                enforce_nonce=True,
            )
        )

    body = json.loads(urlopen.call_args.args[0].data)
    assert body["embeds"] == [{"title": "hi"}]
    assert body["nonce"] == "shiv-1"
    assert body["allowed_mentions"] == {"parse": []}
    assert body["enforce_nonce"] is True


def test_create_message_passes_sticker_ids_and_poll():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MESSAGE_PAYLOAD)]) as urlopen:
        run(messages.create_message("20", sticker_ids=["1"], poll={"question": {"text": "tabs or spaces?"}}))

    body = json.loads(urlopen.call_args.args[0].data)
    assert body["sticker_ids"] == ["1"]
    assert body["poll"] == {"question": {"text": "tabs or spaces?"}}


# --- crosspost / edit / delete / bulk delete ---


def test_crosspost_message_posts_crosspost_path():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MESSAGE_PAYLOAD)]) as urlopen:
        result = run(messages.crosspost_message("20", "1"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/messages/1/crosspost"
    assert req.get_method() == "POST"
    assert isinstance(result, Message)


def test_edit_channel_message_only_sends_fields_that_were_set():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MESSAGE_PAYLOAD)]) as urlopen:
        run(messages.edit_channel_message("20", "1", content="edited"))

    assert json.loads(urlopen.call_args.args[0].data) == {"content": "edited"}


def test_edit_channel_message_sends_explicit_none_to_clear_content():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MESSAGE_PAYLOAD)]) as urlopen:
        run(messages.edit_channel_message("20", "1", content=None))

    assert json.loads(urlopen.call_args.args[0].data) == {"content": None}


def test_edit_channel_message_sets_components_v2_flag():
    """Regression: the flag computation used to only live in create_message,
    so editing a message into Components v2 never set the flag."""
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MESSAGE_PAYLOAD)]) as urlopen:
        run(messages.edit_channel_message("20", "1", components=[{"type": 17, "components": []}]))

    body = json.loads(urlopen.call_args.args[0].data)
    assert body["flags"] & 32768


def test_edit_channel_message_respects_explicit_flags_without_uikit():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MESSAGE_PAYLOAD)]) as urlopen:
        run(messages.edit_channel_message("20", "1", flags=4))

    assert json.loads(urlopen.call_args.args[0].data) == {"flags": 4}


def test_edit_channel_message_explicit_flags_zero_still_sends_it():
    """flags=0 means clear the flags, distinct from omitting flags
    entirely, which leaves them untouched."""
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MESSAGE_PAYLOAD)]) as urlopen:
        run(messages.edit_channel_message("20", "1", flags=0))

    assert json.loads(urlopen.call_args.args[0].data) == {"flags": 0}


def test_edit_channel_message_omitted_flags_are_not_sent():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MESSAGE_PAYLOAD)]) as urlopen:
        run(messages.edit_channel_message("20", "1", content="edited"))

    assert "flags" not in json.loads(urlopen.call_args.args[0].data)


def test_edit_channel_message_keeps_retained_attachments_alongside_new_files():
    """Regression: a new file's attachments metadata used to overwrite the
    caller's explicit attachments=... (the retained-attachment list), losing
    the request to keep the existing attachment."""
    from cordless._multipart import parse_multipart_payload

    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MESSAGE_PAYLOAD)]) as urlopen:
        run(messages.edit_channel_message("20", "1", files=[("new.png", b"data")], attachments=[{"id": "123"}]))

    payload = parse_multipart_payload(urlopen.call_args.args[0].data)
    assert payload["attachments"] == [{"id": "123"}, {"id": 0, "filename": "new.png"}]


def test_delete_channel_message_deletes_message():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(messages.delete_channel_message("20", "1"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/messages/1"
    assert req.get_method() == "DELETE"


def test_bulk_delete_messages_posts_message_ids():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(messages.bulk_delete_messages("20", ["1", "2", "3"]))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/messages/bulk-delete"
    assert json.loads(req.data) == {"messages": ["1", "2", "3"]}


# --- reactions ---


def test_create_reaction_puts_at_me():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(messages.create_reaction("20", "1", "🎉"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/messages/1/reactions/%F0%9F%8E%89/@me"
    assert req.get_method() == "PUT"


def test_create_reaction_url_encodes_custom_emoji():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(messages.create_reaction("20", "1", "shiv:12345"))

    assert "shiv%3A12345" in urlopen.call_args.args[0].full_url


def test_delete_own_reaction_deletes_at_me():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(messages.delete_own_reaction("20", "1", "🎉"))

    req = urlopen.call_args.args[0]
    assert req.full_url.endswith("/@me")
    assert req.get_method() == "DELETE"


def test_delete_user_reaction_deletes_specific_user():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(messages.delete_user_reaction("20", "1", "🎉", "55"))

    req = urlopen.call_args.args[0]
    assert req.full_url.endswith("/55")
    assert req.get_method() == "DELETE"


def test_fetch_reactions_returns_user_list():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_USER_PAYLOAD])]) as urlopen:
        result = run(messages.fetch_reactions("20", "1", "🎉"))

    assert "/reactions/%F0%9F%8E%89" in urlopen.call_args.args[0].full_url
    assert result == [User(_USER_PAYLOAD)]


def test_fetch_reactions_passes_type_after_limit():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([])]) as urlopen:
        run(messages.fetch_reactions("20", "1", "🎉", type=1, after="90", limit=5))

    url = urlopen.call_args.args[0].full_url
    assert "type=1" in url
    assert "after=90" in url
    assert "limit=5" in url


def test_delete_all_reactions_deletes_reactions_root():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(messages.delete_all_reactions("20", "1"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/messages/1/reactions"
    assert req.get_method() == "DELETE"


def test_delete_all_reactions_for_emoji_deletes_just_that_emoji():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(messages.delete_all_reactions_for_emoji("20", "1", "🎉"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/messages/1/reactions/%F0%9F%8E%89"
    assert req.get_method() == "DELETE"


# --- search_guild_messages ---


def test_search_guild_messages_builds_repeated_array_query_params():
    payload = {"total_results": 0, "doing_deep_historical_index": False, "messages": []}
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(payload)]) as urlopen:
        run(messages.search_guild_messages("10", author_id=["1", "2"], content="shiv"))

    url = urlopen.call_args.args[0].full_url
    assert "author_id=1" in url
    assert "author_id=2" in url
    assert "content=shiv" in url


def test_search_guild_messages_sends_lowercase_booleans():
    """Discord's search endpoint expects true/false, not Python's True/False."""
    payload = {"total_results": 0, "doing_deep_historical_index": False, "messages": []}
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(payload)]) as urlopen:
        run(messages.search_guild_messages("10", pinned=True, mention_everyone=False))

    url = urlopen.call_args.args[0].full_url
    assert "pinned=true" in url
    assert "mention_everyone=false" in url


def test_search_guild_messages_flattens_nested_message_arrays():
    payload = {
        "total_results": 1,
        "doing_deep_historical_index": False,
        "messages": [[_MESSAGE_PAYLOAD]],
        "threads": [],
        "members": [],
    }
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(payload)]):
        result = run(messages.search_guild_messages("10"))

    assert isinstance(result, MessageSearchResult)
    assert result.total_results == 1
    assert result.messages == [Message(_MESSAGE_PAYLOAD)]
    assert result.threads == []
    assert result.members == []


# --- polls ---


def test_fetch_poll_answer_voters_returns_user_list():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse({"users": [_USER_PAYLOAD]})]) as urlopen:
        result = run(messages.fetch_poll_answer_voters("20", "1", "3"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/polls/1/answers/3"
    assert result == [User(_USER_PAYLOAD)]


def test_fetch_poll_answer_voters_passes_after_and_limit():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse({"users": []})]) as urlopen:
        run(messages.fetch_poll_answer_voters("20", "1", "3", after="90", limit=10))

    url = urlopen.call_args.args[0].full_url
    assert "after=90" in url
    assert "limit=10" in url


def test_expire_poll_returns_updated_message():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MESSAGE_PAYLOAD)]) as urlopen:
        result = run(messages.expire_poll("20", "1"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/polls/1/expire"
    assert req.get_method() == "POST"
    assert isinstance(result, Message)


# --- bot.send_message()/edit_message() still work, now returning the Message ---


def test_bot_send_message_returns_the_sent_message():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MESSAGE_PAYLOAD)]):
        result = run(bot.send_message("20", "hi"))

    assert isinstance(result, Message)


def test_bot_edit_message_returns_the_edited_message():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MESSAGE_PAYLOAD)]):
        result = run(bot.edit_message("20", "1", "edited"))

    assert isinstance(result, Message)


def test_bot_edit_message_default_none_does_not_clear_content():
    """bot.edit_message()'s content=None means untouched, not cleared -
    unlike messages.edit_channel_message()'s own content=None."""
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MESSAGE_PAYLOAD)]) as urlopen:
        run(bot.edit_message("20", "1", embeds=[{"title": "hi"}]))

    body = json.loads(urlopen.call_args.args[0].data)
    assert "content" not in body
    assert body["embeds"] == [{"title": "hi"}]


def test_bot_delete_message_still_works():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(bot.delete_message("20", "1"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/messages/1"
    assert req.get_method() == "DELETE"


# --- bot.<verb>() delegation for the rest of the mixin methods ---


def test_bot_fetch_channel_messages_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_MESSAGE_PAYLOAD])]):
        assert run(bot.fetch_channel_messages("20")) == [Message(_MESSAGE_PAYLOAD)]


def test_bot_fetch_message_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MESSAGE_PAYLOAD)]):
        assert isinstance(run(bot.fetch_message("20", "1")), Message)


def test_bot_crosspost_message_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MESSAGE_PAYLOAD)]) as urlopen:
        run(bot.crosspost_message("20", "1"))
    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/messages/1/crosspost"


def test_bot_bulk_delete_messages_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(bot.bulk_delete_messages("20", ["1", "2"]))
    assert json.loads(urlopen.call_args.args[0].data) == {"messages": ["1", "2"]}


def test_bot_create_reaction_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(bot.create_reaction("20", "1", "🎉"))
    assert urlopen.call_args.args[0].get_method() == "PUT"


def test_bot_delete_own_reaction_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(bot.delete_own_reaction("20", "1", "🎉"))
    assert urlopen.call_args.args[0].full_url.endswith("/@me")


def test_bot_delete_user_reaction_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(bot.delete_user_reaction("20", "1", "🎉", "55"))
    assert urlopen.call_args.args[0].full_url.endswith("/55")


def test_bot_fetch_reactions_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_USER_PAYLOAD])]):
        assert run(bot.fetch_reactions("20", "1", "🎉")) == [User(_USER_PAYLOAD)]


def test_bot_delete_all_reactions_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(bot.delete_all_reactions("20", "1"))
    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/messages/1/reactions"


def test_bot_delete_all_reactions_for_emoji_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(bot.delete_all_reactions_for_emoji("20", "1", "🎉"))
    assert "%F0%9F%8E%89" in urlopen.call_args.args[0].full_url


def test_bot_search_guild_messages_delegates_to_rest_module():
    bot = Cordless()
    payload = {"total_results": 0, "doing_deep_historical_index": False, "messages": []}
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(payload)]):
        assert isinstance(run(bot.search_guild_messages("10")), MessageSearchResult)


def test_bot_fetch_poll_answer_voters_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse({"users": [_USER_PAYLOAD]})]):
        assert run(bot.fetch_poll_answer_voters("20", "1", "3")) == [User(_USER_PAYLOAD)]


def test_bot_expire_poll_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MESSAGE_PAYLOAD)]) as urlopen:
        run(bot.expire_poll("20", "1"))
    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/polls/1/expire"


# --- channel.*()/guild.*() object-method delegation ---


def test_channel_fetch_messages_delegates_to_rest_module():
    channel = Channel({"id": "20"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_MESSAGE_PAYLOAD])]) as urlopen:
        result = run(channel.fetch_messages())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/messages"
    assert result == [Message(_MESSAGE_PAYLOAD)]


def test_channel_fetch_message_delegates_to_rest_module():
    channel = Channel({"id": "20"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MESSAGE_PAYLOAD)]) as urlopen:
        result = run(channel.fetch_message("1"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/messages/1"
    assert isinstance(result, Message)


def test_channel_send_delegates_to_rest_module():
    channel = Channel({"id": "20"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MESSAGE_PAYLOAD)]) as urlopen:
        result = run(channel.send(content="hi", tts=True))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/messages"
    assert json.loads(req.data) == {"content": "hi", "tts": True}
    assert isinstance(result, Message)


def test_channel_bulk_delete_messages_delegates_to_rest_module():
    channel = Channel({"id": "20"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(channel.bulk_delete_messages(["1", "2"]))

    assert json.loads(urlopen.call_args.args[0].data) == {"messages": ["1", "2"]}


def test_guild_search_messages_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    payload = {"total_results": 0, "doing_deep_historical_index": False, "messages": []}
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(payload)]) as urlopen:
        result = run(guild.search_messages(content="shiv"))

    assert "content=shiv" in urlopen.call_args.args[0].full_url
    assert isinstance(result, MessageSearchResult)


# --- message.*() object-method delegation ---


def test_message_fetch_delegates_to_rest_module():
    message = Message(_MESSAGE_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MESSAGE_PAYLOAD)]) as urlopen:
        result = run(message.fetch())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/messages/1"
    assert isinstance(result, Message)


def test_message_edit_delegates_to_rest_module():
    message = Message(_MESSAGE_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MESSAGE_PAYLOAD)]) as urlopen:
        result = run(message.edit(content="edited"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/messages/1"
    assert json.loads(req.data) == {"content": "edited"}
    assert isinstance(result, Message)


def test_message_delete_delegates_to_rest_module():
    message = Message(_MESSAGE_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(message.delete())

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/messages/1"
    assert req.get_method() == "DELETE"


def test_message_crosspost_delegates_to_rest_module():
    message = Message(_MESSAGE_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MESSAGE_PAYLOAD)]) as urlopen:
        result = run(message.crosspost())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/messages/1/crosspost"
    assert isinstance(result, Message)


def test_message_reply_sets_message_reference():
    message = Message(_MESSAGE_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MESSAGE_PAYLOAD)]) as urlopen:
        result = run(message.reply(content="replying"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/channels/20/messages"
    assert json.loads(req.data) == {"content": "replying", "message_reference": {"message_id": "1"}}
    assert isinstance(result, Message)


def test_message_add_reaction_delegates_to_rest_module():
    message = Message(_MESSAGE_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(message.add_reaction("🎉"))

    req = urlopen.call_args.args[0]
    assert req.full_url.endswith("/@me")
    assert req.get_method() == "PUT"


def test_message_remove_reaction_defaults_to_own_reaction():
    message = Message(_MESSAGE_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(message.remove_reaction("🎉"))

    assert urlopen.call_args.args[0].full_url.endswith("/@me")


def test_message_remove_reaction_with_user_id_removes_that_user():
    message = Message(_MESSAGE_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(message.remove_reaction("🎉", user_id="55"))

    assert urlopen.call_args.args[0].full_url.endswith("/55")


def test_message_fetch_reactions_delegates_to_rest_module():
    message = Message(_MESSAGE_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_USER_PAYLOAD])]):
        assert run(message.fetch_reactions("🎉")) == [User(_USER_PAYLOAD)]


def test_message_clear_reactions_without_emoji_clears_all():
    message = Message(_MESSAGE_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(message.clear_reactions())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/messages/1/reactions"


def test_message_clear_reactions_with_emoji_clears_just_that_one():
    message = Message(_MESSAGE_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(message.clear_reactions("🎉"))

    assert "%F0%9F%8E%89" in urlopen.call_args.args[0].full_url


def test_message_fetch_poll_answer_voters_delegates_to_rest_module():
    message = Message(_MESSAGE_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse({"users": [_USER_PAYLOAD]})]) as urlopen:
        result = run(message.fetch_poll_answer_voters("3"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/polls/1/answers/3"
    assert result == [User(_USER_PAYLOAD)]


def test_message_expire_poll_delegates_to_rest_module():
    message = Message(_MESSAGE_PAYLOAD)
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MESSAGE_PAYLOAD)]) as urlopen:
        result = run(message.expire_poll())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/channels/20/polls/1/expire"
    assert isinstance(result, Message)
