"""
Example AWS Lambda handler for a cordless Discord bot.

Deploy this as `lambda_function.py` (handler: `example.handler`) alongside
your dependencies (cordless pulls in pynacl) — e.g. via a zip package or
container image. Set these environment variables on the function:

  DISCORD_PUBLIC_KEY   - from the Discord Developer Portal, General Information
  DISCORD_APPLICATION_ID
  DISCORD_BOT_TOKEN

Point Discord's "Interactions Endpoint URL" at this function's URL/API Gateway
route. Discord's initial PING to that URL is answered automatically by
cordless once `public_key` is set.

Run `python example.py` locally (with DISCORD_APPLICATION_ID/DISCORD_BOT_TOKEN
set) to register the slash commands with Discord — do this once after
deploying, and again whenever a command's shape changes.
"""

import os

from cordless import Cordless

bot = Cordless(public_key=os.environ["DISCORD_PUBLIC_KEY"])


@bot.command("ping", description="Replies with pong")
async def ping(ctx):
    await ctx.send("pong")


@bot.command(
    "echo",
    description="Repeats text back to you",
    options=[
        {"name": "text", "description": "Text to repeat", "type": 3, "required": True},
    ],
)
async def echo(ctx):
    await ctx.send(ctx.options["text"])


@bot.button("edit_ping")
async def edit_ping(ctx):
    await ctx.edit("edited")


def handler(event, context):
    return bot.handle(event)


if __name__ == "__main__":
    bot.sync_commands(
        application_id=os.environ["DISCORD_APPLICATION_ID"],
        bot_token=os.environ["DISCORD_BOT_TOKEN"],
        guild_id=os.environ.get("DISCORD_DEV_GUILD_ID"),
    )
    print("Commands synced.")
