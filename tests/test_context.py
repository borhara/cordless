import base64
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
    run(ctx.send(components=[Container([TextDisplay("Hi")])]))
    assert json.loads(ctx.response["body"])["data"]["flags"] & 32768


def test_send_uikit_and_ephemeral_combines_flags():
    ctx = _make_ctx()
    run(ctx.send(components=[Container([TextDisplay("Hi")])], ephemeral=True))
    assert json.loads(ctx.response["body"])["data"]["flags"] == (32768 | 64)


# --- send with embeds / components ---


def test_send_with_embed():
    ctx = _make_ctx()
    run(ctx.send("content", embeds=[Embed(title="Hi")]))
    assert json.loads(ctx.response["body"])["data"]["embeds"][0]["title"] == "Hi"


def test_send_with_components():
    ctx = _make_ctx()
    run(ctx.send(components=[ActionRow([Button("Click", custom_id="c")])]))
    assert json.loads(ctx.response["body"])["data"]["components"][0]["type"] == 1


# --- send/edit with files (initial response, non-worker) ---


def test_send_with_files_returns_base64_multipart_body():
    ctx = _make_ctx()
    run(ctx.send("here", files=[("report.pdf", b"binary-data")]))

    assert ctx.response["isBase64Encoded"] is True
    assert ctx.response["headers"]["Content-Type"].startswith("multipart/form-data")

    body = base64.b64decode(ctx.response["body"])
    assert b'name="payload_json"' in body
    assert b'name="files[0]"; filename="report.pdf"' in body
    assert b"binary-data" in body

    boundary = ctx.response["headers"]["Content-Type"].split("boundary=")[1]
    payload_part = body.split(f"--{boundary}".encode())[1]
    payload_json = json.loads(payload_part.split(b"\r\n\r\n", 1)[1].rsplit(b"\r\n", 1)[0])
    assert payload_json["data"]["content"] == "here"
    assert payload_json["data"]["attachments"] == [{"id": 0, "filename": "report.pdf"}]


def test_send_without_files_is_plain_json():
    ctx = _make_ctx()
    run(ctx.send("hi"))
    assert "isBase64Encoded" not in ctx.response
    assert ctx.response["headers"]["Content-Type"] == "application/json"


def test_edit_with_files_returns_base64_multipart_body():
    ctx = _make_ctx()
    run(ctx.edit("updated", files=[("img.png", b"\x89PNG...")]))

    assert ctx.response["isBase64Encoded"] is True
    body = base64.b64decode(ctx.response["body"])
    assert b'filename="img.png"' in body
    assert b"\x89PNG..." in body


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
    ctx = Context(
        {
            "type": 5,
            "data": {
                "custom_id": "feedback",
                "components": [{"type": 1, "components": [{"type": 4, "custom_id": "msg", "value": "Hello"}]}],
            },
            "id": "2",
            "token": "tok",
        }
    )
    assert ctx.modal_values == {"msg": "Hello"}


# --- select values ---


def test_select_values_on_context():
    ctx = Context(
        {
            "type": 3,
            "data": {"custom_id": "color", "component_type": 3, "values": ["red", "blue"]},
            "id": "3",
            "token": "tok",
        }
    )
    assert ctx.values == ["red", "blue"]


# --- user / member attribute access ---


def test_user_exposes_attributes_in_guild():
    ctx = _make_ctx(
        member={
            "nick": "Nick",
            "user": {"id": "1", "username": "testuser", "global_name": "Test User"},
        }
    )
    assert ctx.user.username == "testuser"
    assert ctx.user.id == "1"
    assert ctx.user.display_name == "Test User"
    assert ctx.member.nick == "Nick"
    assert ctx.member.display_name == "Nick"
    assert ctx.member.user.username == "testuser"


def test_member_permissions_exposed():
    ctx = _make_ctx(
        member={
            "nick": "shiv",
            "permissions": "8",  # administrator
            "user": {"id": "1", "username": "shiv"},
        }
    )
    assert ctx.member.permissions.administrator
    assert not ctx.member.permissions.manage_guild


def test_user_exposes_attributes_in_dm():
    ctx = _make_ctx(user={"id": "2", "username": "testuser"})
    assert ctx.user.username == "testuser"
    assert ctx.user.display_name == "testuser"
    assert ctx.member is None


def test_user_missing_attribute_raises():
    ctx = _make_ctx(user={"id": "2", "username": "testuser"})
    try:
        ctx.user.email
    except AttributeError:
        pass
    else:
        raise AssertionError("expected AttributeError for missing field")


