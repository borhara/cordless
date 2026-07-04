import json
from asyncio import run

from cordless import ActionRow, Button, Container, Embed, Modal, TextDisplay, TextInput
from cordless.app import Cordless
from cordless.context import Context


def _make_ctx(data=None, **extra):
    interaction = {"type": 2, "data": data or {"name": "ping"}, "id": "1", "token": "tok", **extra}
    return Context(interaction)


# --- Basic attributes ---

def test_custom_id_exposed_on_button_context():
    bot = Cordless()
    captured = {}

    @bot.button("confirm")
    async def confirm(ctx):
        captured["custom_id"] = ctx.custom_id
        return await ctx.edit("confirmed")

    bot.handle({"body": json.dumps({"type": 3, "data": {"custom_id": "confirm"}})})
    assert captured["custom_id"] == "confirm"


def test_interaction_id_and_token_exposed():
    bot = Cordless()
    captured = {}

    @bot.command("ping")
    async def ping(ctx):
        captured["interaction_id"] = ctx.interaction_id
        captured["token"] = ctx.token
        return await ctx.send("pong")

    bot.handle({"body": json.dumps({"type": 2, "data": {"name": "ping"}, "id": "123", "token": "abc"})})
    assert captured["interaction_id"] == "123"
    assert captured["token"] == "abc"


# --- send flags ---

def test_send_ephemeral_sets_flags():
    bot = Cordless()

    @bot.command("secret")
    async def secret(ctx):
        return await ctx.send("shh", ephemeral=True)

    result = bot.handle({"body": json.dumps({"type": 2, "data": {"name": "secret"}})})
    body = json.loads(result["body"])
    assert body["data"]["flags"] == 64
    assert body["data"]["content"] == "shh"


def test_send_without_ephemeral_has_no_flags():
    bot = Cordless()

    @bot.command("public")
    async def public(ctx):
        return await ctx.send("hello")

    result = bot.handle({"body": json.dumps({"type": 2, "data": {"name": "public"}})})
    assert "flags" not in json.loads(result["body"])["data"]


def test_send_uikit_sets_flag():
    ctx = _make_ctx()
    run(ctx.send(components=[Container(TextDisplay("Hi"))]))
    assert json.loads(ctx.response["body"])["data"]["flags"] & 32768


def test_send_uikit_and_ephemeral_combines_flags():
    ctx = _make_ctx()
    run(ctx.send(components=[Container(TextDisplay("Hi"))], ephemeral=True))
    assert json.loads(ctx.response["body"])["data"]["flags"] == (32768 | 64)


# --- send with embeds / components ---

def test_send_with_embed():
    ctx = _make_ctx()
    run(ctx.send("content", embeds=[Embed(title="Hi")]))
    assert json.loads(ctx.response["body"])["data"]["embeds"][0]["title"] == "Hi"


def test_send_with_components():
    ctx = _make_ctx()
    run(ctx.send(components=[ActionRow(Button("Click", custom_id="c"))]))
    assert json.loads(ctx.response["body"])["data"]["components"][0]["type"] == 1


# --- send_modal ---

def test_send_modal():
    ctx = _make_ctx()
    run(ctx.send_modal(Modal("my_modal", "Title", TextInput("q", "Question"))))
    body = json.loads(ctx.response["body"])
    assert body["type"] == 9
    assert body["data"]["custom_id"] == "my_modal"


# --- respond_autocomplete ---

def test_respond_autocomplete():
    ctx = _make_ctx()
    run(ctx.respond_autocomplete([{"name": "Option A", "value": "a"}]))
    body = json.loads(ctx.response["body"])
    assert body["type"] == 8
    assert body["data"]["choices"][0]["value"] == "a"


# --- modal_values ---

def test_modal_values_parsed_from_submission():
    ctx = Context({
        "type": 5,
        "data": {
            "custom_id": "feedback",
            "components": [
                {"type": 1, "components": [{"type": 4, "custom_id": "msg", "value": "Hello"}]}
            ],
        },
        "id": "2", "token": "tok",
    })
    assert ctx.modal_values == {"msg": "Hello"}


# --- select values ---

def test_select_values_on_context():
    ctx = Context({
        "type": 3,
        "data": {"custom_id": "color", "component_type": 3, "values": ["red", "blue"]},
        "id": "3", "token": "tok",
    })
    assert ctx.values == ["red", "blue"]


# --- context menu: target attributes ---

def test_target_user_from_user_command():
    ctx = Context({
        "type": 2,
        "data": {
            "name": "Inspect User",
            "type": 2,
            "target_id": "999",
            "resolved": {
                "users": {"999": {"id": "999", "username": "alice"}},
                "members": {"999": {"nick": "Alice"}},
            },
        },
        "id": "4", "token": "tok",
    })
    assert ctx.target_user == {"id": "999", "username": "alice"}
    assert ctx.target_member == {"nick": "Alice"}
    assert ctx.target_message is None


def test_target_message_from_message_command():
    ctx = Context({
        "type": 2,
        "data": {
            "name": "Bookmark",
            "type": 3,
            "target_id": "555",
            "resolved": {
                "messages": {"555": {"id": "555", "content": "hello world"}},
            },
        },
        "id": "5", "token": "tok",
    })
    assert ctx.target_message == {"id": "555", "content": "hello world"}
    assert ctx.target_user is None
    assert ctx.target_member is None


def test_target_attributes_absent_on_slash_command():
    ctx = _make_ctx()
    assert ctx.target_user is None
    assert ctx.target_member is None
    assert ctx.target_message is None
