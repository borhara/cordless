from asyncio import run

import pytest

import cordless.defer
from cordless import Permissions
from cordless.app import Cordless
from cordless.errors import (
    CordlessError,
    NoResponseError,
    UnknownButtonError,
    UnknownCommandError,
    UnknownComponentError,
    UnsupportedInteractionError,
)
from cordless.testing import autocomplete, button, command, invoke, member, modal, select

# ---------------------------------------------------------------------------
# command
# ---------------------------------------------------------------------------


def test_command_bare_name():
    interaction = command("ping")
    assert interaction["type"] == 2
    assert interaction["data"] == {"name": "ping", "type": 1}


def test_command_infers_option_types():
    interaction = command("buy", {"item": "sword", "qty": 3, "discount": 1.5, "gift": True})
    options = {o["name"]: o for o in interaction["data"]["options"]}
    assert options["item"] == {"name": "item", "type": 3, "value": "sword"}
    assert options["qty"] == {"name": "qty", "type": 4, "value": 3}
    assert options["discount"] == {"name": "discount", "type": 10, "value": 1.5}
    assert options["gift"] == {"name": "gift", "type": 5, "value": True}


def test_command_nests_subcommand_path():
    interaction = command("shop/buy", {"item": "sword"})
    assert interaction["data"]["name"] == "shop"
    sub = interaction["data"]["options"][0]
    assert sub == {"name": "buy", "type": 1, "options": [{"name": "item", "type": 3, "value": "sword"}]}


def test_command_nests_subcommand_group_path():
    interaction = command("shop/admin/restock", {"item": "sword"})
    assert interaction["data"]["name"] == "shop"
    group = interaction["data"]["options"][0]
    assert group["name"] == "admin"
    assert group["type"] == 2
    sub = group["options"][0]
    assert sub == {"name": "restock", "type": 1, "options": [{"name": "item", "type": 3, "value": "sword"}]}


def test_command_rejects_too_deep_a_path():
    with pytest.raises(ValueError):
        command("a/b/c/d")


def test_command_target_stitches_resolved_users():
    target = {"id": "42", "username": "target-user"}
    interaction = command("inspect", target=target)
    assert interaction["data"]["type"] == 2
    assert interaction["data"]["target_id"] == "42"
    assert interaction["data"]["resolved"] == {"users": {"42": target}}


def test_command_target_stitches_resolved_messages():
    target = {"id": "99", "content": "hello"}
    interaction = command("quote", target=target, target_type=3)
    assert interaction["data"]["type"] == 3
    assert interaction["data"]["resolved"] == {"messages": {"99": target}}


def test_command_guild_context_populates_member_not_user():
    interaction = command("ping", guild_id="500")
    assert interaction["guild_id"] == "500"
    assert interaction["user"] is None
    assert interaction["member"]["user"]["id"] == "1"


def test_command_dm_context_populates_user_not_member():
    interaction = command("ping")
    assert interaction["guild_id"] is None
    assert interaction["member"] is None
    assert interaction["user"]["id"] == "1"


def test_command_custom_user_fields():
    interaction = command("ping", user_id="7", username="borhara")
    assert interaction["user"] == {"id": "7", "username": "borhara"}


def test_command_guild_defaults_to_minimal_object():
    interaction = command("ping", guild_id="30")
    assert interaction["guild"] == {"id": "30"}


def test_command_guild_accepts_explicit_object():
    interaction = command("ping", guild_id="30", guild={"id": "30", "locale": "en-US", "features": ["COMMUNITY"]})
    assert interaction["guild"] == {"id": "30", "locale": "en-US", "features": ["COMMUNITY"]}


def test_command_member_implies_a_guild_context():
    interaction = command("ping", member=member(roles=["999"]))
    assert interaction["guild_id"] == "1"
    assert interaction["member"]["roles"] == ["999"]


# ---------------------------------------------------------------------------
# member
# ---------------------------------------------------------------------------


