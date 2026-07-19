# cordless

[![PyPI](https://img.shields.io/pypi/v/cordless)](https://pypi.org/project/cordless/)
[![Tests](https://github.com/borhara/cordless/actions/workflows/test.yml/badge.svg)](https://github.com/borhara/cordless/actions/workflows/test.yml)
[![License](https://img.shields.io/github/license/borhara/cordless)](https://github.com/borhara/cordless/blob/main/LICENSE)
[![Python versions](https://img.shields.io/pypi/pyversions/cordless)](https://pypi.org/project/cordless/)

Build Discord bots that run on AWS Lambda. Discord sends a request, Lambda wakes up, your handler runs, Lambda goes back to sleep. No server to keep alive, no idle cost.

```python
import os
from cordless import Cordless

bot = Cordless(public_key=os.environ["DISCORD_PUBLIC_KEY"])

@bot.command("ping", description="Say hello")
async def ping(ctx):
    await ctx.send("pong")

handler = bot.handler()
```

```bash
cordless deploy --register
# → https://abc123.lambda-url.us-east-1.on.aws/
```

---

## Why cordless?

Most Discord bots run as long-lived processes, a VPS or container that sits idle 99% of the time, waiting for someone to type a command. You pay for uptime whether your bot is busy or not.

cordless flips this. Your bot is a Lambda function: it only runs when Discord sends an interaction, takes milliseconds to respond, and costs essentially nothing to host. One command provisions everything on AWS: IAM role, Lambda function, public endpoint (a direct Function URL by default, or API Gateway if you want a custom domain) and registers your commands with Discord.

- **No server:** no EC2, no containers, no uptime monitoring, no SSH
- **No idle cost:** Lambda charges per invocation, not per hour
- **One command to ship:** `cordless deploy` handles all the AWS wiring
- **Local dev:** `cordless dev` runs your bot on localhost with a live public tunnel
- **Slow commands:** deferred interactions hand off to a worker Lambda so Discord's 3-second limit is never a problem

---

## Install

```bash
uv add "cordless[deploy]"   # (we should ALL be using uv)
```

---

## Quickstart

**Scaffold** a new bot:

```bash
mkdir my-bot && cd my-bot
cordless init my-bot
```

This creates `lambda_function.py`, `cordless.toml`, and `.env.example`.

**Configure** your credentials in `.env`:

```
DISCORD_PUBLIC_KEY=your_public_key
DISCORD_BOT_TOKEN=your_bot_token
```

**Test locally** — `cordless dev` runs your bot with hot reload. With [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) installed it opens a public tunnel so Discord can reach it directly.

```bash
cordless dev
```

**Deploy** to AWS and register your commands with Discord:

```bash
cordless deploy --register
# → https://abc123.lambda-url.us-east-1.on.aws/
```

Paste the URL into your Discord app's **Interactions Endpoint URL** and your bot is live.

---

## Documentation

Full docs at **[cordless.dev](https://cordless.dev)** — commands, options, buttons, modals, deferred interactions, Components v2, scheduled handlers, and the full deploy reference.


> Please note that this is a work in progress, I have found genuine interest in serverless development and wanted an easy way to provision AWS.