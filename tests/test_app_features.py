"""0.11+ surface: bot.handler(), typed options, name validation, prefix args, attachments."""

import asyncio
import json
from typing import Literal
from unittest.mock import patch

import pytest

from cordless import Cog
from cordless.app import Cordless, options_from_signature


def _handle(bot, payload):
    return bot.handle({"body": json.dumps(payload)})


def _body(result):
    return json.loads(result["body"])


# --- bot.handler() ---


def test_handler_returns_lambda_compatible_callable():
    bot = Cordless()

    @bot.command("ping")
    async def ping(ctx):
        await ctx.send("pong")

    handler = bot.handler()
    result = handler({"body": json.dumps({"type": 2, "data": {"name": "ping"}})}, None)
    assert _body(result)["data"]["content"] == "pong"


# --- invalid JSON ---


def test_invalid_json_body_returns_400():
    bot = Cordless()
    result = bot.handle({"body": "{not json"})
    assert result["statusCode"] == 400


def test_missing_body_returns_400():
    bot = Cordless()
    result = bot.handle({})
    assert result["statusCode"] == 400


# --- ctx.defer(ephemeral=True) ---


def test_defer_ephemeral_sets_flags():
    from asyncio import run

    from cordless.context import Context

    ctx = Context({"type": 2, "data": {"name": "x"}, "id": "1", "token": "t"})
    run(ctx.defer(ephemeral=True))
    body = json.loads(ctx.response["body"])
    assert body["type"] == 5
    assert body["data"]["flags"] == 64


def test_defer_plain_has_no_data():
    from asyncio import run

    from cordless.context import Context

    ctx = Context({"type": 2, "data": {"name": "x"}, "id": "1", "token": "t"})
    run(ctx.defer())
    assert "data" not in json.loads(ctx.response["body"])


# --- command name validation ---


def test_invalid_command_name_raises_at_decoration():
    bot = Cordless()
    with pytest.raises(ValueError):

        @bot.command("Bad Name")
        async def bad(ctx):
            pass


def test_uppercase_command_name_raises():
    bot = Cordless()
    with pytest.raises(ValueError):

        @bot.command("Ping")
        async def ping(ctx):
            pass


def test_too_long_command_name_raises():
    bot = Cordless()
    with pytest.raises(ValueError):

        @bot.command("a" * 33)
        async def long_cmd(ctx):
            pass


def test_subcommand_path_segments_validated():
    bot = Cordless()

    @bot.command("mod/ban")  # valid path
    async def ban(ctx):
        pass

    with pytest.raises(ValueError):

        @bot.command("mod/Bad Seg")
        async def bad(ctx):
            pass


def test_context_menu_names_allow_spaces_and_case():
    bot = Cordless()

    @bot.user_command("Inspect User")
    async def inspect(ctx):
        pass  # must not raise


# --- options from type hints ---


def test_options_inferred_from_signature():
    async def buy(ctx, item: str, qty: int = 1):
        pass

    opts = options_from_signature(buy)
    assert opts[0] == {"name": "item", "description": "No description provided.", "type": 3, "required": True}
    assert opts[1]["name"] == "qty"
    assert opts[1]["type"] == 4
    assert "required" not in opts[1]


def test_bool_and_float_annotations():
    async def f(ctx, flag: bool, ratio: float):
        pass

    opts = options_from_signature(f)
    assert opts[0]["type"] == 5
    assert opts[1]["type"] == 10


def test_unannotated_param_defaults_to_string():
    async def f(ctx, thing):
        pass

    assert options_from_signature(f)[0]["type"] == 3


def test_stringized_annotations_are_resolved():
    # `from __future__ import annotations` turns every annotation into a
    # string; the types must still resolve instead of falling back to string
    src = "from __future__ import annotations\nasync def buy(ctx, item: str, qty: int = 1, ratio: float = 1.0): ..."
    ns = {}
    exec(compile(src, "<test>", "exec"), ns)

    opts = {o["name"]: o for o in options_from_signature(ns["buy"])}
    assert opts["item"]["type"] == 3
    assert opts["qty"]["type"] == 4
    assert opts["ratio"]["type"] == 10


