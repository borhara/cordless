"""_rest/members.py: guild member and role REST endpoints, plus their
bot.<verb>() and Guild/Member/Role object-method delegation."""

import json
import os
from asyncio import run
from unittest.mock import patch

from conftest import FakeDiscordResponse

from cordless._rest import members
from cordless.app import Cordless
from cordless.models import Guild, Member, Role

_ENV = {"DISCORD_BOT_TOKEN": "tok"}

_MEMBER_PAYLOAD = {"nick": "shiv", "roles": ["1"], "user": {"id": "55", "username": "shiv"}}
_ROLE_PAYLOAD = {"id": "1", "name": "moderator", "color": 0, "permissions": "0"}


def _urlopen(responses):
    return patch("cordless._rest._client.urllib.request.urlopen", side_effect=responses)


# --- fetch_guild_member / fetch_guild_members / search_guild_members ---


def test_fetch_guild_member_returns_member_with_guild_id_injected():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MEMBER_PAYLOAD)]) as urlopen:
        result = run(members.fetch_guild_member("10", "55"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/members/55"
    assert isinstance(result, Member)
    assert result.display_name == "shiv"
    assert result._data["guild_id"] == "10"


def test_fetch_guild_members_returns_member_list():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_MEMBER_PAYLOAD])]) as urlopen:
        result = run(members.fetch_guild_members("10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/members"
    assert len(result) == 1
    assert result[0].user.username == "shiv"


def test_fetch_guild_members_passes_limit_and_after():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([])]) as urlopen:
        run(members.fetch_guild_members("10", limit=50, after="90"))

    url = urlopen.call_args.args[0].full_url
    assert "limit=50" in url
    assert "after=90" in url


def test_search_guild_members_passes_query_and_limit():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_MEMBER_PAYLOAD])]) as urlopen:
        result = run(members.search_guild_members("10", "shi", limit=5))

    url = urlopen.call_args.args[0].full_url
    assert "query=shi" in url
    assert "limit=5" in url
    assert len(result) == 1


def test_search_guild_members_url_encodes_query():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([])]) as urlopen:
        run(members.search_guild_members("10", "shiv the second"))

    url = urlopen.call_args.args[0].full_url
    assert "query=shiv%20the%20second" in url


# --- add / edit / kick ---


def test_add_guild_member_puts_access_token_and_returns_member():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MEMBER_PAYLOAD)]) as urlopen:
        result = run(members.add_guild_member("10", "55", "oauth-token", roles=["1"]))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/members/55"
    assert json.loads(req.data) == {"access_token": "oauth-token", "roles": ["1"]}
    assert isinstance(result, Member)


def test_add_guild_member_returns_none_on_204_already_a_member():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]):
        result = run(members.add_guild_member("10", "55", "oauth-token"))

    assert result is None


def test_edit_guild_member_only_sends_fields_that_were_set():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MEMBER_PAYLOAD)]) as urlopen:
        run(members.edit_guild_member("10", "55", nick="new nick"))

    assert json.loads(urlopen.call_args.args[0].data) == {"nick": "new nick"}


def test_edit_guild_member_sends_explicit_none_to_clear_nick():
    """Regression: nick=None used to be silently dropped by the old
    None-means-unset payload builder, making it impossible to clear a nick."""
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MEMBER_PAYLOAD)]) as urlopen:
        run(members.edit_guild_member("10", "55", nick=None))

    assert json.loads(urlopen.call_args.args[0].data) == {"nick": None}


def test_edit_guild_member_sends_explicit_none_to_clear_timeout():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MEMBER_PAYLOAD)]) as urlopen:
        run(members.edit_guild_member("10", "55", communication_disabled_until=None))

    assert json.loads(urlopen.call_args.args[0].data) == {"communication_disabled_until": None}