# --- message / channel / attachment attribute access ---


def test_message_and_channel_expose_attributes():
    ctx = _make_ctx(
        message={"id": "10", "content": "hi", "author": {"id": "1", "username": "testuser"}},
        channel={"id": "20", "name": "general"},
    )
    assert ctx.message.content == "hi"
    assert ctx.message.author.username == "testuser"
    assert ctx.channel.name == "general"


def test_message_and_channel_absent_are_none():
    ctx = _make_ctx()
    assert ctx.message is None
    assert ctx.channel is None


def test_attachment_exposes_attributes():
    ctx = _make_ctx(
        data={
            "name": "upload",
            "options": [{"name": "file", "type": 11, "value": "att-1"}],
            "resolved": {"attachments": {"att-1": {"filename": "cat.png", "size": 12}}},
        }
    )
    assert ctx.attachments["att-1"].filename == "cat.png"
    assert ctx.attachments["att-1"].size == 12


# --- context menu: target attributes ---


def test_target_user_from_user_command():
    ctx = Context(
        {
            "type": 2,
            "data": {
                "name": "Inspect User",
                "type": 2,
                "target_id": "999",
                "resolved": {
                    "users": {"999": {"id": "999", "username": "shiv"}},
                    "members": {"999": {"nick": "Alice"}},
                },
            },
            "id": "4",
            "token": "tok",
        }
    )
    assert ctx.target_user == {"id": "999", "username": "shiv"}
    assert ctx.target_user.username == "shiv"
    assert ctx.target_member.nick == "Alice"
    # resolved.members omits the nested user object; Context stitches it back in
    assert ctx.target_member.user.username == "shiv"
    assert ctx.target_message is None


def test_target_message_from_message_command():
    ctx = Context(
        {
            "type": 2,
            "data": {
                "name": "Bookmark",
                "type": 3,
                "target_id": "555",
                "resolved": {
                    "messages": {"555": {"id": "555", "content": "hello world"}},
                },
            },
            "id": "5",
            "token": "tok",
        }
    )
    assert ctx.target_message == {"id": "555", "content": "hello world"}
    assert ctx.target_message.content == "hello world"
    assert ctx.target_user is None
    assert ctx.target_member is None


def test_target_attributes_absent_on_slash_command():
    ctx = _make_ctx()
    assert ctx.target_user is None
    assert ctx.target_member is None
    assert ctx.target_message is None


# --- entity-select components: resolved objects ---


def test_user_select_exposes_resolved_users_and_members():
    ctx = Context(
        {
            "type": 3,
            "data": {
                "custom_id": "pick_user",
                "component_type": 5,
                "values": ["1"],
                "resolved": {
                    "users": {"1": {"id": "1", "username": "shiv"}},
                    "members": {"1": {"nick": "Ali"}},
                },
            },
            "id": "6",
            "token": "tok",
        }
    )
    assert ctx.values == ["1"]
    assert ctx.resolved_users["1"].username == "shiv"
    assert ctx.resolved_members["1"].nick == "Ali"
    # resolved.members omits the nested user object; Context stitches it back in
    assert ctx.resolved_members["1"].user.username == "shiv"


def test_role_select_exposes_resolved_roles():
    ctx = Context(
        {
            "type": 3,
            "data": {
                "custom_id": "pick_role",
                "component_type": 6,
                "values": ["2"],
                "resolved": {"roles": {"2": {"id": "2", "name": "Admins", "color": 0}}},
            },
            "id": "7",
            "token": "tok",
        }
    )
    assert ctx.resolved_roles["2"].name == "Admins"
    assert ctx.resolved_roles["2"].mention == "<@&2>"


def test_channel_select_exposes_resolved_channels():
    ctx = Context(
        {
            "type": 3,
            "data": {
                "custom_id": "pick_channel",
                "component_type": 8,
                "values": ["3"],
                "resolved": {"channels": {"3": {"id": "3", "name": "general", "type": 0}}},
            },
            "id": "8",
            "token": "tok",
        }
    )
    assert ctx.resolved_channels["3"].name == "general"


def test_resolved_entity_dicts_empty_when_not_applicable():
    ctx = _make_ctx()
    assert ctx.resolved_users == {}
    assert ctx.resolved_members == {}
    assert ctx.resolved_roles == {}
    assert ctx.resolved_channels == {}