def test_stringized_literal_choices_are_resolved():
    src = (
        "from __future__ import annotations\n"
        "from typing import Literal\n"
        "async def f(ctx, size: Literal['small', 'large']): ..."
    )
    ns = {}
    exec(compile(src, "<test>", "exec"), ns)

    opt = options_from_signature(ns["f"])[0]
    assert opt["choices"] == [{"name": "small", "value": "small"}, {"name": "large", "value": "large"}]


def test_unresolvable_annotation_falls_back_to_string():
    async def f(ctx, thing: "NotDefinedAnywhere"):  # noqa: F821
        pass

    assert options_from_signature(f)[0]["type"] == 3


def test_string_literal_choices():
    async def f(ctx, size: Literal["small", "large"]):
        pass

    opt = options_from_signature(f)[0]
    assert opt["type"] == 3
    assert opt["choices"] == [{"name": "small", "value": "small"}, {"name": "large", "value": "large"}]


def test_int_literal_choices():
    async def f(ctx, tier: Literal[1, 2, 3]):
        pass

    opt = options_from_signature(f)[0]
    assert opt["type"] == 4
    assert opt["choices"][0] == {"name": "1", "value": 1}


def test_float_literal_choices_are_typed_as_number():
    async def f(ctx, ratio: Literal[1.5, 2.5]):
        pass

    opt = options_from_signature(f)[0]
    assert opt["type"] == 10
    assert opt["choices"][0] == {"name": "1.5", "value": 1.5}


def test_bool_literal_choices_raise():
    async def f(ctx, flag: Literal[True, False]):
        pass

    with pytest.raises(ValueError):
        options_from_signature(f)


def test_typed_options_registered_in_definitions():
    bot = Cordless()

    @bot.command("buy")
    async def buy(ctx, item: str, qty: int = 1):
        await ctx.send("ok")

    cmd = next(d for d in bot.router.command_definitions() if d["name"] == "buy")
    assert [o["name"] for o in cmd["options"]] == ["item", "qty"]


def test_explicit_options_override_signature():
    bot = Cordless()
    explicit = [{"name": "other", "description": "x", "type": 3}]

    @bot.command("cmd", options=explicit)
    async def cmd(ctx, item: str):
        await ctx.send("ok")

    cmd_def = next(d for d in bot.router.command_definitions() if d["name"] == "cmd")
    assert cmd_def["options"] == explicit


def test_typed_options_passed_as_kwargs():
    bot = Cordless()
    got = {}

    @bot.command("buy")
    async def buy(ctx, item: str, qty: int = 1):
        got.update(item=item, qty=qty)
        await ctx.send("ok")

    _handle(
        bot,
        {
            "type": 2,
            "id": "1",
            "token": "t",
            "data": {
                "name": "buy",
                "options": [{"name": "item", "type": 3, "value": "sword"}, {"name": "qty", "type": 4, "value": 3}],
            },
        },
    )
    assert got == {"item": "sword", "qty": 3}


def test_typed_options_defaults_apply_when_omitted():
    bot = Cordless()
    got = {}

    @bot.command("buy")
    async def buy(ctx, item: str, qty: int = 1):
        got.update(item=item, qty=qty)
        await ctx.send("ok")

    _handle(
        bot,
        {
            "type": 2,
            "id": "1",
            "token": "t",
            "data": {
                "name": "buy",
                "options": [{"name": "item", "type": 3, "value": "shield"}],
            },
        },
    )
    assert got == {"item": "shield", "qty": 1}


