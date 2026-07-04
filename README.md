# cordless

Serverless Discord bots for AWS Lambda — no gateway, no WebSockets, just functions.

```
Discord → API Gateway → Lambda → cordless → your handlers → response
```

---

## install

```bash
pip install cordless
```

For deploying to Lambda, also install the `deploy` extra which pulls in `boto3`:

```bash
pip install "cordless[deploy]"
```

---

## quickstart

Create `lambda_function.py`, deploy it to Lambda, and point Discord's **Interactions Endpoint URL** at your function URL.

```python
import os
from cordless import Cordless

bot = Cordless(public_key=os.environ["DISCORD_PUBLIC_KEY"])

@bot.command("ping", description="Replies with pong")
async def ping(ctx):
    await ctx.send("pong")

handler = bot.handler()
```

Your **public key** is in the Discord Developer Portal → General Information. Every incoming request is verified automatically — invalid signatures return 401 before your code runs. PING interactions (sent when you first save your endpoint URL) are answered automatically.

> Omit `public_key` to skip verification. Fine for local testing; never do it in production.

---

## commands

### options

Use the `option()` helper to build option dicts. Type defaults to `string`.

```python
from cordless import Cordless, option

@bot.command("echo", description="Repeats text back", options=[
    option("text", "What to echo", required=True),
])
async def echo(ctx):
    await ctx.send(ctx.options["text"])
```

Available types: `string`, `integer`, `number`, `boolean`, `user`, `channel`, `role`, `attachment`. Extra kwargs map directly to Discord option fields: `required`, `autocomplete`, `choices`, `min_value`, `max_value`, `min_length`, `max_length`.

### subcommands

Use `parent/sub` and `parent/group/sub` paths — cordless builds the Discord subcommand tree automatically.

```python
@bot.command("info/bot", description="About this bot")
async def info_bot(ctx): ...

@bot.command("info/server", description="About this server")
async def info_server(ctx): ...
```

### autocomplete

Mark the option with `autocomplete=True`, then register a handler with `@bot.autocomplete`. The focused option's current value is on `ctx.focused_value`.

```python
@bot.command("color", description="Look up a colour", options=[
    option("name", "Colour name", autocomplete=True),
])
async def color_cmd(ctx):
    await ctx.send(f"Colour: {ctx.options['name']}")

@bot.autocomplete("color", "name")
async def color_ac(ctx):
    query = (ctx.focused_value or "").lower()
    matches = [{"name": c.title(), "value": c} for c in COLORS if c.startswith(query)]
    await ctx.respond_autocomplete(matches[:25])
```

### deferred replies

Discord requires a response within 3 seconds. Use `defer=True` for slow operations — cordless ACKs Discord immediately, invokes a second Lambda (the *worker*) in the background, and the worker calls `ctx.send()` when it's done.

```python
@bot.command("report", description="Generate a report", defer=True)
async def report(ctx):
    data = await build_report()       # can take as long as needed
    await ctx.send(f"Report ready: {data}")
```

In `lambda_function.py`, expose the worker handler:

```python
from cordless.worker import make_worker_handler

worker_handler = make_worker_handler(bot)
```

Set `defer_worker` in `cordless.toml` so `cordless deploy` creates the worker and wires the invoke permission automatically.

### deferred buttons

Buttons can also be deferred — useful when the response takes time. Use `defer=True` on `@bot.button()` (or `@cog_button()`). cordless responds with a loading state immediately and lets the worker update the message.

```python
@bot.button("slow_action", defer=True)
async def slow_action(ctx):
    result = await do_work()
    await ctx.edit(f"Done: {result}")
```

---

## context menu commands

Context menu commands appear when a user right-clicks a user or message → **Apps**. They have no slash-command syntax — just a name.

```python
@bot.user_command("Inspect User")
async def inspect(ctx):
    user = ctx.target_user           # the right-clicked user
    await ctx.send(f"**{user['username']}** — {user['id']}", ephemeral=True)

@bot.message_command("Bookmark")
async def bookmark(ctx):
    msg = ctx.target_message         # the right-clicked message
    await ctx.send(f"Saved: {msg['content'][:100]}", ephemeral=True)
```

