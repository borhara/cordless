import json

from cordless.app import Cordless


def test_custom_id_is_exposed_on_button_context():
    bot = Cordless()
    captured = {}

    @bot.button("confirm")
    async def confirm(ctx):
        captured["custom_id"] = ctx.custom_id
        return await ctx.edit("confirmed")

    event = {"body": json.dumps({"type": 3, "data": {"custom_id": "confirm"}})}
    bot.handle(event)

    assert captured["custom_id"] == "confirm"


def test_interaction_id_and_token_are_exposed():
    bot = Cordless()
    captured = {}

    @bot.command("ping")
    async def ping(ctx):
        captured["interaction_id"] = ctx.interaction_id
        captured["token"] = ctx.token
        return await ctx.send("pong")

    payload = {"type": 2, "data": {"name": "ping"}, "id": "123456789", "token": "abc.def.ghi"}
    bot.handle({"body": json.dumps(payload)})

    assert captured["interaction_id"] == "123456789"
    assert captured["token"] == "abc.def.ghi"


def test_send_ephemeral_sets_flags():
    bot = Cordless()

    @bot.command("secret")
    async def secret(ctx):
        return await ctx.send("shh", ephemeral=True)

    event = {"body": json.dumps({"type": 2, "data": {"name": "secret"}})}
    result = bot.handle(event)

    body = json.loads(result["body"])
    assert body["data"]["flags"] == 64
    assert body["data"]["content"] == "shh"


def test_send_without_ephemeral_has_no_flags():
    bot = Cordless()

    @bot.command("public")
    async def public(ctx):
        return await ctx.send("hello")

    event = {"body": json.dumps({"type": 2, "data": {"name": "public"}})}
    result = bot.handle(event)

    body = json.loads(result["body"])
    assert "flags" not in body["data"]
