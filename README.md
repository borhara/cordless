# Cordless

A serverless Discord interactions framework for AWS Lambda.

Cordless lets you build Discord bots without running a server — just functions, deployed to Lambda. Discord sends HTTP interactions to your endpoint; you return a JSON response. No WebSockets, no gateway, no persistent runtime.

```
Discord Interaction -> API Gateway -> AWS Lambda -> Cordless -> Your handlers -> Response
```

## Install

```bash
pip install cordless
```

## Quickstart

```python
import os
from cordless import Cordless

bot = Cordless(public_key=os.environ["DISCORD_PUBLIC_KEY"])

@bot.command("ping", description="Replies with pong")
async def ping(ctx):
    await ctx.send("pong")

def handler(event, context):
    return bot.handle(event)
```

Deploy `lambda_function.py` with that handler and point Discord's **Interactions Endpoint URL** at your function's URL (via API Gateway or a Lambda function URL).

## Request verification

Every request from Discord is signed with Ed25519. Pass your application's public key (from the Discord Developer Portal, General Information) to `Cordless()` and every request is verified before your handlers run — invalid signatures return 401 and never reach your code.

```python
bot = Cordless(public_key=os.environ["DISCORD_PUBLIC_KEY"])
```

Omitting `public_key` skips verification, which is useful for local testing but should never be done in production.

PING interactions (sent by Discord when you first configure your endpoint URL) are handled automatically.

## Commands

```python
@bot.command("hello", description="Says hello")
async def hello(ctx):
    await ctx.send("Hello!")
```

Commands with options:

```python
@bot.command(
    "echo",
    description="Repeats text back to you",
    options=[
        {"name": "text", "description": "Text to repeat", "type": 3, "required": True},
    ],
)
async def echo(ctx):
    await ctx.send(ctx.options["text"])
```

Options are available on `ctx.options` as a plain dict.

## Buttons

```python
@bot.button("my_button")
async def my_button(ctx):
    await ctx.edit("You clicked it")
```

## Deferred responses

For slow handlers, defer first to acknowledge the interaction within Discord's 3-second window, then follow up separately:

```python
@bot.command("slow", description="Does something slow")
async def slow(ctx):
    await ctx.defer()
    # ... do work ...
```

## Registering commands with Discord

`@bot.command(...)` wires up local dispatch — you also need to register your commands with Discord so they appear in the client. Use the `cordless` CLI after deploying:

```bash
export DISCORD_BOT_TOKEN=...
cordless register app:bot                        # global (up to 1 hour to propagate)
cordless register app:bot --guild-id 123456789   # single guild, instant
```

Point `MODULE:ATTRIBUTE` at wherever your `Cordless()` instance lives.

### No bot token

If your app only ever responds to HTTP interactions and has no bot user, you can authenticate with client credentials instead:

```bash
export DISCORD_CLIENT_ID=...
export DISCORD_CLIENT_SECRET=...
cordless register app:bot
```

If both are set, the bot token takes precedence.

You can also call it from code — useful inside a deploy script:

```python
bot.sync_commands(bot_token=os.environ["DISCORD_BOT_TOKEN"])
bot.sync_commands(bot_token=..., guild_id="123456789")
bot.sync_commands(client_id=..., client_secret=...)
```

## Context reference

| Attribute | Description |
|-----------|-------------|
| `ctx.options` | Command options as a `{name: value}` dict |
| `ctx.user` | The user who triggered the interaction |
| `ctx.guild_id` | Guild ID, or `None` for DMs |
| `ctx.channel_id` | Channel ID |
| `ctx.interaction` | Raw interaction payload |

| Method | Description |
|--------|-------------|
| `await ctx.send(msg)` | Reply with a message |
| `await ctx.edit(msg)` | Edit the original message (for button handlers) |
| `await ctx.defer()` | Acknowledge within 3 seconds, respond later |

## Packaging for Lambda

Cordless has no compiled dependencies — it works on any platform. Just `pip install cordless` into your deployment package and it will run on Lambda without any architecture-specific build steps.
