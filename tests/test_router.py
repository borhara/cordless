import json

from cordless.app import Cordless
from cordless.errors import PermissionDeniedError


def _handle(bot, payload):
    return bot.handle({"body": json.dumps(payload)})


def _body(result):
    return json.loads(result["body"])


# --- Slash commands ---

def test_slash_command_dispatch():
    bot = Cordless()

    @bot.command("ping")
    async def ping(ctx):
        return await ctx.send("pong")

    result = _handle(bot, {"type": 2, "data": {"name": "ping"}})
    assert result["statusCode"] == 200
    assert _body(result)["data"]["content"] == "pong"


def test_command_options_exposed_on_context():
    bot = Cordless()
    received = {}

    @bot.command("echo")
    async def echo(ctx):
        received.update(ctx.options)
        return await ctx.send(ctx.options["text"])

    result = _handle(bot, {
        "type": 2,
        "data": {"name": "echo", "options": [{"name": "text", "type": 3, "value": "hello"}]},
    })
    assert received == {"text": "hello"}
    assert _body(result)["data"]["content"] == "hello"


def test_handler_without_return_still_responds():
    bot = Cordless()

    @bot.command("ping")
    async def ping(ctx):
        await ctx.send("pong")  # no return, common gotcha

    result = _handle(bot, {"type": 2, "data": {"name": "ping"}})
    assert result["statusCode"] == 200
    assert _body(result)["data"]["content"] == "pong"


def test_handler_that_sends_nothing_returns_400():
    bot = Cordless()

    @bot.command("noop")
    async def noop(ctx): pass

    result = _handle(bot, {"type": 2, "data": {"name": "noop"}})
    assert result["statusCode"] == 400


def test_unknown_command_returns_400():
    bot = Cordless()
    result = _handle(bot, {"type": 2, "data": {"name": "missing"}})
    assert result["statusCode"] == 400
    assert "missing" in _body(result)["error"]


# --- Buttons ---

def test_button_dispatch():
    bot = Cordless()

    @bot.button("edit_ping")
    async def edit_ping(ctx):
        return await ctx.edit("edited")

    result = _handle(bot, {"type": 3, "data": {"custom_id": "edit_ping"}})
    assert result["statusCode"] == 200
    assert _body(result)["type"] == 7
    assert _body(result)["data"]["content"] == "edited"


def test_unknown_button_returns_400():
    bot = Cordless()
    result = _handle(bot, {"type": 3, "data": {"custom_id": "missing"}})
    assert result["statusCode"] == 400


# --- Select menus ---

def test_select_dispatch():
    bot = Cordless()

    @bot.select("color_select")
    async def on_select(ctx):
        await ctx.edit("You picked!")

    result = _handle(bot, {
        "type": 3, "id": "1", "token": "tok",
        "data": {"custom_id": "color_select", "component_type": 3, "values": ["red"]},
    })
    assert result["statusCode"] == 200


def test_unknown_select_returns_400():
    bot = Cordless()
    result = _handle(bot, {
        "type": 3, "id": "1", "token": "tok",
        "data": {"custom_id": "nope", "component_type": 3},
    })
    assert result["statusCode"] == 400


# --- Modals ---

def test_modal_dispatch():
    bot = Cordless()

    @bot.modal("feedback_modal")
    async def on_modal(ctx):
        await ctx.send("Thanks!")

    result = _handle(bot, {
        "type": 5, "id": "1", "token": "tok",
        "data": {
            "custom_id": "feedback_modal",
            "components": [{"type": 1, "components": [{"type": 4, "custom_id": "msg", "value": "Hi"}]}],
        },
    })
    assert result["statusCode"] == 200


def test_unknown_modal_returns_400():
    bot = Cordless()
    result = _handle(bot, {
        "type": 5, "id": "1", "token": "tok",
        "data": {"custom_id": "ghost_modal", "components": []},
    })
    assert result["statusCode"] == 400


# --- Autocomplete ---

def test_autocomplete_dispatch():
    bot = Cordless()

    @bot.command("search", description="Search")
    async def search(ctx):
        await ctx.send("results")

    @bot.autocomplete("search", "query")
    async def search_autocomplete(ctx):
        await ctx.respond_autocomplete([{"name": "foo", "value": "foo"}])

    result = _handle(bot, {
        "type": 4, "id": "1", "token": "tok",
        "data": {"name": "search", "options": [{"name": "query", "value": "fo", "focused": True}]},
    })
    assert _body(result)["type"] == 8


def test_subcommand_autocomplete_focused_value():
    from cordless.context import Context

    event = {
        "type": 4,
        "data": {
            "name": "shop",
            "options": [{"type": 1, "name": "buy", "options": [
                {"name": "item", "value": "sw", "focused": True},
            ]}],
        },
    }
    ctx = Context(event)
    assert ctx.focused_value == "sw"


def test_subcommand_autocomplete_options():
    from cordless.context import Context

    event = {
        "type": 4,
        "data": {
            "name": "shop",
            "options": [{"type": 1, "name": "buy", "options": [
                {"name": "qty", "value": 3},
                {"name": "item", "value": "sw", "focused": True},
            ]}],
        },
    }
    ctx = Context(event)
    assert ctx.options == {"qty": 3, "item": "sw"}