def test_ctx_only_handlers_unchanged():
    bot = Cordless()

    @bot.command("ping")
    async def ping(ctx):
        await ctx.send("pong")

    result = _handle(bot, {"type": 2, "data": {"name": "ping"}})
    assert _body(result)["data"]["content"] == "pong"


def test_cog_command_guild_ids_threads_through_to_router():
    admin = Cog()

    @admin.command("purge", guild_ids=["guild-1", "guild-2"])
    async def purge(ctx):
        await ctx.send("done")

    bot = Cordless()
    bot.add_cog(admin)

    assert bot.router.guild_ids() == ["guild-1", "guild-2"]
    assert [d["name"] for d in bot.router.scoped_command_definitions("guild-1")] == ["purge"]
    assert [d["name"] for d in bot.router.scoped_command_definitions("guild-2")] == ["purge"]
    assert bot.router.scoped_command_definitions(None) == []


def test_cog_command_options_from_signature():
    shop = Cog()

    @shop.command("buy")
    async def buy(ctx, item: str, qty: int = 2):
        await ctx.send(f"{qty}x {item}")

    bot = Cordless()
    bot.add_cog(shop)

    cmd = next(d for d in bot.router.command_definitions() if d["name"] == "buy")
    assert [o["name"] for o in cmd["options"]] == ["item", "qty"]

    got = _handle(
        bot,
        {
            "type": 2,
            "id": "1",
            "token": "t",
            "data": {
                "name": "buy",
                "options": [{"name": "item", "type": 3, "value": "potion"}],
            },
        },
    )
    assert _body(got)["data"]["content"] == "2x potion"


# --- custom_id prefix matching + args ---


def test_button_prefix_args():
    bot = Cordless()
    got = {}

    @bot.button("shop")
    async def shop(ctx):
        got["args"] = ctx.custom_id_args
        await ctx.edit("ok")

    _handle(bot, {"type": 3, "id": "1", "token": "t", "data": {"custom_id": "shop:item1:2"}})
    assert got["args"] == ["item1", "2"]


def test_select_prefix_matching():
    bot = Cordless()
    got = {}

    @bot.select("pick")
    async def pick(ctx):
        got["args"] = ctx.custom_id_args
        await ctx.edit("ok")

    result = _handle(
        bot,
        {"type": 3, "id": "1", "token": "t", "data": {"custom_id": "pick:page2", "component_type": 3, "values": ["a"]}},
    )
    assert result["statusCode"] == 200
    assert got["args"] == ["page2"]


def test_modal_prefix_matching():
    bot = Cordless()
    got = {}

    @bot.modal("form")
    async def form(ctx):
        got["args"] = ctx.custom_id_args
        await ctx.send("ok")

    result = _handle(bot, {"type": 5, "id": "1", "token": "t", "data": {"custom_id": "form:step2", "components": []}})
    assert result["statusCode"] == 200
    assert got["args"] == ["step2"]


def test_exact_match_has_no_args():
    bot = Cordless()
    got = {}

    @bot.button("confirm")
    async def confirm(ctx):
        got["args"] = ctx.custom_id_args
        await ctx.edit("ok")

    _handle(bot, {"type": 3, "id": "1", "token": "t", "data": {"custom_id": "confirm"}})
    assert got["args"] == []


# --- ctx.attachments ---


def test_attachments_resolved_from_interaction():
    bot = Cordless()
    got = {}

    @bot.command("upload")
    async def upload(ctx):
        got["attachment"] = ctx.attachments[ctx.options["file"]]
        await ctx.send("ok")

    _handle(
        bot,
        {
            "type": 2,
            "id": "1",
            "token": "t",
            "data": {
                "name": "upload",
                "options": [{"name": "file", "type": 11, "value": "att-1"}],
                "resolved": {"attachments": {"att-1": {"filename": "cat.png", "url": "https://cdn/x.png", "size": 12}}},
            },
        },
    )
    assert got["attachment"]["filename"] == "cat.png"


