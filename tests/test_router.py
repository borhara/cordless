import asyncio
from cordless.app import Cordless


def test_ping():
    bot = Cordless()

    @bot.command("ping")
    async def ping(ctx):
        return await ctx.send("pong")

    # fake Discord interaction event
    event = {
        "body": """
        {
            "type": 2,
            "data": {
                "name": "ping"
            }
        }
        """
    }

    result = bot.handle(event)

    # basic sanity check
    assert result["statusCode"] == 200
    assert result["body"]["type"] == 4
    assert result["body"]["data"]["content"] == "pong"
