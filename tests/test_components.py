"""Tests for component builders, embeds, modals, and new context methods."""
import asyncio
import json
import pytest

from cordless import (
    ActionRow, Button, ButtonStyle, ChannelSelect, Container,
    Embed, EmbedField, MediaGallery, MentionableSelect, Modal,
    RoleSelect, Section, SelectOption, Separator, StringSelect,
    TextDisplay, TextInput, TextInputStyle, Thumbnail, UserSelect,
    Cordless,
)
from cordless.errors import PermissionDeniedError, UnknownComponentError, UnknownModalError
from cordless.context import Context


# --- SelectOption ---

def test_select_option_minimal():
    o = SelectOption("Label", "val")
    d = o.to_dict()
    assert d == {"label": "Label", "value": "val"}


def test_select_option_full():
    o = SelectOption("Label", "val", description="Desc", default=True)
    d = o.to_dict()
    assert d["description"] == "Desc"
    assert d["default"] is True


# --- Button ---

def test_button_primary():
    b = Button("Click me", custom_id="btn1")
    d = b.to_dict()
    assert d["type"] == 2
    assert d["label"] == "Click me"
    assert d["custom_id"] == "btn1"
    assert d["style"] == 1


def test_button_link():
    b = Button("Go", style=ButtonStyle.LINK, url="https://example.com")
    d = b.to_dict()
    assert d["style"] == 5
    assert d["url"] == "https://example.com"
    assert "custom_id" not in d


def test_button_disabled():
    b = Button("X", custom_id="x", disabled=True)
    assert b.to_dict()["disabled"] is True


# --- ActionRow ---

def test_action_row_wraps_buttons():
    row = ActionRow(Button("A", custom_id="a"), Button("B", custom_id="b"))
    d = row.to_dict()
    assert d["type"] == 1
    assert len(d["components"]) == 2


# --- StringSelect ---

def test_string_select():
    opts = [SelectOption("One", "1"), SelectOption("Two", "2")]
    s = StringSelect("color", opts, placeholder="Pick one")
    d = s.to_dict()
    assert d["type"] == 3
    assert d["custom_id"] == "color"
    assert d["placeholder"] == "Pick one"
    assert len(d["options"]) == 2


# --- Other select types ---

def test_user_select():
    assert UserSelect("u").to_dict()["type"] == 5

def test_role_select():
    assert RoleSelect("r").to_dict()["type"] == 6

def test_mentionable_select():
    assert MentionableSelect("m").to_dict()["type"] == 7

def test_channel_select():
    d = ChannelSelect("ch", channel_types=[0, 2]).to_dict()
    assert d["type"] == 8
    assert d["channel_types"] == [0, 2]


# --- TextInput / Modal ---

def test_text_input():
    ti = TextInput("name_input", "Your name", style=TextInputStyle.SHORT, placeholder="e.g. Alice")
    d = ti.to_dict()
    assert d["type"] == 4
    assert d["custom_id"] == "name_input"
    assert d["style"] == 1
    assert d["placeholder"] == "e.g. Alice"


def test_modal_wraps_text_inputs_in_action_rows():
    ti = TextInput("q", "Question")
    m = Modal("feedback_modal", "Feedback", ti)
    d = m.to_dict()
    assert d["custom_id"] == "feedback_modal"
    assert d["title"] == "Feedback"
    assert d["components"][0]["type"] == 1
    assert d["components"][0]["components"][0]["type"] == 4


def test_modal_accepts_action_rows_directly():
    ti = TextInput("q", "Question")
    row = ActionRow(ti)
    m = Modal("m", "Title", row)
    d = m.to_dict()
    assert d["components"][0]["type"] == 1


# --- Embed ---

def test_embed_minimal():
    e = Embed(title="Hello", description="World", color=0xFF5733)
    d = e.to_dict()
    assert d["title"] == "Hello"
    assert d["description"] == "World"
    assert d["color"] == 0xFF5733


def test_embed_all_fields():
    e = (
        Embed(title="T")
        .set_footer("Footer", icon_url="https://i.example.com/icon.png")
        .set_image("https://i.example.com/img.png")
        .set_thumbnail("https://i.example.com/thumb.png")
        .set_author("Author", url="https://example.com", icon_url="https://i.example.com/a.png")
        .add_field("Field", "Value", inline=True)
    )
    d = e.to_dict()
    assert d["footer"]["text"] == "Footer"
    assert d["image"]["url"] == "https://i.example.com/img.png"
    assert d["thumbnail"]["url"] == "https://i.example.com/thumb.png"
    assert d["author"]["name"] == "Author"
    assert d["fields"][0]["name"] == "Field"
    assert d["fields"][0]["inline"] is True


def test_embed_field():
    f = EmbedField("Name", "Value", inline=True)
    d = f.to_dict()
    assert d == {"name": "Name", "value": "Value", "inline": True}