def test_empty_public_key_rejects_invalid_signature():
    bot = Cordless(public_key="")

    @bot.command("ping")
    async def ping(ctx):
        await ctx.send("pong")

    result = bot.handle(
        {
            "body": json.dumps({"type": 2, "data": {"name": "ping"}}),
            "headers": {
                "x-signature-ed25519": "a" * 128,
                "x-signature-timestamp": "1234567890",
            },
        }
    )
    assert result["statusCode"] == 401


def test_raw_dict_uikit_component_sets_flag():
    bot = Cordless()

    @bot.command("test")
    async def test_cmd(ctx):
        await ctx.send(components=[{"type": 17, "components": []}])

    result = _handle(bot, {"type": 2, "data": {"name": "test"}, "id": "1", "token": "t"})
    flags = _body(result)["data"].get("flags", 0)
    assert flags & 32768


# --- send_message / edit_message ---


def _captured_request(bot, coro):
    captured = {}

    def fake_request(method, path, payload=None, files=None):
        captured["payload"] = payload
        captured["files"] = files
        return b"{}"

    with patch.object(bot, "_discord_request", side_effect=fake_request):
        asyncio.run(coro)
    return captured


def _captured_payload(bot, coro):
    return _captured_request(bot, coro)["payload"]


def test_send_message_sets_components_v2_flag():
    bot = Cordless()
    payload = _captured_payload(
        bot, bot.send_message("123", components=[{"type": 17, "components": []}])
    )
    assert payload["flags"] & 32768


def test_send_message_omits_flags_without_uikit_components():
    bot = Cordless()
    payload = _captured_payload(bot, bot.send_message("123", content="hi"))
    assert "flags" not in payload


def test_edit_message_sets_components_v2_flag():
    bot = Cordless()
    payload = _captured_payload(
        bot, bot.edit_message("123", "456", components=[{"type": 17, "components": []}])
    )
    assert payload["flags"] & 32768


def test_send_message_passes_files_through_to_discord_request():
    bot = Cordless()
    files = [("board.png", b"\x89PNG...")]
    captured = _captured_request(bot, bot.send_message("123", content="hi", files=files))
    assert captured["files"] == files


def test_send_message_without_files_passes_none():
    bot = Cordless()
    captured = _captured_request(bot, bot.send_message("123", content="hi"))
    assert captured["files"] is None


def test_edit_message_passes_files_through_to_discord_request():
    bot = Cordless()
    files = [("board.png", b"\x89PNG...")]
    captured = _captured_request(bot, bot.edit_message("123", "456", files=files))
    assert captured["files"] == files


def test_discord_request_attaches_files_metadata_and_builds_multipart():
    bot = Cordless()
    captured = {}

    def fake_urlopen(req):
        captured["headers"] = dict(req.header_items())
        captured["body"] = req.data

        class _Resp:
            def __enter__(self_):
                return self_

            def __exit__(self_, *a):
                return False

            def read(self_):
                return b"{}"

        return _Resp()

    import os

    with (
        patch.dict(os.environ, {"DISCORD_BOT_TOKEN": "tok"}),
        patch("urllib.request.urlopen", side_effect=fake_urlopen),
    ):
        bot._discord_request(
            "POST", "/channels/123/messages", {"content": "hi"}, [("board.png", b"\x89PNG...")]
        )

    assert captured["headers"]["Content-type"].startswith("multipart/form-data; boundary=")
    assert b'name="files[0]"; filename="board.png"' in captured["body"]
    assert b'name="payload_json"' in captured["body"]
    assert b'"attachments": [{"id": 0, "filename": "board.png"}]' in captured["body"]


# --- load_extension ---


def test_load_extension_without_setup_raises():
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "fixtures"))
    try:
        bot = Cordless()
        with pytest.raises(ValueError):
            bot.load_extension("ext_without_setup")
    finally:
        sys.path.pop(0)
        sys.modules.pop("ext_without_setup", None)