def test_member_defaults():
    data = member()
    assert data == {"user": {"id": "1", "username": "test-user"}, "roles": []}


def test_member_carries_roles():
    data = member(roles=["100", "200"])
    assert data["roles"] == ["100", "200"]


def test_member_accepts_a_permissions_instance():
    data = member(permissions=Permissions(manage_guild=True))
    assert data["permissions"] == str(int(Permissions(manage_guild=True)))


def test_member_accepts_a_raw_permissions_int():
    data = member(permissions=8)
    assert data["permissions"] == "8"


def test_member_carries_nick():
    data = member(nick="shivvy")
    assert data["nick"] == "shivvy"


# ---------------------------------------------------------------------------
# invoke - commands
# ---------------------------------------------------------------------------


def _bot(public_key="ab" * 32):
    return Cordless(public_key=public_key)


def test_invoke_by_name_dispatches_through_real_router():
    bot = _bot()

    @bot.command("ping", description="ping")
    async def ping(ctx):
        await ctx.send("pong")

    response, ctx = run(invoke(bot, "ping"))
    assert response == {"type": 4, "data": {"content": "pong"}}
    assert ctx.user.id == "1"


def test_invoke_forwards_options_to_the_handler():
    bot = _bot()

    @bot.command("buy", description="buy")
    async def buy(ctx, item: str, qty: int = 1):
        await ctx.send(f"bought {qty}x {item}")

    response, _ = run(invoke(bot, "buy", options={"item": "sword", "qty": 3}))
    assert response["data"]["content"] == "bought 3x sword"


def test_invoke_works_regardless_of_public_key():
    """No HTTP request is ever made, so signature verification never runs -
    this should behave identically with or without a real DISCORD_PUBLIC_KEY."""
    with_key = _bot(public_key="ab" * 32)
    without_key = _bot(public_key=None)

    for bot in (with_key, without_key):

        @bot.command("ping", description="ping")
        async def ping(ctx):
            await ctx.send("pong")

        response, _ = run(invoke(bot, "ping"))
        assert response == {"type": 4, "data": {"content": "pong"}}


def test_invoke_resolves_subcommand_paths():
    bot = _bot()

    @bot.command("shop/list", description="list")
    async def shop_list(ctx):
        await ctx.send("nothing in stock")

    response, _ = run(invoke(bot, "shop/list"))
    assert response["data"]["content"] == "nothing in stock"


def test_invoke_accepts_a_custom_interaction_for_context_menu_commands():
    bot = _bot()

    @bot.user_command("inspect")
    async def inspect(ctx):
        await ctx.send(f"inspecting {ctx.target_user.username}")

    interaction = command("inspect", target={"id": "42", "username": "target-user"})
    response, _ = run(invoke(bot, interaction))
    assert response["data"]["content"] == "inspecting target-user"


def test_invoke_exposes_member_on_ctx():
    bot = _bot()

    @bot.command("check", description="check permissions")
    async def check(ctx):
        await ctx.send(str(ctx.member.permissions.manage_guild))

    interaction = command("check", member=member(permissions=Permissions(manage_guild=True)))
    response, ctx = run(invoke(bot, interaction))
    assert response["data"]["content"] == "True"
    assert ctx.member.permissions.manage_guild is True


def test_invoke_raises_for_unknown_command():
    bot = _bot()

    with pytest.raises(UnknownCommandError):
        run(invoke(bot, "nope"))


def test_invoke_raises_when_handler_never_responds():
    bot = _bot()

    @bot.command("broken", description="never responds")
    async def broken(ctx):
        pass

    with pytest.raises(NoResponseError):
        run(invoke(bot, "broken"))


# ---------------------------------------------------------------------------
# button / select
# ---------------------------------------------------------------------------


def test_button_defaults():
    interaction = button("confirm")
    assert interaction["type"] == 3
    assert interaction["data"] == {"custom_id": "confirm", "component_type": 2}


def test_button_attaches_message():
    interaction = button("confirm", message={"id": "99", "content": "are you sure?"})
    assert interaction["message"] == {"id": "99", "content": "are you sure?"}