def test_edit_current_member_patches_at_me():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MEMBER_PAYLOAD)]) as urlopen:
        run(members.edit_current_member("10", nick="shiv"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/members/@me"
    assert json.loads(req.data) == {"nick": "shiv"}


def test_add_guild_member_role_puts_role():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(members.add_guild_member_role("10", "55", "1"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/members/55/roles/1"
    assert req.get_method() == "PUT"


def test_remove_guild_member_role_deletes_role():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(members.remove_guild_member_role("10", "55", "1"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/members/55/roles/1"
    assert req.get_method() == "DELETE"


def test_remove_guild_member_kicks():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(members.remove_guild_member("10", "55"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/members/55"
    assert req.get_method() == "DELETE"


def test_remove_guild_member_sends_audit_log_reason():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(members.remove_guild_member("10", "55", reason="spamming"))

    req = urlopen.call_args.args[0]
    assert req.get_header("X-audit-log-reason") == "spamming"


def test_remove_guild_member_omits_audit_log_reason_when_not_given():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(members.remove_guild_member("10", "55"))

    req = urlopen.call_args.args[0]
    assert req.get_header("X-audit-log-reason") is None


# --- roles ---


def test_fetch_guild_roles_returns_role_list():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_ROLE_PAYLOAD])]) as urlopen:
        result = run(members.fetch_guild_roles("10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/roles"
    assert len(result) == 1
    assert result[0].mention == "<@&1>"
    assert result[0]._data["guild_id"] == "10"


def test_fetch_guild_role_returns_single_role():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_ROLE_PAYLOAD)]) as urlopen:
        result = run(members.fetch_guild_role("10", "1"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/roles/1"
    assert isinstance(result, Role)


def test_fetch_guild_role_member_counts_returns_raw_mapping():
    payload = {"1": 12, "2": 3}
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(payload)]) as urlopen:
        result = run(members.fetch_guild_role_member_counts("10"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/roles/member-counts"
    assert result == payload


def test_create_guild_role_only_sends_fields_that_were_set():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_ROLE_PAYLOAD)]) as urlopen:
        result = run(members.create_guild_role("10", name="mods", hoist=True))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/roles"
    assert json.loads(req.data) == {"name": "mods", "hoist": True}
    assert isinstance(result, Role)


def test_edit_guild_role_positions_sends_raw_list_and_returns_role_list():
    positions = [{"id": "1", "position": 2}]
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_ROLE_PAYLOAD])]) as urlopen:
        result = run(members.edit_guild_role_positions("10", positions))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/roles"
    assert json.loads(req.data) == positions
    assert len(result) == 1


def test_edit_guild_role_only_sends_fields_that_were_set():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_ROLE_PAYLOAD)]) as urlopen:
        result = run(members.edit_guild_role("10", "1", mentionable=True))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/roles/1"
    assert json.loads(req.data) == {"mentionable": True}
    assert isinstance(result, Role)


def test_delete_guild_role_deletes_role():
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(members.delete_guild_role("10", "1"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/roles/1"
    assert req.get_method() == "DELETE"


# --- bot.<verb>() delegation (every mixin method) ---


def test_bot_fetch_guild_member_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MEMBER_PAYLOAD)]):
        assert isinstance(run(bot.fetch_guild_member("10", "55")), Member)


def test_bot_fetch_guild_members_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_MEMBER_PAYLOAD])]):
        assert len(run(bot.fetch_guild_members("10"))) == 1


def test_bot_search_guild_members_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_MEMBER_PAYLOAD])]):
        assert len(run(bot.search_guild_members("10", "shi"))) == 1


def test_bot_add_guild_member_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MEMBER_PAYLOAD)]):
        assert isinstance(run(bot.add_guild_member("10", "55", "oauth-token")), Member)


def test_bot_edit_guild_member_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MEMBER_PAYLOAD)]):
        assert isinstance(run(bot.edit_guild_member("10", "55", nick="shiv")), Member)


def test_bot_edit_current_member_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MEMBER_PAYLOAD)]):
        assert isinstance(run(bot.edit_current_member("10", nick="shiv")), Member)


