from asyncio import run

import pytest

from cordless.app import Cordless
from cordless.errors import NoResponseError, UnknownButtonError, UnknownCommandError, UnknownComponentError
from cordless.testing import invoke, make_command_interaction, make_component_interaction

# ---------------------------------------------------------------------------
# make_command_interaction
# ---------------------------------------------------------------------------


def test_make_command_interaction_bare_name():
    interaction = make_command_interaction("ping")
    assert interaction["type"] == 2
    assert interaction["data"] == {"name": "ping", "type": 1}


def test_make_command_interaction_infers_option_types():
    interaction = make_command_interaction("buy", {"item": "sword", "qty": 3, "discount": 1.5, "gift": True})
    options = {o["name"]: o for o in interaction["data"]["options"]}
    assert options["item"] == {"name": "item", "type": 3, "value": "sword"}
    assert options["qty"] == {"name": "qty", "type": 4, "value": 3}
    assert options["discount"] == {"name": "discount", "type": 10, "value": 1.5}
    assert options["gift"] == {"name": "gift", "type": 5, "value": True}


def test_make_command_interaction_nests_subcommand_path():
    interaction = make_command_interaction("shop/buy", {"item": "sword"})
    assert interaction["data"]["name"] == "shop"
    sub = interaction["data"]["options"][0]
    assert sub == {"name": "buy", "type": 1, "options": [{"name": "item", "type": 3, "value": "sword"}]}


def test_make_command_interaction_nests_subcommand_group_path():
    interaction = make_command_interaction("shop/admin/restock", {"item": "sword"})
    assert interaction["data"]["name"] == "shop"
    group = interaction["data"]["options"][0]
    assert group["name"] == "admin"
    assert group["type"] == 2
    sub = group["options"][0]
    assert sub == {"name": "restock", "type": 1, "options": [{"name": "item", "type": 3, "value": "sword"}]}


def test_make_command_interaction_rejects_too_deep_a_path():
    with pytest.raises(ValueError):
        make_command_interaction("a/b/c/d")


def test_make_command_interaction_context_menu_defaults_to_user_type():
    interaction = make_command_interaction(
        "inspect", target_id="42", resolved={"users": {"42": {"id": "42", "username": "shiv"}}}
    )
    assert interaction["data"]["type"] == 2
    assert interaction["data"]["target_id"] == "42"
    assert interaction["data"]["resolved"] == {"users": {"42": {"id": "42", "username": "shiv"}}}


def test_make_command_interaction_context_menu_message_type():
    interaction = make_command_interaction("quote", target_id="99", target_type=3)
    assert interaction["data"]["type"] == 3
    assert interaction["data"]["target_id"] == "99"


def test_make_command_interaction_guild_context_populates_member_not_user():
    interaction = make_command_interaction("ping", guild_id="500")
    assert interaction["guild_id"] == "500"
    assert interaction["user"] is None
    assert interaction["member"]["user"]["id"] == "1"


def test_make_command_interaction_dm_context_populates_user_not_member():
    interaction = make_command_interaction("ping")
    assert interaction["guild_id"] is None
    assert interaction["member"] is None
    assert interaction["user"]["id"] == "1"


def test_make_command_interaction_custom_user_fields():
    interaction = make_command_interaction("ping", user_id="7", username="borhara")
    assert interaction["user"] == {"id": "7", "username": "borhara"}


def test_make_command_interaction_guild_defaults_to_minimal_object():
    interaction = make_command_interaction("ping", guild_id="30")
    assert interaction["guild"] == {"id": "30"}


def test_make_command_interaction_guild_accepts_explicit_object():
    interaction = make_command_interaction(
        "ping", guild_id="30", guild={"id": "30", "locale": "en-US", "features": ["COMMUNITY"]}
    )
    assert interaction["guild"] == {"id": "30", "locale": "en-US", "features": ["COMMUNITY"]}


# ---------------------------------------------------------------------------
# invoke
# ---------------------------------------------------------------------------


