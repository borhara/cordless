from cordless import Cordless

bot = Cordless()

cron_calls = []


@bot.command("ping", description="Replies with pong")
async def ping(ctx):
    await ctx.send("pong")


@bot.cron("rate(1 hour)")
async def hourly():
    cron_calls.append("hourly")
