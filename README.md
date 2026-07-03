# cordless

A serverless Discord interactions framework for AWS Lambda.

Build Discord bots without running a server — just functions deployed to Lambda. Discord sends HTTP interactions to your endpoint; you return a JSON response. No WebSockets, no gateway, no persistent runtime.

```
Discord → API Gateway → Lambda → cordless → your handlers → response
```

---

## install

```bash
pip install cordless
```

## quickstart

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

Deploy as `lambda_function.py` and point Discord's **Interactions Endpoint URL** at your function's URL (via API Gateway or a Lambda function URL).

---

## request verification

Every request from Discord is signed with Ed25519. Pass your application's public key (from the Developer Portal → General Information) to `Cordless()` and every incoming request is verified automatically — invalid signatures return 401 before your code runs.

```python
bot = Cordless(public_key=os.environ["DISCORD_PUBLIC_KEY"])
```

Omitting `public_key` skips verification. Fine for local testing, never do it in production. PING interactions (sent when you first configure your endpoint) are answered automatically.

---

## commands

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

Options land on `ctx.options` as a plain `{name: value}` dict.

## buttons

```python
@bot.button("confirm")
async def confirm(ctx):
    await ctx.edit(f"Confirmed (button: {ctx.custom_id})")
```

## ephemeral replies

```python
@bot.command("secret", description="Only you can see this")
async def secret(ctx):
    await ctx.send("just for you", ephemeral=True)
```

---

## registering commands

`@bot.command(...)` wires up local dispatch — Discord also needs to know your commands exist. Use the CLI after deploying:

```bash
export DISCORD_BOT_TOKEN=...

cordless register app:bot                        # global — up to 1 hour to propagate
cordless register app:bot --guild-id 123456789   # single guild, instant
```

Pass `MODULE:ATTRIBUTE` pointing at your `Cordless()` instance.

No bot user? Authenticate with client credentials instead:

```bash
export DISCORD_CLIENT_ID=...
export DISCORD_CLIENT_SECRET=...
cordless register app:bot
```

Or call it from code:

```python
bot.sync_commands(bot_token=os.environ["DISCORD_BOT_TOKEN"])
bot.sync_commands(client_id=..., client_secret=..., guild_id="123456789")
```

---

## deploying the layer

cordless has no compiled dependencies. Package it as a Lambda layer and attach it to your function in one step:

```bash
cordless upload --function my-discord-bot
cordless upload --function my-discord-bot --region eu-west-1
```

Uses the AWS CLI under the hood — your existing credentials, profile, and region config all apply.

---

## context reference

**Attributes**

| | |
|---|---|
| `ctx.options` | Command options as `{name: value}` |
| `ctx.custom_id` | Custom ID of the button that was clicked |
| `ctx.user` | User who triggered the interaction |
| `ctx.guild_id` | Guild ID, or `None` in DMs |
| `ctx.channel_id` | Channel ID |
| `ctx.interaction_id` | Interaction ID |
| `ctx.token` | Interaction token |
| `ctx.interaction` | Raw interaction payload |

**Methods**

| | |
|---|---|
| `await ctx.send(msg, *, ephemeral=False)` | Reply with a message |
| `await ctx.edit(msg)` | Edit the original message (button handlers) |
| `await ctx.defer()` | Acknowledge within 3 s, respond later |
