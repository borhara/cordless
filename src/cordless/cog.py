# pyright: strict
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

from collections.abc import Callable
from typing import Any, Literal, TypeVar

_F = TypeVar("_F")


class Cog:
    """Group related handlers. Decorate functions with @cog.command, @cog.button, etc."""

    def __init__(self) -> None:
        self._handlers: list[tuple[str, Any, dict[str, Any]]] = []

    def command(
        self,
        name: str,
        description: str = "No description provided.",
        options: Any = None,
        defer: bool = False,
        dm_permission: bool = True,
        default_member_permissions: Any = None,
        nsfw: bool = False,
        ephemeral: bool = False,
        guild_ids: Any = None,
        user_installable: bool | Literal["only"] = False,
        name_localizations: Any = None,
        description_localizations: Any = None,
        group_description: str | None = None,
        group_name_localizations: Any = None,
        group_description_localizations: Any = None,
        parent_name_localizations: Any = None,
    ) -> Callable[[_F], _F]:
        """Same parameters as `Cordless.command`. Handlers registered here
        take effect once the cog is passed to `bot.add_cog(cog)`."""

        def decorator(func: _F) -> _F:
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
                        "user_installable": user_installable,
                        "name_localizations": name_localizations,
                        "description_localizations": description_localizations,
                        "group_description": group_description,
                        "group_name_localizations": group_name_localizations,
                        "group_description_localizations": group_description_localizations,
                        "parent_name_localizations": parent_name_localizations,
                    },
                )
            )
            return func

        return decorator

    def button(self, custom_id: str, defer: bool = False) -> Callable[[_F], _F]:
        """Same as `Cordless.button`."""

        def decorator(func: _F) -> _F:
            self._handlers.append(("button", func, {"custom_id": custom_id, "defer": defer}))
            return func

        return decorator

    def select(self, custom_id: str, defer: bool = False) -> Callable[[_F], _F]:
        """Same as `Cordless.select`."""

        def decorator(func: _F) -> _F:
            self._handlers.append(("select", func, {"custom_id": custom_id, "defer": defer}))
            return func

        return decorator

    def modal(self, custom_id: str, defer: bool = False) -> Callable[[_F], _F]:
        """Same as `Cordless.modal`."""

        def decorator(func: _F) -> _F:
            self._handlers.append(("modal", func, {"custom_id": custom_id, "defer": defer}))
            return func

        return decorator

    def route(self, method: str, path: str) -> Callable[[_F], _F]:
        """Same as `Cordless.route`."""

        def decorator(func: _F) -> _F:
            self._handlers.append(("route", func, {"method": method, "path": path}))
            return func

        return decorator

    def autocomplete(self, cmd_name: str, option_name: str | None) -> Callable[[_F], _F]:
        """Same as `Cordless.autocomplete`."""

        def decorator(func: _F) -> _F:
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

    def user_command(
        self,
        name: str,
        dm_permission: bool = True,
        default_member_permissions: Any = None,
        nsfw: bool = False,
        guild_ids: Any = None,
        user_installable: bool | Literal["only"] = False,
        name_localizations: Any = None,
    ) -> Callable[[_F], _F]:
        """Same as `Cordless.user_command`."""

        def decorator(func: _F) -> _F:
            self._handlers.append(
                (
                    "user_command",
                    func,
                    {
                        "name": name,
                        "dm_permission": dm_permission,
                        "default_member_permissions": default_member_permissions,
                        "nsfw": nsfw,
                        "guild_ids": guild_ids,
                        "user_installable": user_installable,
                        "name_localizations": name_localizations,
                    },
                )
            )
            return func

        return decorator

    def message_command(
        self,
        name: str,
        dm_permission: bool = True,
        default_member_permissions: Any = None,
        nsfw: bool = False,
        guild_ids: Any = None,
        user_installable: bool | Literal["only"] = False,
        name_localizations: Any = None,
    ) -> Callable[[_F], _F]:
        """Same as `Cordless.message_command`."""

        def decorator(func: _F) -> _F:
            self._handlers.append(
                (
                    "message_command",
                    func,
                    {
                        "name": name,
                        "dm_permission": dm_permission,
                        "default_member_permissions": default_member_permissions,
                        "nsfw": nsfw,
                        "guild_ids": guild_ids,
                        "user_installable": user_installable,
                        "name_localizations": name_localizations,
                    },
                )
            )
            return func

        return decorator
