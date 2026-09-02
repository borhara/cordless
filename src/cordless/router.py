import asyncio
import inspect
from typing import Any, Literal, cast

from .errors import (
    CordlessError,
    NoResponseError,
    UnknownButtonError,
    UnknownCommandError,
    UnknownComponentError,
    UnknownModalError,
    UnsupportedInteractionError,
)
from .routes import compile_pattern, match_pattern, patterns_conflict, specificity
from .routes import normalize as _normalize_route

PING = 1
APPLICATION_COMMAND = 2
MESSAGE_COMPONENT = 3
APPLICATION_COMMAND_AUTOCOMPLETE = 4
MODAL_SUBMIT = 5

_SUB_COMMAND = 1
_SUB_COMMAND_GROUP = 2

# Discord's integration_types/contexts values, for user_installable=True.
# Not exposed publicly: user_installable is the one knob that matters (can
# people run this from a DM/group chat with someone other than the bot,
# after installing it to their own account), so there's no reason to make
# callers juggle these two raw arrays themselves.
_INTEGRATION_TYPE_GUILD_INSTALL = 0
_INTEGRATION_TYPE_USER_INSTALL = 1
_CONTEXT_GUILD = 0
_CONTEXT_BOT_DM = 1
_CONTEXT_PRIVATE_CHANNEL = 2


