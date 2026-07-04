import asyncio
import inspect

from .errors import (
    CordlessError,
    NoResponseError,
    UnknownButtonError,
    UnknownCommandError,
    UnknownComponentError,
    UnknownModalError,
    UnsupportedInteractionError,
)

PING = 1
APPLICATION_COMMAND = 2
MESSAGE_COMPONENT = 3
APPLICATION_COMMAND_AUTOCOMPLETE = 4
MODAL_SUBMIT = 5

_SUB_COMMAND = 1
_SUB_COMMAND_GROUP = 2


class Router:
    def __init__(self):
        self.commands = {}
        self.buttons = {}
        self.selects = {}
        self.modals = {}
        self.autocompletes = {}   # (cmd_key, option_name) → handler
        self._error_handler = None

    def register_command(self, name, handler, description="No description provided.", options=None, dm_permission=True, cmd_type=1):
        self.commands[name] = {
            "handler": handler,
            "description": description,
            "options": options or [],
            "dm_permission": dm_permission,
            "cmd_type": cmd_type,
        }

    def register_button(self, custom_id, handler):
        self.buttons[custom_id] = handler

    def register_select(self, custom_id, handler):
        self.selects[custom_id] = handler

    def register_modal(self, custom_id, handler):
        self.modals[custom_id] = handler

    def register_autocomplete(self, cmd_name, option_name, handler):
        self.autocompletes[(cmd_name, option_name)] = handler

    def register_error_handler(self, handler):
        self._error_handler = handler

    def command_definitions(self):
        flat = {}   # name → meta
        subs = {}   # top-level name → {path → meta}

        for key, meta in self.commands.items():
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

        result = []

        for name, meta in flat.items():
            cmd_type = meta.get("cmd_type", 1)
            if cmd_type in (2, 3):
                # Context menu commands: no description, no options
                cmd = {"name": name, "type": cmd_type}
                if not meta.get("dm_permission", True):
                    cmd["dm_permission"] = False
                result.append(cmd)
                continue
            cmd = {
                "name": name,
                "description": meta["description"],
                "type": 1,
                "options": meta["options"],
            }
            if not meta.get("dm_permission", True):
                cmd["dm_permission"] = False
            result.append(cmd)

        for top, entries in subs.items():
            options = []
            for path, meta in entries.items():
                parts = path.split("/")
                if len(parts) == 2:
                    # parent/sub
                    options.append({
                        "name": parts[1],
                        "description": meta["description"],
                        "type": _SUB_COMMAND,
                        "options": meta["options"],
                    })
                elif len(parts) == 3:
                    # parent/group/sub, grouped by group name
                    group_name = parts[1]
                    sub_name = parts[2]
                    group = next((o for o in options if o["name"] == group_name), None)
                    if group is None:
                        group = {
                            "name": group_name,
                            "description": "No description provided.",
                            "type": _SUB_COMMAND_GROUP,
                            "options": [],
                        }
                        options.append(group)
                    group["options"].append({
                        "name": sub_name,
                        "description": meta["description"],
                        "type": _SUB_COMMAND,
                        "options": meta["options"],
                    })

            first_desc = next(iter(entries.values()))["description"]
            cmd = {
                "name": top,
                "description": first_desc,
                "type": 1,
                "options": options,
            }
            if any(not m.get("dm_permission", True) for m in entries.values()):
                cmd["dm_permission"] = False
            result.append(cmd)

        return result

    async def dispatch(self, interaction, ctx):
        try:
            return await self._dispatch_inner(interaction, ctx)
        except Exception as exc:
            if self._error_handler is not None:
                result = self._error_handler(ctx, exc)
                if asyncio.iscoroutine(result):
                    result = await result
                response = result if result is not None else ctx.response
                if response is not None:
                    return response
            raise

    async def _dispatch_inner(self, interaction, ctx):
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
                import os
                import traceback
                from .defer import invoke_worker
                worker_fn = os.environ.get("CORDLESS_WORKER_FUNCTION")
                if not worker_fn:
                    raise CordlessError(
                        "CORDLESS_WORKER_FUNCTION is not set: add defer_worker to cordless.toml and run cordless deploy"
                    )
                # ACK Discord first so type 5 still goes back even if the invoke fails
                await ctx.defer()
                try:
                    invoke_worker(worker_fn, interaction)
                except Exception:
                    traceback.print_exc()
                return ctx.response
            return await _invoke(handler, ctx, f"Command '{key}'", pass_options=True)

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
                import os
                import traceback
                from .defer import invoke_worker
                worker_fn = os.environ.get("CORDLESS_WORKER_FUNCTION")
                if not worker_fn:
                    raise CordlessError(
                        "CORDLESS_WORKER_FUNCTION is not set: add defer_worker to cordless.toml and run cordless deploy"
                    )
                await ctx.defer_edit()
                try:
                    invoke_worker(worker_fn, interaction)
                except Exception:
                    traceback.print_exc()
                return ctx.response

            return await _invoke(handler, ctx, f"Component '{cid}'")

        if itype == APPLICATION_COMMAND_AUTOCOMPLETE:
            key, _ = _resolve_command_key(interaction["data"])
            option_name = _focused_option_name(interaction["data"])
            handler = self.autocompletes.get((key, option_name))
            if not handler:
                raise UnsupportedInteractionError(f"No autocomplete handler for ({key!r}, {option_name!r})")
            return await _invoke(handler, ctx, f"Autocomplete '{key}/{option_name}'")

        if itype == MODAL_SUBMIT:
            cid = interaction["data"]["custom_id"]
            handler = _prefix_lookup(self.modals, cid, ctx)
            if not handler:
                raise UnknownModalError(f"Unknown modal: {cid}")
            return await _invoke(handler, ctx, f"Modal '{cid}'")

        raise UnsupportedInteractionError(f"Unsupported interaction type: {itype}")


def _resolve_command_key(data):
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


def _focused_option_name(data):
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


def _prefix_lookup(registry, cid, ctx):
    """Match "shop:item1" to a "shop" handler; suffix segments land on ctx.custom_id_args."""
    handler = registry.get(cid)
    if handler is None and ":" in cid:
        prefix, *args = cid.split(":")
        handler = registry.get(prefix)
        if handler is not None:
            ctx.custom_id_args = args
    return handler


async def _invoke(handler, ctx, description, pass_options=False):
    guard = getattr(handler, "_guard", None)
    if guard is not None:
        result = guard(ctx)
        if asyncio.iscoroutine(result):
            await result

    kwargs = {}
    if pass_options and ctx.options:
        # Handlers may declare options as parameters: async def buy(ctx, item: str, qty: int = 1)
        params = list(inspect.signature(handler).parameters)
        kwargs = {name: ctx.options[name] for name in params[1:] if name in ctx.options}

    result = await handler(ctx, **kwargs)
    response = result if result is not None else ctx.response

    if response is None:
        if ctx._worker_mode:
            return None  # deferred handler did nothing, Discord keeps the message as-is
        raise NoResponseError(f"{description} handler never called ctx.send/edit/defer nor returned a response")

    return response
