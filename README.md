# 📡 Cordless

> **A serverless Discord interactions framework for AWS Lambda**

Cordless lets you build Discord bots without running a server — just functions, deployed to Lambda.

* **No WebSockets**
* **No stateful runtime**
* **No gateway sharding**

Just **HTTP → functions → responses**.

## ✨ Why Cordless?

Traditional Discord bots require:
* persistent servers
* WebSocket connections
* intent configuration
* runtime state management

Cordless flips that model:
> Discord sends events → AWS Lambda runs your code → you return a response

## ⚡ Core Idea

```text
Discord Interaction
      │
      ▼
API Gateway
      │
      ▼
 AWS Lambda
      │
      ▼
Cordless Router
      │
      ▼
 Your Functions
      │
      ▼
JSON Response back to Discord
```

## 🚀 Quickstart

### Install

```bash
pip install cordless
```

### Create your first bot

```python
from cordless import Cordless

bot = Cordless()

@bot.command("ping")
async def ping(ctx):
    await ctx.send("pong")
```

### Lambda entry point

```python
import os
from cordless import Cordless

bot = Cordless(public_key=os.environ["DISCORD_PUBLIC_KEY"])

@bot.command("ping")
async def ping(ctx):
    await ctx.send("pong")

def handler(event, context):
    return bot.handle(event)
```

## 🔒 Request verification

Every request Discord sends to your endpoint is signed with Ed25519. Pass your
application's **public key** (from the Discord Developer Portal) to `Cordless()`
and every incoming request is verified before your handlers ever run —
requests with a missing or invalid signature are rejected with `401` and never
reach your code.

```python
bot = Cordless(public_key=os.environ["DISCORD_PUBLIC_KEY"])
```

`PING` interactions, which Discord sends when you first configure your
endpoint URL, are answered automatically.

> Omitting `public_key` skips verification — useful for local testing, but
> **never deploy without it**: anyone who finds your Lambda URL could otherwise
> forge interactions.

## 🗒️ Registering commands with Discord

`@bot.command(...)` only wires up local dispatch — Discord also needs to know
your commands exist so it can show them in the client. Give each command a
description (and options, if it takes arguments), then sync them from a
deploy script (not from inside the Lambda handler, since it makes a network call):

```python
@bot.command(
    "echo",
    description="Repeats what you say",
    options=[
        {"name": "text", "description": "Text to repeat", "type": 3, "required": True},
    ],
)
async def echo(ctx):
    await ctx.send(ctx.options["text"])

# Run once after deploying, e.g. from a deploy script or CI step.
bot.sync_commands(
    application_id=os.environ["DISCORD_APPLICATION_ID"],
    bot_token=os.environ["DISCORD_BOT_TOKEN"],
    guild_id=os.environ.get("DISCORD_DEV_GUILD_ID"),  # omit for global commands
)
```

Pass `guild_id` while developing — guild-scoped commands update instantly.
Global commands (no `guild_id`) can take up to an hour to propagate.

Command arguments show up on `ctx.options` as a plain dict, e.g. `ctx.options["text"]`.

## 🧩 Commands & Interactivity

### Commands

```python
@bot.command("hello")
async def hello(ctx):
    await ctx.send("Hello world!")
```

### Buttons

> **Note:** the `@bot.button(...)` decorator below works today. Sending
> button components (the `components=` argument and `cordless.ui.Button`
> class) is still in active development.

Send a button:

```python
from cordless.ui import Button

@bot.command("ping")
async def ping(ctx):
    await ctx.send(
        "pong",
        components=[
            Button(label="Edit", custom_id="edit_ping")
        ]
    )
```

Handle button clicks:

```python
@bot.button("edit_ping")
async def edit_ping(ctx):
    await ctx.edit("edited")
```

## 🧠 Key concepts

Stateless by design:
* **interaction payload**
* **custom_id routing**
* **Lambda invocation context**

No WebSocket required.

## 📦 Architecture

```text
src/cordless/
├── __init__.py
├── app.py
├── router.py
├── context.py
├── verify.py
├── register.py
├── errors.py
└── response/
    └── responder.py
```

## 💡 Philosophy

Cordless is built around one idea:

> Discord apps should feel like serverless functions, not servers.

