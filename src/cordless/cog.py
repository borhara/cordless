"""
Cog support: group related handlers into a module.

Usage:
    from cordless import Cog

    cog = Cog()

    @cog.command("ping", description="Check the bot is alive")
    async def ping(ctx):
        await ctx.send("Pong!")

    @cog.button("next_page")
    async def next_page(ctx):
        await ctx.edit(...)

    bot.add_cog(cog)
"""


class Cog:
    """Group related handlers. Decorate functions with @cog.command, @cog.button, etc."""

    def __init__(self):
        self._handlers = []

    def command(
        self,
        name,
        description="No description provided.",
        options=None,
        defer=False,
        dm_permission=True,
        default_member_permissions=None,
        nsfw=False,
        ephemeral=False,
        guild_ids=None,
    ):
        def decorator(func):
            self._handlers.append(
                (
                    "command",
                    func,
                    {
                        "name": name,
                        "description": description,
                        "options": options,
                        "defer": defer,
                        "dm_permission": dm_permission,
                        "default_member_permissions": default_member_permissions,
                        "nsfw": nsfw,
                        "ephemeral": ephemeral,
                        "guild_ids": guild_ids,
                    },
                )
            )
            return func

        return decorator

    def button(self, custom_id, defer=False):
        def decorator(func):
            self._handlers.append(("button", func, {"custom_id": custom_id, "defer": defer}))
            return func

        return decorator

    def select(self, custom_id, defer=False):
        def decorator(func):
            self._handlers.append(("select", func, {"custom_id": custom_id, "defer": defer}))
            return func

        return decorator

    def modal(self, custom_id, defer=False):
        def decorator(func):
            self._handlers.append(("modal", func, {"custom_id": custom_id, "defer": defer}))
            return func

        return decorator

    def autocomplete(self, cmd_name, option_name):
        def decorator(func):
            self._handlers.append(
                (
                    "autocomplete",
                    func,
                    {
                        "cmd_name": cmd_name,
                        "option_name": option_name,
                    },
                )
            )
            return func

        return decorator

    def user_command(self, name, dm_permission=True, guild_ids=None):
        def decorator(func):
            self._handlers.append(
                (
                    "user_command",
                    func,
                    {
                        "name": name,
                        "dm_permission": dm_permission,
                        "guild_ids": guild_ids,
                    },
                )
            )
            return func

        return decorator

    def message_command(self, name, dm_permission=True, guild_ids=None):
        def decorator(func):
            self._handlers.append(
                (
                    "message_command",
                    func,
                    {
                        "name": name,
                        "dm_permission": dm_permission,
                        "guild_ids": guild_ids,
                    },
                )
            )
            return func

        return decorator
