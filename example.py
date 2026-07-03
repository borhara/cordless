"""
Example AWS Lambda handler for a cordless Discord bot.

Deploy this as `lambda_function.py` (handler: `example.handler`) alongside
your dependencies (cordless pulls in pynacl) — e.g. via a zip package or
container image. Set these environment variables on the function:

  DISCORD_PUBLIC_KEY   - from the Discord Developer Portal, General Information
  DISCORD_BOT_TOKEN    - from the Bot page; also used to resolve the application id

Point Discord's "Interactions Endpoint URL" at this function's URL/API Gateway
route. Discord's initial PING to that URL is answered automatically by
cordless once `public_key` is set.

Register the slash commands with Discord using the `cordless` CLI (installed
alongside the package) — do this once after deploying, and again whenever a
command's shape changes:

    cordless register example:bot

The application id is resolved from the bot token automatically. Registering
globally (the default) rolls the commands out to every guild that has
authorized the bot, for every user in it. Pass --guild-id while developing
for instant, guild-scoped updates.
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
