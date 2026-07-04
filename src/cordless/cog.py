"""
Cog support — split bot commands across multiple classes.

Usage:
    from cordless import Cog, cog_command, cog_button

    class GameCog(Cog):
        @cog_command("ping", description="Check the bot is alive")
        async def ping(self, ctx):
            await ctx.send("Pong!")

        @cog_button("next_page")
        async def next_page(self, ctx):
            await ctx.edit(...)

    bot.add_cog(GameCog())
"""


class Cog:
    """Base class for all cogs. Subclass this and decorate methods."""
    pass


def cog_command(name, description="No description provided.", options=None,
                defer=False, dm_permission=True):
    def decorator(func):
        func._cog_type = "command"
        func._cog_name = name
        func._cog_description = description
        func._cog_options = options or []
        func._cog_defer = defer
        func._cog_dm_permission = dm_permission
        return func
    return decorator


def cog_button(custom_id):
    def decorator(func):
        func._cog_type = "button"
        func._cog_custom_id = custom_id
        return func
    return decorator


def cog_select(custom_id):
    def decorator(func):
        func._cog_type = "select"
        func._cog_custom_id = custom_id
        return func
    return decorator


def cog_modal(custom_id):
    def decorator(func):
        func._cog_type = "modal"
        func._cog_custom_id = custom_id
        return func
    return decorator


def cog_autocomplete(cmd_name, option_name):
    def decorator(func):
        func._cog_type = "autocomplete"
        func._cog_cmd_name = cmd_name
        func._cog_option_name = option_name
        return func
    return decorator


def cog_user_command(name, dm_permission=True):
    def decorator(func):
        func._cog_type = "user_command"
        func._cog_name = name
        func._cog_dm_permission = dm_permission
        return func
    return decorator


def cog_message_command(name, dm_permission=True):
    def decorator(func):
        func._cog_type = "message_command"
        func._cog_name = name
        func._cog_dm_permission = dm_permission
        return func
    return decorator