# --- Subcommands ---

def test_subcommand_dispatch():
    bot = Cordless()
    called = {}

    @bot.command("mod/ban", description="Ban a user")
    async def mod_ban(ctx):
        called["cmd"] = "mod/ban"
        await ctx.send("Banned.")

    result = _handle(bot, {
        "type": 2, "id": "1", "token": "tok",
        "data": {"name": "mod", "options": [{"name": "ban", "type": 1, "options": []}]},
    })
    assert result["statusCode"] == 200
    assert called["cmd"] == "mod/ban"


def test_subcommand_definitions_structure():
    bot = Cordless()

    @bot.command("mod/ban", description="Ban a user")
    async def mod_ban(ctx): pass

    @bot.command("mod/kick", description="Kick a user")
    async def mod_kick(ctx): pass

    parent = next(d for d in bot.router.command_definitions() if d["name"] == "mod")
    assert parent["type"] == 1
    assert {o["name"] for o in parent["options"]} == {"ban", "kick"}
    assert all(o["type"] == 1 for o in parent["options"])


def test_subcommand_group_definitions_structure():
    bot = Cordless()

    @bot.command("admin/users/ban", description="Ban a user")
    async def ban(ctx): pass

    parent = next(d for d in bot.router.command_definitions() if d["name"] == "admin")
    group = next(o for o in parent["options"] if o["name"] == "users")
    assert group["type"] == 2  # SUB_COMMAND_GROUP
    assert group["options"][0] == {"name": "ban", "description": "Ban a user", "type": 1, "options": []}


# --- Context menu commands ---

def test_user_command_dispatch():
    bot = Cordless()
    captured = {}

    @bot.user_command("Inspect User")
    async def inspect(ctx):
        captured["target"] = ctx.target_user
        await ctx.send("ok", ephemeral=True)

    result = _handle(bot, {
        "type": 2, "id": "1", "token": "tok",
        "data": {
            "name": "Inspect User",
            "type": 2,
            "target_id": "42",
            "resolved": {"users": {"42": {"id": "42", "username": "bob"}}},
        },
    })
    assert result["statusCode"] == 200
    assert captured["target"] == {"id": "42", "username": "bob"}


def test_message_command_dispatch():
    bot = Cordless()
    captured = {}

    @bot.message_command("Bookmark")
    async def bookmark(ctx):
        captured["msg"] = ctx.target_message
        await ctx.send("saved", ephemeral=True)

    result = _handle(bot, {
        "type": 2, "id": "1", "token": "tok",
        "data": {
            "name": "Bookmark",
            "type": 3,
            "target_id": "77",
            "resolved": {"messages": {"77": {"id": "77", "content": "hey"}}},
        },
    })
    assert result["statusCode"] == 200
    assert captured["msg"] == {"id": "77", "content": "hey"}


def test_context_menu_command_definitions():
    bot = Cordless()

    @bot.user_command("Inspect User")
    async def inspect(ctx): pass

    @bot.message_command("Bookmark")
    async def bookmark(ctx): pass

    defs = {d["name"]: d for d in bot.router.command_definitions()}
    assert defs["Inspect User"] == {"name": "Inspect User", "type": 2}
    assert defs["Bookmark"] == {"name": "Bookmark", "type": 3}


def test_context_menu_excluded_from_subcommand_grouping():
    bot = Cordless()

    @bot.user_command("Say Hi")
    async def say_hi(ctx): pass

    @bot.command("hi", description="Slash hi")
    async def slash_hi(ctx): pass

    defs = bot.router.command_definitions()
    # "Say Hi" must not be merged into a "Say" subcommand group
    assert any(d["name"] == "Say Hi" and d["type"] == 2 for d in defs)
    assert any(d["name"] == "hi" and d["type"] == 1 for d in defs)


# --- Unsupported type ---

def test_unsupported_interaction_type_returns_400():
    bot = Cordless()
    result = _handle(bot, {"type": 99})
    assert result["statusCode"] == 400


# --- Error handler ---

def test_error_handler_catches_exception():
    bot = Cordless()

    @bot.command("boom")
    async def boom(ctx):
        raise ValueError("test error")

    @bot.error
    async def on_error(ctx, exc):
        return await ctx.send(f"Error: {exc}")

    result = _handle(bot, {"type": 2, "data": {"name": "boom"}, "id": "1", "token": "tok"})
    assert "Error: test error" in _body(result)["data"]["content"]


# --- Permission guard ---

def test_guard_blocks_handler():
    bot = Cordless()

    def admin_only(ctx):
        raise PermissionDeniedError("Admins only")

    @bot.guard(admin_only)
    @bot.command("admin")
    async def admin_cmd(ctx):
        await ctx.send("Secret")

    result = _handle(bot, {"type": 2, "data": {"name": "admin"}, "id": "1", "token": "tok"})
    assert result["statusCode"] == 400
    assert "Admins only" in _body(result)["error"]


def test_guard_allows_handler():
    bot = Cordless()

    @bot.guard(lambda ctx: None)
    @bot.command("public")
    async def public_cmd(ctx):
        await ctx.send("Welcome!")

    result = _handle(bot, {"type": 2, "data": {"name": "public"}, "id": "1", "token": "tok"})
    assert result["statusCode"] == 200
