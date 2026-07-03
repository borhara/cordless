from cordless import Cordless

bot = Cordless()


@bot.command("ping", description="Replies with pong")
async def ping(ctx):
    await ctx.send("pong")