def _bot(public_key="ab" * 32):
    return Cordless(public_key=public_key)


def test_invoke_by_name_dispatches_through_real_router():
    bot = _bot()

    @bot.command("ping", description="ping")
    async def ping(ctx):
        await ctx.send("pong")

    response = run(invoke(bot, "ping"))
    assert response == {"type": 4, "data": {"content": "pong"}}


def test_invoke_forwards_options_to_the_handler():
    bot = _bot()

    @bot.command("buy", description="buy")
    async def buy(ctx, item: str, qty: int = 1):
        await ctx.send(f"bought {qty}x {item}")

    response = run(invoke(bot, "buy", options={"item": "sword", "qty": 3}))
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

        assert run(invoke(bot, "ping")) == {"type": 4, "data": {"content": "pong"}}


def test_invoke_resolves_subcommand_paths():
    bot = _bot()

    @bot.command("shop/list", description="list")
    async def shop_list(ctx):
        await ctx.send("nothing in stock")

    response = run(invoke(bot, "shop/list"))
    assert response["data"]["content"] == "nothing in stock"


def test_invoke_accepts_a_custom_interaction_for_context_menu_commands():
    bot = _bot()

    @bot.user_command("inspect")
    async def inspect(ctx):
        await ctx.send(f"inspecting {ctx.target_user.username}")

    interaction = make_command_interaction(
        "inspect",
        target_id="42",
        target_type=2,
        resolved={"users": {"42": {"id": "42", "username": "target-user"}}},
    )
    response = run(invoke(bot, interaction))
    assert response["data"]["content"] == "inspecting target-user"


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
# make_component_interaction
# ---------------------------------------------------------------------------


def test_make_component_interaction_defaults_to_a_button():
    interaction = make_component_interaction("confirm")
    assert interaction["type"] == 3
    assert interaction["data"] == {"custom_id": "confirm", "component_type": 2}


def test_make_component_interaction_carries_select_values():
    interaction = make_component_interaction("pick", values=["a", "b"], component_type=3)
    assert interaction["data"] == {"custom_id": "pick", "component_type": 3, "values": ["a", "b"]}


def test_make_component_interaction_attaches_message():
    interaction = make_component_interaction("confirm", message={"id": "99", "content": "are you sure?"})
    assert interaction["message"] == {"id": "99", "content": "are you sure?"}


def test_make_component_interaction_omits_message_by_default():
    interaction = make_component_interaction("confirm")
    assert "message" not in interaction


# ---------------------------------------------------------------------------
# invoke - components
# ---------------------------------------------------------------------------


def test_invoke_dispatches_a_button():
    bot = _bot()

    @bot.button("confirm")
    async def confirm(ctx):
        await ctx.send("confirmed")

    response = run(invoke(bot, make_component_interaction("confirm")))
    assert response["data"]["content"] == "confirmed"


def test_invoke_dispatches_a_prefix_matched_button():
    bot = _bot()

    @bot.button("shop")
    async def shop(ctx):
        await ctx.send(f"picked {ctx.custom_id_args[0]}")

    response = run(invoke(bot, make_component_interaction("shop:item1")))
    assert response["data"]["content"] == "picked item1"


def test_invoke_dispatches_a_select_with_values():
    bot = _bot()

    @bot.select("pick")
    async def pick(ctx):
        await ctx.send(f"picked {', '.join(ctx.values)}")

    response = run(invoke(bot, make_component_interaction("pick", values=["a", "b"], component_type=3)))
    assert response["data"]["content"] == "picked a, b"


def test_invoke_raises_for_unknown_button():
    bot = _bot()

    with pytest.raises(UnknownButtonError):
        run(invoke(bot, make_component_interaction("nope")))


def test_invoke_raises_for_unknown_select():
    bot = _bot()

    with pytest.raises(UnknownComponentError):
        run(invoke(bot, make_component_interaction("nope", component_type=3)))
