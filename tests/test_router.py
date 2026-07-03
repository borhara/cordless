import json

from cordless.app import Cordless


def test_slash_command_dispatch():
    bot = Cordless()

    @bot.command("ping")
    async def ping(ctx):
        return await ctx.send("pong")

    event = {
        "body": json.dumps({
            "type": 2,
            "data": {"name": "ping"},
        })
    }

    result = bot.handle(event)

    assert result["statusCode"] == 200
    assert json.loads(result["body"])["data"]["content"] == "pong"


def test_button_dispatch():
    bot = Cordless()

    @bot.button("edit_ping")
    async def edit_ping(ctx):
        return await ctx.edit("edited")

    event = {
        "body": json.dumps({
            "type": 3,
            "data": {"custom_id": "edit_ping"},
        })
    }

    result = bot.handle(event)

    assert result["statusCode"] == 200
    assert json.loads(result["body"])["type"] == 7
    assert json.loads(result["body"])["data"]["content"] == "edited"


def test_command_options_are_exposed_on_context():
    bot = Cordless()
    received = {}

    @bot.command("echo")
    async def echo(ctx):
        received.update(ctx.options)
        return await ctx.send(ctx.options["text"])

    event = {
        "body": json.dumps({
            "type": 2,
            "data": {
                "name": "echo",
                "options": [{"name": "text", "type": 3, "value": "hello"}],
            },
        })
    }

    result = bot.handle(event)

    assert received == {"text": "hello"}
    assert json.loads(result["body"])["data"]["content"] == "hello"


def test_unknown_command_returns_400_instead_of_raising():
    bot = Cordless()

    event = {
        "body": json.dumps({
            "type": 2,
            "data": {"name": "missing"},
        })
    }

    result = bot.handle(event)

    assert result["statusCode"] == 400
    assert "missing" in json.loads(result["body"])["error"]


def test_unknown_button_returns_400_instead_of_raising():
    bot = Cordless()

    event = {
        "body": json.dumps({
            "type": 3,
            "data": {"custom_id": "missing"},
        })
    }

    result = bot.handle(event)

    assert result["statusCode"] == 400


def test_unsupported_interaction_type_returns_400():
    bot = Cordless()

    event = {"body": json.dumps({"type": 99})}

    result = bot.handle(event)

    assert result["statusCode"] == 400


def test_handler_that_forgets_to_return_still_responds():
    bot = Cordless()

    @bot.command("ping")
    async def ping(ctx):
        await ctx.send("pong")  # no `return` — a common gotcha

    event = {"body": json.dumps({"type": 2, "data": {"name": "ping"}})}

    result = bot.handle(event)

    assert result["statusCode"] == 200
    assert json.loads(result["body"])["data"]["content"] == "pong"


def test_handler_that_sends_nothing_returns_400():
    bot = Cordless()

    @bot.command("noop")
    async def noop(ctx):
        pass

    event = {"body": json.dumps({"type": 2, "data": {"name": "noop"}})}

    result = bot.handle(event)

    assert result["statusCode"] == 400