| attribute | description |
|---|---|
| `ctx.target_user` | Right-clicked user object (user commands) |
| `ctx.target_member` | Right-clicked guild member (user commands, guild only) |
| `ctx.target_message` | Right-clicked message object (message commands) |

---

## buttons

```python
from cordless import ActionRow, Button, ButtonStyle

@bot.command("vote", description="Start a vote")
async def vote(ctx):
    await ctx.send("Cast your vote:", components=[
        ActionRow(
            Button("Yes", custom_id="vote_yes", style=ButtonStyle.SUCCESS),
            Button("No",  custom_id="vote_no",  style=ButtonStyle.DANGER),
        )
    ])

@bot.button("vote_yes")
async def on_yes(ctx):
    await ctx.edit("You voted yes.")
```

`ctx.edit()` updates the original message in-place. `ButtonStyle` values: `PRIMARY`, `SECONDARY`, `SUCCESS`, `DANGER`, `LINK`. Link buttons take a `url=` instead of `custom_id=`.

---

## select menus

```python
from cordless import ActionRow, StringSelect, SelectOption

@bot.command("pick", description="Pick a colour")
async def pick(ctx):
    await ctx.send("Choose:", components=[
        ActionRow(StringSelect("colour_select", [
            SelectOption("Red",   "red"),
            SelectOption("Green", "green"),
            SelectOption("Blue",  "blue"),
        ], placeholder="Pick one"))
    ])

@bot.select("colour_select")
async def on_colour(ctx):
    await ctx.edit(f"You picked {ctx.values[0]}")
```

Selected values are on `ctx.values` as a list. Also available: `UserSelect`, `RoleSelect`, `MentionableSelect`, `ChannelSelect`.

---

## modals

```python
from cordless import Modal, TextInput, TextInputStyle

@bot.command("feedback", description="Leave feedback")
async def feedback_cmd(ctx):
    await ctx.send_modal(Modal(
        "feedback_modal", "Leave Feedback",
        TextInput("subject", "Subject", style=TextInputStyle.SHORT),
        TextInput("body", "Message", style=TextInputStyle.PARAGRAPH, required=False),
    ))

@bot.modal("feedback_modal")
async def on_feedback(ctx):
    subject = ctx.modal_values["subject"]
    body    = ctx.modal_values.get("body", "")
    await ctx.send(f"**{subject}**\n{body}", ephemeral=True)
```

Submission values land in `ctx.modal_values` as a `{custom_id: value}` dict.

---

## embeds

```python
from cordless import Embed

embed = (
    Embed(title="Status", description="All systems operational", color=0x57AB5A)
    .set_author("cordless", icon_url=icon_url)
    .set_footer("Last checked just now")
    .add_field("Uptime", "99.9%", inline=True)
    .add_field("Region", "eu-west-1", inline=True)
)

await ctx.send(embeds=[embed])
```

---

## components v2

Discord's UI Kit — richer layouts with `Container`, `Section`, `TextDisplay`, `Thumbnail`, and `Separator`. The `32768` flag is set automatically when any of these appear in your response.

```python
from cordless import Container, Section, TextDisplay, Thumbnail, Separator

await ctx.send(components=[
    Container(
        Section(
            TextDisplay(f"**{user['username']}**\n-# joined {joined_at}"),
            accessory=Thumbnail(avatar_url(user)),
        ),
        Separator(divider=True, spacing=1),
        TextDisplay(f"-# User ID: {user['id']}"),
        accent_color=0x5865F2,
    )
])
```

`Section` can take a `Button` as its `accessory` instead of a `Thumbnail`. `-#` in text produces subtext (smaller, muted).

---

## error handling

Register a single global handler with `@bot.error`. It catches any unhandled exception from any command, button, modal, or select handler.