def test_bot_add_guild_member_role_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(bot.add_guild_member_role("10", "55", "1"))
    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/members/55/roles/1"


def test_bot_remove_guild_member_role_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(bot.remove_guild_member_role("10", "55", "1"))
    assert urlopen.call_args.args[0].get_method() == "DELETE"


def test_bot_remove_guild_member_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(bot.remove_guild_member("10", "55"))
    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/members/55"


def test_bot_add_role_still_works_under_its_older_name():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(bot.add_role("10", "55", "1"))
    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/members/55/roles/1"


def test_bot_remove_role_still_works_under_its_older_name():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(bot.remove_role("10", "55", "1"))
    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/members/55/roles/1"
    assert req.get_method() == "DELETE"


def test_bot_fetch_guild_roles_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_ROLE_PAYLOAD])]):
        assert len(run(bot.fetch_guild_roles("10"))) == 1


def test_bot_fetch_guild_role_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_ROLE_PAYLOAD)]):
        assert isinstance(run(bot.fetch_guild_role("10", "1")), Role)


def test_bot_fetch_guild_role_member_counts_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse({"1": 5})]):
        assert run(bot.fetch_guild_role_member_counts("10")) == {"1": 5}


def test_bot_create_guild_role_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_ROLE_PAYLOAD)]):
        assert isinstance(run(bot.create_guild_role("10", name="mods")), Role)


def test_bot_edit_guild_role_positions_delegates_to_rest_module():
    bot = Cordless()
    positions = [{"id": "1", "position": 1}]
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_ROLE_PAYLOAD])]) as urlopen:
        run(bot.edit_guild_role_positions("10", positions))
    assert json.loads(urlopen.call_args.args[0].data) == positions


def test_bot_edit_guild_role_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_ROLE_PAYLOAD)]):
        assert isinstance(run(bot.edit_guild_role("10", "1", mentionable=True)), Role)


def test_bot_delete_guild_role_delegates_to_rest_module():
    bot = Cordless()
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(bot.delete_guild_role("10", "1"))
    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/roles/1"


# --- guild.*() object-method delegation ---


def test_guild_fetch_member_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MEMBER_PAYLOAD)]) as urlopen:
        result = run(guild.fetch_member("55"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/members/55"
    assert isinstance(result, Member)


def test_guild_fetch_members_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_MEMBER_PAYLOAD])]):
        assert len(run(guild.fetch_members())) == 1


def test_guild_search_members_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_MEMBER_PAYLOAD])]) as urlopen:
        run(guild.search_members("shi"))

    assert "query=shi" in urlopen.call_args.args[0].full_url


def test_guild_add_member_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MEMBER_PAYLOAD)]):
        assert isinstance(run(guild.add_member("55", "oauth-token")), Member)


def test_guild_edit_member_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MEMBER_PAYLOAD)]) as urlopen:
        result = run(guild.edit_member("55", nick="shiv"))

    assert json.loads(urlopen.call_args.args[0].data) == {"nick": "shiv"}
    assert isinstance(result, Member)


def test_guild_edit_current_member_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MEMBER_PAYLOAD)]):
        assert isinstance(run(guild.edit_current_member(nick="shiv")), Member)


def test_guild_add_member_role_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(guild.add_member_role("55", "1"))
    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/members/55/roles/1"


def test_guild_remove_member_role_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(guild.remove_member_role("55", "1"))
    assert urlopen.call_args.args[0].get_method() == "DELETE"


def test_guild_kick_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(guild.kick("55"))
    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/members/55"


def test_guild_fetch_roles_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_ROLE_PAYLOAD])]):
        assert len(run(guild.fetch_roles())) == 1


def test_guild_fetch_role_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_ROLE_PAYLOAD)]):
        assert isinstance(run(guild.fetch_role("1")), Role)


def test_guild_fetch_role_member_counts_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse({"1": 9})]):
        assert run(guild.fetch_role_member_counts()) == {"1": 9}


