# 📡 Cordless

**A serverless Discord interactions framework for AWS Lambda**

Cordless lets you build Discord bots without running a server — just functions, deployed to Lambda.

No WebSockets. No stateful runtime. No gateway sharding.

Just HTTP → functions → responses.

---

# ✨ Why Cordless?

Traditional Discord bots require:

- persistent servers
- WebSocket connections
- intent configuration
- runtime state management

Cordless flips that model:

> Discord sends events → AWS Lambda runs your code → you return a response

---

# ⚡ Core idea

Discord Interaction
→ API Gateway
→ AWS Lambda
→ Cordless Router
→ Your Functions
→ JSON Response back to Discord

---

# 🚀 Quickstart

## Install

```bash
pip install cordless
```

---

## Create your first bot

```python
from cordless import Cordless

bot = Cordless()

@bot.command("ping")
async def ping(ctx):
    await ctx.send("pong")
```

---

## Lambda entry point

```python
from cordless import Cordless

bot = Cordless()

@bot.command("ping")
async def ping(ctx):
    await ctx.send("pong")

def handler(event, context):
    return bot.handle(event)
```

---

# 🧩 Commands

```python
@bot.command("hello")
async def hello(ctx):
    await ctx.send("Hello world!")
```

---

# 🔘 Buttons

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

---

Handle button clicks:

```python
@bot.button("edit_ping")
async def edit_ping(ctx):
    await ctx.edit("edited")
```

---

# 🧠 Key concepts

Stateless by design:
- interaction payload
- custom_id routing
- Lambda invocation context

No WebSocket required.

---

# 📦 Architecture

```
cordless
├── app.py
├── router.py
├── context.py
├── response/
└── adapters/
```
---

# 💡 Philosophy

Cordless is built around one idea:

> Discord apps should feel like serverless functions, not servers.