# --- UI Kit components ---

def test_text_display():
    d = TextDisplay("Hello world").to_dict()
    assert d == {"type": 10, "content": "Hello world"}


def test_thumbnail():
    d = Thumbnail("https://example.com/img.png", description="Alt").to_dict()
    assert d["type"] == 11
    assert d["media"]["url"] == "https://example.com/img.png"
    assert d["description"] == "Alt"


def test_separator():
    d = Separator(divider=True, spacing=2).to_dict()
    assert d == {"type": 14, "divider": True, "spacing": 2}


def test_section_with_accessory():
    thumb = Thumbnail("https://example.com/img.png")
    s = Section(TextDisplay("Hi"), accessory=thumb)
    d = s.to_dict()
    assert d["type"] == 9
    assert d["accessory"]["type"] == 11


def test_container():
    c = Container(TextDisplay("Hi"), accent_color=0xFF0000)
    d = c.to_dict()
    assert d["type"] == 17
    assert d["accent_color"] == 0xFF0000


def test_media_gallery():
    d = MediaGallery({"url": "https://example.com/img.png"}).to_dict()
    assert d["type"] == 12


# --- Context: embeds and components in send ---

def _make_ctx(data=None):
    interaction = {"type": 2, "data": data or {"name": "ping"}, "id": "1", "token": "tok"}
    return Context(interaction)


def test_send_with_embed():
    ctx = _make_ctx()
    e = Embed(title="Hi")
    asyncio.run(ctx.send("content", embeds=[e]))
    body = json.loads(ctx.response["body"])
    assert body["data"]["embeds"][0]["title"] == "Hi"


def test_send_with_components():
    ctx = _make_ctx()
    row = ActionRow(Button("Click", custom_id="c"))
    asyncio.run(ctx.send(components=[row]))
    body = json.loads(ctx.response["body"])
    assert body["data"]["components"][0]["type"] == 1


def test_send_uikit_sets_flag():
    ctx = _make_ctx()
    asyncio.run(ctx.send(components=[Container(TextDisplay("Hi"))]))
    body = json.loads(ctx.response["body"])
    assert body["data"]["flags"] & 32768


def test_send_uikit_and_ephemeral_combines_flags():
    ctx = _make_ctx()
    asyncio.run(ctx.send(components=[Container(TextDisplay("Hi"))], ephemeral=True))
    body = json.loads(ctx.response["body"])
    assert body["data"]["flags"] == (32768 | 64)


# --- Context: send_modal ---

def test_send_modal():
    ctx = _make_ctx()
    m = Modal("my_modal", "Title", TextInput("q", "Question"))
    asyncio.run(ctx.send_modal(m))
    body = json.loads(ctx.response["body"])
    assert body["type"] == 9
    assert body["data"]["custom_id"] == "my_modal"


# --- Context: respond_autocomplete ---

def test_respond_autocomplete():
    ctx = _make_ctx()
    asyncio.run(ctx.respond_autocomplete([{"name": "Option A", "value": "a"}]))
    body = json.loads(ctx.response["body"])
    assert body["type"] == 8
    assert body["data"]["choices"][0]["value"] == "a"


# --- Context: modal_values ---

def test_modal_values_parsed_from_submission():
    interaction = {
        "type": 5,
        "data": {
            "custom_id": "feedback",
            "components": [
                {"type": 1, "components": [{"type": 4, "custom_id": "msg", "value": "Hello"}]}
            ],
        },
        "id": "2",
        "token": "tok",
    }
    ctx = Context(interaction)
    assert ctx.modal_values == {"msg": "Hello"}


# --- Context: select values ---

def test_select_values_on_context():
    interaction = {
        "type": 3,
        "data": {"custom_id": "color", "component_type": 3, "values": ["red", "blue"]},
        "id": "3",
        "token": "tok",
    }
    ctx = Context(interaction)
    assert ctx.values == ["red", "blue"]


# --- Router: selects ---

def test_select_dispatch():
    bot = Cordless()

    @bot.select("color_select")
    async def on_select(ctx):
        await ctx.edit("You picked!")

    interaction = {
        "type": 3,
        "data": {"custom_id": "color_select", "component_type": 3, "values": ["red"]},
        "id": "4",
        "token": "tok",
    }
    resp = bot.handle({"body": json.dumps(interaction)})
    assert resp["statusCode"] == 200


def test_unknown_select_returns_400():
    bot = Cordless()
    interaction = {
        "type": 3,
        "data": {"custom_id": "nope", "component_type": 3},
        "id": "5",
        "token": "tok",
    }
    resp = bot.handle({"body": json.dumps(interaction)})
    assert resp["statusCode"] == 400


# --- Router: modals ---