def test_guild_create_role_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_ROLE_PAYLOAD)]):
        assert isinstance(run(guild.create_role(name="mods")), Role)


def test_guild_edit_role_positions_delegates_to_rest_module():
    guild = Guild({"id": "10"})
    positions = [{"id": "1", "position": 3}]
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse([_ROLE_PAYLOAD])]) as urlopen:
        run(guild.edit_role_positions(positions))
    assert json.loads(urlopen.call_args.args[0].data) == positions


# --- member.*()/role.*() object-method delegation ---


def test_member_edit_delegates_to_rest_module():
    member = Member(dict(_MEMBER_PAYLOAD, guild_id="10"))
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MEMBER_PAYLOAD)]) as urlopen:
        result = run(member.edit(nick="new nick"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/members/55"
    assert json.loads(req.data) == {"nick": "new nick"}
    assert isinstance(result, Member)


def test_member_add_role_delegates_to_rest_module():
    member = Member(dict(_MEMBER_PAYLOAD, guild_id="10"))
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(member.add_role("2"))

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/members/55/roles/2"


def test_member_remove_role_delegates_to_rest_module():
    member = Member(dict(_MEMBER_PAYLOAD, guild_id="10"))
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(member.remove_role("2"))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/members/55/roles/2"
    assert req.get_method() == "DELETE"


def test_member_kick_delegates_to_rest_module():
    member = Member(dict(_MEMBER_PAYLOAD, guild_id="10"))
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(member.kick())

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/members/55"
    assert req.get_method() == "DELETE"


def test_member_timeout_sends_communication_disabled_until():
    member = Member(dict(_MEMBER_PAYLOAD, guild_id="10"))
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MEMBER_PAYLOAD)]) as urlopen:
        run(member.timeout("2024-01-01T00:00:00Z"))

    assert json.loads(urlopen.call_args.args[0].data) == {"communication_disabled_until": "2024-01-01T00:00:00Z"}


def test_member_timeout_none_clears_it():
    member = Member(dict(_MEMBER_PAYLOAD, guild_id="10"))
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_MEMBER_PAYLOAD)]) as urlopen:
        run(member.timeout(None))

    assert json.loads(urlopen.call_args.args[0].data) == {"communication_disabled_until": None}


def test_role_edit_delegates_to_rest_module():
    role = Role(dict(_ROLE_PAYLOAD, guild_id="10"))
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(_ROLE_PAYLOAD)]) as urlopen:
        result = run(role.edit(mentionable=True))

    req = urlopen.call_args.args[0]
    assert req.full_url == "https://discord.com/api/v10/guilds/10/roles/1"
    assert json.loads(req.data) == {"mentionable": True}
    assert isinstance(result, Role)


def test_role_delete_delegates_to_rest_module():
    role = Role(dict(_ROLE_PAYLOAD, guild_id="10"))
    with patch.dict(os.environ, _ENV), _urlopen([FakeDiscordResponse(None)]) as urlopen:
        run(role.delete())

    assert urlopen.call_args.args[0].full_url == "https://discord.com/api/v10/guilds/10/roles/1"


# --- ctx.member / ctx.resolved_roles carry guild_id for the sugar above ---


def test_ctx_member_gets_guild_id_injected_for_action_methods():
    from cordless.context import Context

    interaction = {
        "guild_id": "10",
        "member": {"nick": "shiv", "user": {"id": "55", "username": "shiv"}},
    }
    ctx = Context(interaction)

    assert ctx.member._data["guild_id"] == "10"


def test_ctx_resolved_roles_get_guild_id_injected():
    from cordless.context import Context

    interaction = {
        "guild_id": "10",
        "data": {"resolved": {"roles": {"1": _ROLE_PAYLOAD}}},
    }
    ctx = Context(interaction)

    assert ctx.resolved_roles["1"]._data["guild_id"] == "10"
