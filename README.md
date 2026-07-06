# cordless

Build Discord bots that run on AWS Lambda. Discord sends a request, Lambda wakes up, your handler runs, Lambda goes back to sleep. No server to keep alive, no idle cost.

```python
from cordless import Cordless

bot = Cordless()

@bot.command("ping", description="Say hello")
async def ping(ctx):
    await ctx.send("pong")

handler = bot.handler()
```

```bash
cordless deploy --register
# → https://abc123.execute-api.eu-west-2.amazonaws.com/
```

---

## Why cordless?

Most Discord bots run as long-lived processes, a VPS or container that sits idle 99% of the time, waiting for someone to type a command. You pay for uptime whether your bot is busy or not.

cordless flips this. Your bot is a Lambda function: it only runs when Discord sends an interaction, takes milliseconds to respond, and costs essentially nothing to host. One command provisions everything on AWS: IAM role, Lambda function, API Gateway endpoint and registers your commands with Discord.

- **No server:** no EC2, no containers, no uptime monitoring, no SSH
- **No idle cost:** Lambda charges per invocation, not per hour
- **One command to ship:** `cordless deploy` handles all the AWS wiring
- **Local dev:** `cordless dev` runs your bot on localhost with a live public tunnel
- **Slow commans:** deferred interactions hand off to a worker Lambda so Discord's 3-second limit is never a problem

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
# → https://abc123.execute-api.eu-west-2.amazonaws.com/
```

Paste the URL into your Discord app's **Interactions Endpoint URL** and your bot is live.

---

## Documentation

Full docs at **[cordless.dev](https://cordless.dev)** — commands, options, buttons, modals, deferred interactions, Components v2, scheduled handlers, and the full deploy reference.


> Please note that this is a work in progress, I have found genuine interest in serverless development and wanted an easy way to provision AWS.