```python
@bot.error
async def on_error(ctx, exc):
    await ctx.send(f"Something went wrong: {exc}", ephemeral=True)
```

---

## guards

Guards run before a handler. Raise `PermissionDeniedError` to block it — the error propagates to your `@bot.error` handler.

```python
from cordless.errors import PermissionDeniedError

def admin_only(ctx):
    if not is_admin(ctx.user):
        raise PermissionDeniedError("Admins only.")

@bot.guard(admin_only)
@bot.command("ban", description="Ban a user")
async def ban(ctx): ...
```

---

## deploying

### cordless deploy

Packages your source directory, creates (or updates) the Lambda function and a cordless layer, sets up API Gateway, and returns the endpoint URL.

```bash
cordless deploy --function my-bot --source .

# with a deferred worker Lambda
cordless deploy --function my-bot --defer-worker my-bot-worker
```

### cordless register

Pushes your bot's registered commands to Discord. Run this once after deploying, and again whenever you add or change commands.

```bash
cordless register lambda_function:bot --token $DISCORD_BOT_TOKEN

# guild-specific (instant — no propagation delay)
cordless register lambda_function:bot --guild-id 123456789

# without a bot user, via client credentials
cordless register lambda_function:bot \
  --client-id $DISCORD_CLIENT_ID \
  --client-secret $DISCORD_CLIENT_SECRET
```

Pass `MODULE:ATTRIBUTE` pointing at your `Cordless()` instance. Environment variables `DISCORD_BOT_TOKEN`, `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, and `DISCORD_GUILD_ID` are read automatically if set.

### cordless logs

Tail CloudWatch logs for your deployed function.

```bash
cordless logs --function my-bot
cordless logs --function my-bot --follow
cordless logs --function my-bot --since 30    # last 30 minutes
```

### cordless.toml

Put a `cordless.toml` in your project root to avoid passing flags on every deploy.

```toml
[deploy]
function      = "my-bot"
region        = "eu-west-1"
runtime       = "python3.12"
handler       = "lambda_function.handler"
defer_worker  = "my-bot-worker"
defer_memory  = 256        # MB — increase if your worker does heavy work (e.g. image generation)
packages      = ["pillow"] # extra pip packages to bundle into the zip

[deploy.env]
DISCORD_PUBLIC_KEY = "abc123..."
```

> AWS credentials are read from the standard chain — environment variables, `~/.aws/credentials`, or an instance role. No credentials are ever prompted for on the terminal.

---

## context reference

Every handler receives a `ctx` object.

### attributes

| attribute | description |
|---|---|
| `ctx.user` | User who triggered the interaction |
| `ctx.guild_id` | Guild ID, or `None` in DMs |
| `ctx.channel_id` | Channel ID |
| `ctx.options` | Command options as `{name: value}` |
| `ctx.custom_id` | Custom ID of the button or select that fired |
| `ctx.values` | Selected values from a select menu |
| `ctx.modal_values` | Modal submission as `{custom_id: value}` |
| `ctx.focused_value` | Current value of the focused autocomplete option |
| `ctx.target_user` | Right-clicked user (user context menu commands) |
| `ctx.target_member` | Right-clicked guild member (user context menu, guild only) |
| `ctx.target_message` | Right-clicked message (message context menu commands) |
| `ctx.interaction_id` | Interaction ID |
| `ctx.token` | Interaction token |
| `ctx.interaction` | Raw interaction payload |

### methods

| method | description |
|---|---|
| `await ctx.send(msg, *, content, ephemeral, embeds, components)` | Reply with a new message |
| `await ctx.edit(msg, *, content, embeds, components)` | Edit the original message (buttons / selects) |
| `await ctx.defer()` | ACK within 3 s; respond later via the worker |
| `await ctx.send_modal(modal)` | Open a modal form |
| `await ctx.respond_autocomplete(choices)` | Return autocomplete suggestions |
| `await ctx.followup(msg, …)` | Send a followup message (deferred worker, post-ACK) |