def test_button_omits_message_by_default():
    interaction = button("confirm")
    assert "message" not in interaction


def test_select_defaults_to_string_kind():
    interaction = select("pick", values=["a", "b"])
    assert interaction["data"] == {"custom_id": "pick", "component_type": 3, "values": ["a", "b"]}


def test_select_rejects_unknown_kind():
    with pytest.raises(ValueError):
        select("pick", kind="nope")


def test_select_stitches_resolved_roles_from_role_objects():
    role = {"id": "999", "name": "Admin"}
    interaction = select("pickrole", values=[role], kind="role")
    assert interaction["data"]["values"] == ["999"]
    assert interaction["data"]["resolved"] == {"roles": {"999": role}}


def test_select_leaves_plain_ids_unresolved():
    interaction = select("pickrole", values=["999"], kind="role")
    assert interaction["data"]["values"] == ["999"]
    assert "resolved" not in interaction["data"]


def test_invoke_dispatches_a_button():
    bot = _bot()

    @bot.button("confirm")
    async def confirm(ctx):
        await ctx.send("confirmed")

    response, _ = run(invoke(bot, button("confirm")))
    assert response["data"]["content"] == "confirmed"


def test_invoke_dispatches_a_prefix_matched_button():
    bot = _bot()

    @bot.button("shop")
    async def shop(ctx):
        await ctx.send(f"picked {ctx.custom_id_args[0]}")

    response, ctx = run(invoke(bot, button("shop:item1")))
    assert response["data"]["content"] == "picked item1"
    assert ctx.custom_id_args == ["item1"]


def test_invoke_dispatches_a_select_with_values():
    bot = _bot()

    @bot.select("pick")
    async def pick(ctx):
        await ctx.send(f"picked {', '.join(ctx.values)}")

    response, _ = run(invoke(bot, select("pick", values=["a", "b"])))
    assert response["data"]["content"] == "picked a, b"


def test_invoke_dispatches_a_role_select_with_resolved_roles():
    bot = _bot()

    @bot.select("pickrole")
    async def pickrole(ctx):
        names = ", ".join(r.name for r in ctx.resolved_roles.values())
        await ctx.send(f"picked {names}")

    role = {"id": "999", "name": "Admin"}
    response, _ = run(invoke(bot, select("pickrole", values=[role], kind="role")))
    assert response["data"]["content"] == "picked Admin"


def test_invoke_raises_for_unknown_button():
    bot = _bot()

    with pytest.raises(UnknownButtonError):
        run(invoke(bot, button("nope")))


def test_invoke_raises_for_unknown_select():
    bot = _bot()

    with pytest.raises(UnknownComponentError):
        run(invoke(bot, select("nope")))


# ---------------------------------------------------------------------------
# modal
# ---------------------------------------------------------------------------


def test_modal_flattens_values_into_rows():
    interaction = modal("form", values={"name_field": "shiv", "age_field": "30"})
    assert interaction["data"]["custom_id"] == "form"
    rows = interaction["data"]["components"]
    assert {"type": 1, "components": [{"type": 4, "custom_id": "name_field", "value": "shiv"}]} in rows
    assert {"type": 1, "components": [{"type": 4, "custom_id": "age_field", "value": "30"}]} in rows


def test_modal_with_no_values():
    interaction = modal("form")
    assert interaction["data"]["components"] == []


def test_invoke_dispatches_a_modal_submission():
    bot = _bot()

    @bot.modal("form")
    async def form(ctx):
        await ctx.send(f"hello {ctx.modal_values['name_field']}")

    response, ctx = run(invoke(bot, modal("form", values={"name_field": "shiv"})))
    assert response["data"]["content"] == "hello shiv"
    assert ctx.modal_values == {"name_field": "shiv"}


# ---------------------------------------------------------------------------
# autocomplete
# ---------------------------------------------------------------------------