class Router:
    def __init__(self) -> None:
        self.commands: dict[str, dict[str, Any]] = {}
        self.buttons: dict[str, Any] = {}
        self.selects: dict[str, Any] = {}
        self.modals: dict[str, Any] = {}
        self.autocompletes: dict[tuple[str, str | None], Any] = {}  # (cmd_key, option_name) → handler
        self.routes: list[dict[str, Any]] = []  # raw HTTP routes: {method, path, pattern, handler}
        self._error_handler: Any = None

    def register_command(
        self,
        name: str,
        handler: Any,
        description: str | None = "No description provided.",
        options: Any = None,
        dm_permission: bool = True,
        cmd_type: int = 1,
        default_member_permissions: Any = None,
        nsfw: bool = False,
        guild_ids: Any = None,
        user_installable: bool | Literal["only"] = False,
        name_localizations: Any = None,
        description_localizations: Any = None,
        group_description: str | None = None,
        group_name_localizations: Any = None,
        group_description_localizations: Any = None,
        parent_name_localizations: Any = None,
    ) -> None:
        if cmd_type == 1:
            for existing, meta in self.commands.items():
                if meta.get("cmd_type", 1) != 1:
                    continue
                if existing.startswith(f"{name}/") or name.startswith(f"{existing}/"):
                    parent, _child = sorted((name, existing), key=len)
                    raise ValueError(
                        f"Command {name!r} conflicts with {existing!r}: the parent "
                        f"{parent!r} is created automatically from subcommand paths, "
                        "so it must not be registered as a command itself"
                    )
        self.commands[name] = {
            "handler": handler,
            "description": description,
            "options": options or [],
            "dm_permission": dm_permission,
            "cmd_type": cmd_type,
            "params": list(inspect.signature(handler).parameters)[1:],
            "default_member_permissions": default_member_permissions,
            "nsfw": nsfw,
            "guild_ids": list(guild_ids) if guild_ids else None,
            "user_installable": user_installable,
            "name_localizations": name_localizations,
            "description_localizations": description_localizations,
            "group_description": group_description,
            "group_name_localizations": group_name_localizations,
            "group_description_localizations": group_description_localizations,
            "parent_name_localizations": parent_name_localizations,
        }

    def register_button(self, custom_id: str, handler: Any) -> None:
        self.buttons[custom_id] = handler

    def register_select(self, custom_id: str, handler: Any) -> None:
        self.selects[custom_id] = handler

    def register_modal(self, custom_id: str, handler: Any) -> None:
        self.modals[custom_id] = handler

    def register_autocomplete(self, cmd_name: str, option_name: str | None, handler: Any) -> None:
        self.autocompletes[(cmd_name, option_name)] = handler

    def register_route(self, method: str, path: str, handler: Any) -> None:
        """Register a raw HTTP handler. Rejects a route that would match the
        same paths as one already registered."""
        method, norm = _normalize_route(method, path)
        pattern = compile_pattern(norm)
        for existing in self.routes:
            if existing["method"] == method and patterns_conflict(existing["pattern"], pattern):
                raise ValueError(
                    f"Route {method} {path!r} conflicts with the registered {existing['method']} {existing['path']!r}"
                )
        self.routes.append({"method": method, "path": norm, "pattern": pattern, "handler": handler})
        self.routes.sort(key=lambda route: specificity(route["pattern"]), reverse=True)

    def match_route(self, method: str, path: str) -> tuple[Any, dict[str, str]] | None:
        """Return `(handler, path_params)` for the first route matching
        `method` and `path`, or `None`."""
        method = method.upper()
        for route in self.routes:
            if route["method"] != method:
                continue
            params = match_pattern(route["pattern"], path)
            if params is not None:
                return route["handler"], params
        return None

    def route_defs(self) -> list[tuple[str, str]]:
        """Sorted `(method, path)` pairs with `{name}` tokens intact, for
        `cordless deploy` to sync onto the API."""
        return sorted((route["method"], route["path"]) for route in self.routes)

    def register_error_handler(self, handler: Any) -> None:
        self._error_handler = handler

    def command_definitions(self) -> list[dict[str, Any]]:
        """Every registered command, regardless of guild scoping: the full
        set deploy tooling pushes to one guild for instant dev updates."""
        return self._definitions(self.commands)

    def scoped_command_definitions(self, guild_id: str | None) -> list[dict[str, Any]]:
        """Only commands registered for this scope (None = global), see
        register_command's guild_ids. A command with guild_ids=[a, b] shows
        up in both scoped_command_definitions(a) and (b)."""
        if guild_id is None:
            scoped = {k: m for k, m in self.commands.items() if not m.get("guild_ids")}
        else:
            scoped = {k: m for k, m in self.commands.items() if guild_id in (m.get("guild_ids") or [])}
        return self._definitions(scoped)

    def guild_ids(self) -> list[str]:
        """Every distinct guild referenced by any command's guild_ids."""
        return sorted({gid for m in self.commands.values() for gid in cast("list[Any]", m.get("guild_ids") or [])})

    @staticmethod
    def _apply_installability(cmd: dict[str, Any], user_installable: Any) -> bool:
        """contexts/integration_types replace dm_permission for the modern
        install model, so when this is set, dm_permission is left off
        entirely rather than sent alongside a field that supersedes it.
        `user_installable=True` allows both guild and user install;
        `user_installable="only"` drops the guild install, so the command
        never shows up as a guild-wide command, only for users who've
        installed it to their own account."""
        if not user_installable:
            return False
        if user_installable == "only":
            cmd["integration_types"] = [_INTEGRATION_TYPE_USER_INSTALL]
        else:
            cmd["integration_types"] = [_INTEGRATION_TYPE_GUILD_INSTALL, _INTEGRATION_TYPE_USER_INSTALL]
        cmd["contexts"] = [_CONTEXT_GUILD, _CONTEXT_BOT_DM, _CONTEXT_PRIVATE_CHANNEL]
        return True

    def _definitions(self, commands: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        flat: dict[str, Any] = {}  # name → meta
        subs: dict[str, dict[str, Any]] = {}  # top-level name → {path → meta}

        for key, meta in commands.items():
            # Context menu commands (type 2/3) never participate in subcommand grouping
            if meta.get("cmd_type", 1) in (2, 3):
                flat[key] = meta
                continue
            parts = key.split("/")
            if len(parts) == 1:
                flat[key] = meta
            else:
                top = parts[0]
                subs.setdefault(top, {})[key] = meta

        result: list[dict[str, Any]] = []

        for name, meta in flat.items():
            cmd_type = meta.get("cmd_type", 1)
            if cmd_type in (2, 3):
                # Context menu commands: no description, no options
                cmd: dict[str, Any] = {"name": name, "type": cmd_type}
                if not self._apply_installability(cmd, meta.get("user_installable")) and not meta.get(
                    "dm_permission", True
                ):
                    cmd["dm_permission"] = False
                if meta.get("default_member_permissions") is not None:
                    cmd["default_member_permissions"] = str(int(meta["default_member_permissions"]))
                if meta.get("nsfw"):
                    cmd["nsfw"] = True
                if meta.get("name_localizations"):
                    cmd["name_localizations"] = meta["name_localizations"]
                result.append(cmd)
                continue
            cmd: dict[str, Any] = {
                "name": name,
                "description": meta["description"],
                "type": 1,
                "options": meta["options"],
            }
            if not self._apply_installability(cmd, meta.get("user_installable")) and not meta.get(
                "dm_permission", True
            ):
                cmd["dm_permission"] = False
            if meta.get("default_member_permissions") is not None:
                cmd["default_member_permissions"] = str(int(meta["default_member_permissions"]))
            if meta.get("nsfw"):
                cmd["nsfw"] = True
            if meta.get("name_localizations"):
                cmd["name_localizations"] = meta["name_localizations"]
            if meta.get("description_localizations"):
                cmd["description_localizations"] = meta["description_localizations"]
            result.append(cmd)

        for top, entries in subs.items():
            options: list[dict[str, Any]] = []
            for path, meta in entries.items():
                parts = path.split("/")
                if len(parts) == 2:
                    # parent/sub
                    sub: dict[str, Any] = {
                        "name": parts[1],
                        "description": meta["description"],
                        "type": _SUB_COMMAND,
                        "options": meta["options"],
                    }
                    if meta.get("name_localizations"):
                        sub["name_localizations"] = meta["name_localizations"]
                    if meta.get("description_localizations"):
                        sub["description_localizations"] = meta["description_localizations"]
                    options.append(sub)
                elif len(parts) == 3:
                    # parent/group/sub, grouped by group name
                    group_name = parts[1]
                    sub_name = parts[2]
                    group: dict[str, Any] | None = next((o for o in options if o["name"] == group_name), None)
                    if group is None:
                        group = {
                            "name": group_name,
                            "description": meta.get("group_description") or "No description provided.",
                            "type": _SUB_COMMAND_GROUP,
                            "options": [],
                        }
                        if meta.get("group_name_localizations"):
                            group["name_localizations"] = meta["group_name_localizations"]
                        if meta.get("group_description_localizations"):
                            group["description_localizations"] = meta["group_description_localizations"]
                        options.append(group)
                    sub = {
                        "name": sub_name,
                        "description": meta["description"],
                        "type": _SUB_COMMAND,
                        "options": meta["options"],
                    }
                    if meta.get("name_localizations"):
                        sub["name_localizations"] = meta["name_localizations"]
                    if meta.get("description_localizations"):
                        sub["description_localizations"] = meta["description_localizations"]
                    group["options"].append(sub)

            first_meta: Any = next(iter(entries.values()))
            cmd = {
                "name": top,
                "description": first_meta["description"],
                "type": 1,
                "options": options,
            }
            if first_meta.get("description_localizations"):
                cmd["description_localizations"] = first_meta["description_localizations"]
            if first_meta.get("parent_name_localizations"):
                cmd["name_localizations"] = first_meta["parent_name_localizations"]
            installables: list[Any] = [m.get("user_installable") for m in entries.values()]
            # a subcommand wanting both guild and user install wins over one
            # wanting user-install "only", since they share one parent command
            combined: Any
            if any(v is True for v in installables):
                combined = True
            elif any(v == "only" for v in installables):
                combined = "only"
            else:
                combined = False
            installable = self._apply_installability(cmd, combined)
            if not installable and any(not m.get("dm_permission", True) for m in entries.values()):
                cmd["dm_permission"] = False
            # Discord only accepts these at the top level, so combine across
            # subcommands: union the permission bits (most restrictive wins)
            perms = 0
            for m in entries.values():
                if m.get("default_member_permissions") is not None:
                    perms |= int(m["default_member_permissions"])
            if perms:
                cmd["default_member_permissions"] = str(perms)
            if any(m.get("nsfw") for m in entries.values()):
                cmd["nsfw"] = True
            result.append(cmd)

        return result

    async def dispatch(self, interaction: Any, ctx: Any) -> Any:
        try:
            return await self._dispatch_inner(interaction, ctx)
        except Exception as exc:
            if self._error_handler is not None:
                result = self._error_handler(ctx, exc)
                if asyncio.iscoroutine(result):
                    result = await result
                response = result if result is not None else ctx.response
                if response is not None:
                    # a shared error handler that falls back to ctx.send() would
                    # otherwise hand Discord a message-type response for an
                    # autocomplete interaction, which it rejects outright
                    if interaction["type"] == APPLICATION_COMMAND_AUTOCOMPLETE and ctx._response_kind != "autocomplete":
                        return await ctx.respond_autocomplete([])
                    return response
            raise

    async def _dispatch_inner(self, interaction: Any, ctx: Any) -> Any:
        itype = interaction["type"]

        if itype == APPLICATION_COMMAND:
            key, leaf_options = _resolve_command_key(interaction["data"])
            entry = self.commands.get(key)
            if not entry:
                raise UnknownCommandError(f"Unknown command: {key}")
            if leaf_options is not None:
                ctx.options = {opt["name"]: opt["value"] for opt in leaf_options if "value" in opt}
            handler = entry["handler"]
            if getattr(handler, "_defer", False) and not ctx._worker_mode:
                ephemeral = getattr(handler, "_defer_ephemeral", False)
                return await _defer_to_worker(ctx, interaction, ctx.defer, ephemeral=ephemeral)
            return await _invoke(handler, ctx, f"Command '{key}'", params=entry["params"])

        if itype == MESSAGE_COMPONENT:
            cid = interaction["data"]["custom_id"]
            component_type = interaction["data"].get("component_type", 2)
            if component_type == 2:
                handler = _prefix_lookup(self.buttons, cid, ctx)
                if not handler:
                    raise UnknownButtonError(f"Unknown button: {cid}")
            else:
                handler = _prefix_lookup(self.selects, cid, ctx)
                if not handler:
                    raise UnknownComponentError(f"Unknown select: {cid}")

            if getattr(handler, "_defer", False) and not ctx._worker_mode:
                return await _defer_to_worker(ctx, interaction, ctx.defer_edit)

            return await _invoke(handler, ctx, f"Component '{cid}'")

        if itype == APPLICATION_COMMAND_AUTOCOMPLETE:
            key, _ = _resolve_command_key(interaction["data"])
            option_name = _focused_option_name(interaction["data"])
            handler = self.autocompletes.get((key, option_name))
            if not handler:
                raise UnsupportedInteractionError(f"No autocomplete handler for ({key!r}, {option_name!r})")
            response = await _invoke(handler, ctx, f"Autocomplete '{key}/{option_name}'")
            # handlers may simply return the choices: plain strings are
            # filtered against the typed value, dicts are sent as-is
            if isinstance(response, list):
                response = cast("list[Any]", response)
                if all(isinstance(c, str) for c in response):
                    query = str(ctx.focused_value or "").lower()
                    response = [{"name": c, "value": c} for c in response if query in c.lower()]
                return await ctx.respond_autocomplete(response[:25])
            return response

        if itype == MODAL_SUBMIT:
            cid = interaction["data"]["custom_id"]
            handler = _prefix_lookup(self.modals, cid, ctx)
            if not handler:
                raise UnknownModalError(f"Unknown modal: {cid}")
            if getattr(handler, "_defer", False) and not ctx._worker_mode:
                return await _defer_to_worker(ctx, interaction, ctx.defer)
            return await _invoke(handler, ctx, f"Modal '{cid}'")

        raise UnsupportedInteractionError(f"Unsupported interaction type: {itype}")


def _resolve_command_key(data: Any) -> tuple[str, Any]:
    name = data["name"]
    options = data.get("options", [])
    if not options:
        return name, None
    first = options[0]
    if first.get("type") == _SUB_COMMAND:
        return f"{name}/{first['name']}", first.get("options", [])
    if first.get("type") == _SUB_COMMAND_GROUP:
        sub = first["options"][0]
        return f"{name}/{first['name']}/{sub['name']}", sub.get("options", [])
    return name, None


def _focused_option_name(data: Any) -> str | None:
    for opt in data.get("options", []):
        if opt.get("focused"):
            return opt["name"]
        # subcommand: focused option may be nested
        if opt.get("type") in (_SUB_COMMAND, _SUB_COMMAND_GROUP):
            for inner in opt.get("options", []):
                if inner.get("focused"):
                    return inner["name"]
                for deepest in inner.get("options", []):
                    if deepest.get("focused"):
                        return deepest["name"]
    return None


async def _defer_to_worker(ctx: Any, interaction: Any, ack: Any, **ack_kwargs: Any) -> Any:
    import os
    import traceback

    from .defer import invoke_worker

    worker_fn = os.environ.get("CORDLESS_WORKER_FUNCTION")
    if not worker_fn:
        raise CordlessError(
            "CORDLESS_WORKER_FUNCTION is not set: add defer_worker to cordless.toml and run cordless deploy"
        )
    # ACK Discord first so the deferred response still goes back even if the invoke fails
    await ack(**ack_kwargs)
    try:
        invoke_worker(worker_fn, interaction)
    except Exception:
        traceback.print_exc()
    return ctx.response


def _prefix_lookup(registry: Any, cid: str, ctx: Any) -> Any:
    """Match "shop:item1" to a "shop" handler; suffix segments land on ctx.custom_id_args."""
    handler = registry.get(cid)
    if handler is None and ":" in cid:
        prefix, *args = cid.split(":")
        handler = registry.get(prefix)
        if handler is not None:
            ctx.custom_id_args = args
    return handler


async def _invoke(handler: Any, ctx: Any, description: str, params: Any = None) -> Any:
    guard = getattr(handler, "_guard", None)
    if guard is not None:
        result = guard(ctx)
        if asyncio.iscoroutine(result):
            await result

    kwargs: dict[str, Any] = {}
    if params and ctx.options:
        # Handlers may declare options as parameters: async def buy(ctx, item: str, qty: int = 1)
        kwargs = {name: ctx.options[name] for name in params if name in ctx.options}

    result = await handler(ctx, **kwargs)
    response = result if result is not None else ctx.response

    if response is None:
        if ctx._worker_mode:
            return None  # deferred handler did nothing, Discord keeps the message as-is
        raise NoResponseError(f"{description} handler never called ctx.send/edit/defer nor returned a response")

    return response