def test_modal_dispatch():
    bot = Cordless()

    @bot.modal("feedback_modal")
    async def on_modal(ctx):
        await ctx.send("Thanks!")

    interaction = {
        "type": 5,
        "data": {
            "custom_id": "feedback_modal",
            "components": [
                {"type": 1, "components": [{"type": 4, "custom_id": "msg", "value": "Hi"}]}
            ],
        },
        "id": "6",
        "token": "tok",
    }
    resp = bot.handle({"body": json.dumps(interaction)})
    assert resp["statusCode"] == 200


def test_unknown_modal_returns_400():
    bot = Cordless()
    interaction = {
        "type": 5,
        "data": {"custom_id": "ghost_modal", "components": []},
        "id": "7",
        "token": "tok",
    }
    resp = bot.handle({"body": json.dumps(interaction)})
    assert resp["statusCode"] == 400


# --- Router: autocomplete ---

def test_autocomplete_dispatch():
    bot = Cordless()

    @bot.command("search", description="Search")
    async def search(ctx):
        await ctx.send("results")

    @bot.autocomplete("search", "query")
    async def search_query_autocomplete(ctx):
        await ctx.respond_autocomplete([{"name": "foo", "value": "foo"}])

    interaction = {
        "type": 4,
        "data": {
            "name": "search",
            "options": [{"name": "query", "value": "fo", "focused": True}],
        },
        "id": "8",
        "token": "tok",
    }
    resp = bot.handle({"body": json.dumps(interaction)})
    body = json.loads(resp["body"])
    assert body["type"] == 8


# --- Router: subcommands ---

def test_subcommand_dispatch():
    bot = Cordless()
    called = {}

    @bot.command("mod/ban", description="Ban a user")
    async def mod_ban(ctx):
        called["cmd"] = "mod/ban"
        await ctx.send("Banned.")

    interaction = {
        "type": 2,
        "data": {
            "name": "mod",
            "options": [{"name": "ban", "type": 1, "options": []}],
        },
        "id": "9",
        "token": "tok",
    }
    resp = bot.handle({"body": json.dumps(interaction)})
    assert resp["statusCode"] == 200
    assert called["cmd"] == "mod/ban"


def test_subcommand_definitions_structure():
    bot = Cordless()

    @bot.command("mod/ban", description="Ban a user")
    async def mod_ban(ctx): pass

    @bot.command("mod/kick", description="Kick a user")
    async def mod_kick(ctx): pass

    defs = bot.router.command_definitions()
    parent = next(d for d in defs if d["name"] == "mod")
    assert parent["type"] == 1
    sub_names = {o["name"] for o in parent["options"]}
    assert sub_names == {"ban", "kick"}
    for opt in parent["options"]:
        assert opt["type"] == 1  # SUB_COMMAND


def test_subcommand_group_definitions_structure():
    bot = Cordless()

    @bot.command("admin/users/ban", description="Ban a user")
    async def ban(ctx): pass

    defs = bot.router.command_definitions()
    parent = next(d for d in defs if d["name"] == "admin")
    group = next(o for o in parent["options"] if o["name"] == "users")
    assert group["type"] == 2  # SUB_COMMAND_GROUP
    sub = group["options"][0]
    assert sub["name"] == "ban"
    assert sub["type"] == 1  # SUB_COMMAND


# --- Error handler ---

def test_error_handler_catches_exception():
    bot = Cordless()

    @bot.command("boom", description="Explodes")
    async def boom(ctx):
        raise ValueError("test error")

    @bot.error
    async def on_error(ctx, exc):
        return await ctx.send(f"Error: {exc}")

    interaction = {"type": 2, "data": {"name": "boom"}, "id": "10", "token": "tok"}
    resp = bot.handle({"body": json.dumps(interaction)})
    body = json.loads(resp["body"])
    assert "Error: test error" in body["data"]["content"]


# --- Permission guard ---

def test_guard_blocks_handler():
    bot = Cordless()

    def admin_only(ctx):
        raise PermissionDeniedError("Admins only")

    @bot.guard(admin_only)
    @bot.command("admin", description="Admin only")
    async def admin_cmd(ctx):
        await ctx.send("Secret admin stuff")

    interaction = {"type": 2, "data": {"name": "admin"}, "id": "11", "token": "tok"}
    resp = bot.handle({"body": json.dumps(interaction)})
    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert "Admins only" in body["error"]


def test_guard_allows_handler():
    bot = Cordless()

    def allow_all(ctx):
        pass  # no exception = allowed

    @bot.guard(allow_all)
    @bot.command("public", description="Public command")
    async def public_cmd(ctx):
        await ctx.send("Welcome!")

    interaction = {"type": 2, "data": {"name": "public"}, "id": "12", "token": "tok"}
    resp = bot.handle({"body": json.dumps(interaction)})
    assert resp["statusCode"] == 200