def test_autocomplete_bare_name():
    interaction = autocomplete("shop")
    assert interaction["type"] == 4
    assert interaction["data"] == {"name": "shop", "type": 1}


def test_autocomplete_marks_the_focused_option():
    interaction = autocomplete("shop", {"item": "sw", "qty": 3}, focused="item")
    options = {o["name"]: o for o in interaction["data"]["options"]}
    assert options["item"]["focused"] is True
    assert "focused" not in options["qty"]


def test_autocomplete_nests_subcommand_path():
    interaction = autocomplete("shop/buy", {"item": "sw"}, focused="item")
    sub = interaction["data"]["options"][0]
    assert sub["name"] == "buy"
    assert sub["options"][0]["focused"] is True


def test_invoke_dispatches_autocomplete_and_filters_string_choices():
    bot = _bot()

    @bot.command("shop", description="shop", options=[{"name": "item", "type": 3, "autocomplete": True}])
    async def shop(ctx, item: str):
        await ctx.send("bought")

    @bot.autocomplete("shop", "item")
    async def shop_item(ctx):
        return ["sword", "shield", "bow"]

    interaction = autocomplete("shop", {"item": "sw"}, focused="item")
    response, ctx = run(invoke(bot, interaction))
    assert response["data"]["choices"] == [{"name": "sword", "value": "sword"}]
    assert ctx.focused_value == "sw"


def test_invoke_dispatches_autocomplete_with_dict_choices_unfiltered():
    bot = _bot()

    @bot.command("shop", description="shop", options=[{"name": "item", "type": 3, "autocomplete": True}])
    async def shop(ctx, item: str):
        await ctx.send("bought")

    @bot.autocomplete("shop", "item")
    async def shop_item(ctx):
        return [{"name": "Sword of Doom", "value": "sword"}]

    response, _ = run(invoke(bot, autocomplete("shop", {"item": "any"}, focused="item")))
    assert response["data"]["choices"] == [{"name": "Sword of Doom", "value": "sword"}]


def test_invoke_raises_for_unregistered_autocomplete_handler():
    bot = _bot()

    @bot.command("shop", description="shop", options=[{"name": "item", "type": 3, "autocomplete": True}])
    async def shop(ctx, item: str):
        await ctx.send("bought")

    with pytest.raises(UnsupportedInteractionError):
        run(invoke(bot, autocomplete("shop", {"item": "sw"}, focused="item")))


# ---------------------------------------------------------------------------
# invoke - worker mode (defer=True handlers)
# ---------------------------------------------------------------------------


def test_invoke_without_worker_mode_requires_a_configured_worker(monkeypatch):
    """A defer=True handler dispatched normally hits the real defer-to-worker
    path, which needs CORDLESS_WORKER_FUNCTION - it should fail loudly
    rather than silently invoke anything."""
    monkeypatch.delenv("CORDLESS_WORKER_FUNCTION", raising=False)
    bot = _bot()

    @bot.command("slow", description="slow", defer=True)
    async def slow(ctx):
        await ctx.send("done")

    with pytest.raises(CordlessError):
        run(invoke(bot, "slow"))


def test_invoke_worker_mode_runs_the_handler_directly(monkeypatch):
    bot = _bot()
    followups = []
    monkeypatch.setattr(cordless.defer, "patch_followup", lambda app_id, token, payload: followups.append(payload))

    @bot.command("slow", description="slow", defer=True)
    async def slow(ctx):
        await ctx.send("done")

    response, ctx = run(invoke(bot, "slow", worker_mode=True))
    assert response == {"_cordless_followup": True}
    assert followups == [{"content": "done"}]
    assert ctx._worker_mode is True


def test_invoke_worker_mode_handler_doing_nothing_returns_none(monkeypatch):
    bot = _bot()
    monkeypatch.setattr(cordless.defer, "patch_followup", lambda app_id, token, payload: None)

    @bot.command("slow", description="slow", defer=True)
    async def slow(ctx):
        pass

    response, _ = run(invoke(bot, "slow", worker_mode=True))
    assert response is None
