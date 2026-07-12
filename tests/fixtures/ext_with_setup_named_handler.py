"""Fixture: a Cog whose command handler happens to be named `setup`, colliding
with the manual setup(bot) hook's name. Regression fixture for the bug where
load_extension mistook this coroutine for the hook and never registered the Cog."""

from cordless import Cog

cog = Cog()


@cog.command("setup", description="Configure things")
async def setup(ctx):
    await ctx.send("configured")
