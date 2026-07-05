import asyncio
import base64
import inspect
import json
import os
import re
from typing import Literal, Union, get_args, get_origin

from .context import Context
from .errors import CordlessError
from .register import sync_commands
from .router import Router
from .verify import verify_signature

PING = 1

_OPTION_TYPES = {
    "string": 3,
    "integer": 4,
    "boolean": 5,
    "user": 6,
    "channel": 7,
    "role": 8,
    "number": 10,
    "attachment": 11,
}

_ANNOTATION_TYPES = {str: 3, int: 4, bool: 5, float: 10}

_NAME_RE = re.compile(r"[a-z0-9_-]{1,32}")


def _validate_command_name(name):
    """Fail at decoration time instead of with a cryptic Discord API error at register time."""
    for part in name.split("/"):
        if not _NAME_RE.fullmatch(part):
            raise ValueError(
                f"Invalid command name {name!r}: Discord requires 1-32 lowercase letters, digits, - or _"
            )


def _unwrap_optional(annotation):
    if get_origin(annotation) is Union:
        inner = [a for a in get_args(annotation) if a is not type(None)]
        if len(inner) == 1:
            return inner[0], True
    try:
        import types
        if isinstance(annotation, types.UnionType):
            inner = [a for a in annotation.__args__ if a is not type(None)]
            if len(inner) == 1:
                return inner[0], True
    except AttributeError:
        pass
    return annotation, False


def options_from_signature(func):
    """Infer Discord option dicts from a handler's type hints.

    async def buy(ctx, item: str, qty: int = 1) →
    a required string option "item" and an optional integer option "qty".
    Supports Literal["a", "b"] for choices and Optional[int] / int | None for
    optional typed parameters.
    """
    params = list(inspect.signature(func).parameters.values())[1:]  # skip ctx
    options = []
    for p in params:
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        annotation = p.annotation
        optional_from_default = p.default is not inspect.Parameter.empty

        annotation, optional_from_type = _unwrap_optional(annotation)
        is_optional = optional_from_default or optional_from_type

        opt = {"name": p.name, "description": "No description provided."}

        if get_origin(annotation) is Literal:
            choices_vals = get_args(annotation)
            opt["type"] = 4 if choices_vals and isinstance(choices_vals[0], int) else 3
            opt["choices"] = [{"name": str(v), "value": v} for v in choices_vals]
        else:
            opt["type"] = _ANNOTATION_TYPES.get(annotation, 3)

        if not is_optional:
            opt["required"] = True
        options.append(opt)
    return options


def option(name, description="No description provided.", *, type="string", required=False,
           autocomplete=False, choices=None, min_value=None, max_value=None,
           min_length=None, max_length=None):
    """Build a Discord application command option dict."""
    if isinstance(type, str) and type not in _OPTION_TYPES:
        raise ValueError(
            f"Unknown option type {type!r}: expected one of {', '.join(_OPTION_TYPES)}"
        )
    opt = {
        "name": name,
        "description": description,
        "type": _OPTION_TYPES[type] if isinstance(type, str) else type,
    }
    if required:
        opt["required"] = True
    if autocomplete:
        opt["autocomplete"] = True
    if choices is not None:
        opt["choices"] = choices
    if min_value is not None:
        opt["min_value"] = min_value
    if max_value is not None:
        opt["max_value"] = max_value
    if min_length is not None:
        opt["min_length"] = min_length
    if max_length is not None:
        opt["max_length"] = max_length
    return opt


class Cordless:
    def __init__(self, public_key=None):
        self.router = Router()
        self.public_key = public_key
        self.crons = {}
        if public_key is not None and not public_key:
            print(
                "cordless: DISCORD_PUBLIC_KEY is empty - all requests will be "
                "rejected with 401 until it is set"
            )

    def command(self, name, description="No description provided.", options=None, defer=False,
                dm_permission=True, default_member_permissions=None, nsfw=False, ephemeral=False):
        _validate_command_name(name)

        def decorator(func):
            _options = options if options is not None else options_from_signature(func)
            if defer:
                func._defer = True
                if ephemeral:
                    func._defer_ephemeral = True
                # Importing defer.py here (at decorator-application time, i.e. Lambda INIT)
                # causes boto3 to be imported and the Lambda client pre-created before
                # Discord's 3-second response window opens on the first invocation.
                try:
                    from . import defer as _defer_mod  # noqa: F401
                except Exception:
                    pass
            self.router.register_command(name, func, description=description, options=_options,
                                         dm_permission=dm_permission,
                                         default_member_permissions=default_member_permissions,
                                         nsfw=nsfw)
            return func

        return decorator

    def _discord_request(self, method, path, payload=None):
        import json
        import urllib.error
        import urllib.request
        from importlib.metadata import version as _ver
        token = os.environ["DISCORD_BOT_TOKEN"]
        body = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(
            f"https://discord.com/api/v10{path}",
            data=body,
            headers={
                "Authorization": f"Bot {token}",
                "User-Agent": f"DiscordBot (https://cordless.dev, {_ver('cordless')})",
                **({"Content-Type": "application/json"} if body else {}),
            },
            method=method,
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Discord API error {exc.code}: {exc.read().decode()}") from exc

    async def send_message(self, channel_id, content=None, *, embeds=None, components=None):
        payload = {}
        if content is not None:
            payload["content"] = content
        if embeds is not None:
            payload["embeds"] = [e.to_dict() if hasattr(e, "to_dict") else e for e in embeds]
        if components is not None:
            payload["components"] = [c.to_dict() if hasattr(c, "to_dict") else c for c in components]
        import asyncio
        await asyncio.get_event_loop().run_in_executor(
            None, self._discord_request, "POST", f"/channels/{channel_id}/messages", payload
        )

    async def edit_message(self, channel_id, message_id, content=None, *, embeds=None, components=None):
        payload = {}
        if content is not None:
            payload["content"] = content
        if embeds is not None:
            payload["embeds"] = [e.to_dict() if hasattr(e, "to_dict") else e for e in embeds]
        if components is not None:
            payload["components"] = [c.to_dict() if hasattr(c, "to_dict") else c for c in components]
        import asyncio
        await asyncio.get_event_loop().run_in_executor(
            None, self._discord_request, "PATCH", f"/channels/{channel_id}/messages/{message_id}", payload
        )

    async def delete_message(self, channel_id, message_id):
        import asyncio
        await asyncio.get_event_loop().run_in_executor(
            None, self._discord_request, "DELETE", f"/channels/{channel_id}/messages/{message_id}"
        )

    async def add_role(self, guild_id, user_id, role_id):
        import asyncio
        await asyncio.get_event_loop().run_in_executor(
            None, self._discord_request, "PUT", f"/guilds/{guild_id}/members/{user_id}/roles/{role_id}"
        )

    async def remove_role(self, guild_id, user_id, role_id):
        import asyncio
        await asyncio.get_event_loop().run_in_executor(
            None, self._discord_request, "DELETE", f"/guilds/{guild_id}/members/{user_id}/roles/{role_id}"
        )

    def worker_handler(self):
        from .worker import make_worker_handler
        return make_worker_handler(self)

    def handler(self):
        def _handler(event, context=None):
            cron_name = (event or {}).get("_cordless_cron")
            if cron_name:
                return self.run_cron(cron_name)
            return self.handle(event, context)
        return _handler

    def cron(self, schedule, name=None):
        """Register a scheduled handler; `cordless deploy` wires it to EventBridge.

        `schedule` is an EventBridge expression, e.g. "rate(1 day)" or
        "cron(0 12 * * ? *)". The handler takes no arguments.
        """
        def decorator(func):
            self.crons[name or func.__name__] = {"schedule": schedule, "handler": func}
            return func
        return decorator

    def run_cron(self, name):
        entry = self.crons.get(name)
        if entry is None:
            raise CordlessError(f"Unknown cron: {name}")
        return asyncio.run(entry["handler"]())

    def button(self, custom_id, defer=False):
        def decorator(func):
            if defer:
                func._defer = True
                try:
                    from . import defer as _defer_mod  # noqa: F401
                except Exception:
                    pass
            self.router.register_button(custom_id, func)
            return func

        return decorator

    def select(self, custom_id, defer=False):
        def decorator(func):
            if defer:
                func._defer = True
                try:
                    from . import defer as _defer_mod  # noqa: F401
                except Exception:
                    pass
            self.router.register_select(custom_id, func)
            return func

        return decorator

    def modal(self, custom_id, defer=False):
        def decorator(func):
            if defer:
                func._defer = True
                try:
                    from . import defer as _defer_mod  # noqa: F401
                except Exception:
                    pass
            self.router.register_modal(custom_id, func)
            return func

        return decorator

    def user_command(self, name, dm_permission=True):
        """Register a User context menu command (right-click → Apps → name)."""
        def decorator(func):
            self.router.register_command(name, func, description=None, options=[], dm_permission=dm_permission, cmd_type=2)
            return func
        return decorator

    def message_command(self, name, dm_permission=True):
        """Register a Message context menu command (right-click message → Apps → name)."""
        def decorator(func):
            self.router.register_command(name, func, description=None, options=[], dm_permission=dm_permission, cmd_type=3)
            return func
        return decorator

    def autocomplete(self, cmd_name, option_name):
        def decorator(func):
            self.router.register_autocomplete(cmd_name, option_name, func)
            return func

        return decorator

    def error(self, func):
        self.router.register_error_handler(func)
        return func

    def guard(self, fn):
        def decorator(handler):
            handler._guard = fn
            return handler

        return decorator

    def handle(self, event, context=None):
        body = _extract_body(event)

        # None means verification is deliberately off (local/testing); an empty
        # string is a misconfiguration and must fail closed, not silently skip
        if self.public_key is not None:
            headers = event.get("headers") or {}
            signature = _get_header(headers, "x-signature-ed25519")
            timestamp = _get_header(headers, "x-signature-timestamp")

            if not verify_signature(self.public_key, signature, timestamp, body):
                return _json_response(401, {"error": "invalid request signature"})

        try:
            interaction = json.loads(body)
        except (ValueError, TypeError):
            return _json_response(400, {"error": "invalid JSON body"})

        if interaction.get("type") == PING:
            return _json_response(200, {"type": PING})

        ctx = Context(interaction)

        try:
            return asyncio.run(self.router.dispatch(interaction, ctx))
        except CordlessError as exc:
            return _json_response(400, {"error": str(exc)})

    def load_extension(self, name: str) -> None:
        """Load a cog module by dotted path (e.g. 'cogs.game').
        Discovers all Cog instances defined in the module automatically.
        Alternatively, define setup(bot) for manual control."""
        import importlib
        from .cog import Cog as _Cog
        module = importlib.import_module(name)
        if hasattr(module, "setup"):
            module.setup(self)
            return
        cogs = [v for v in vars(module).values() if isinstance(v, _Cog)]
        if not cogs:
            raise ValueError(f"Extension '{name}' must define a Cog instance or a setup(bot) function")
        for cog in cogs:
            self.add_cog(cog)

    def load_extensions(self, package: str) -> None:
        """Load all cog modules in a package (e.g. 'cogs'). Files starting with '_' are skipped."""
        import importlib
        import pkgutil
        pkg = importlib.import_module(package)
        for module_info in pkgutil.iter_modules(pkg.__path__):
            if not module_info.name.startswith("_"):
                self.load_extension(f"{package}.{module_info.name}")

    def add_cog(self, cog):
        """Register all decorated handlers from a Cog instance."""
        for ctype, func, kwargs in cog._handlers:
            if ctype == "command":
                if kwargs["defer"]:
                    func._defer = True
                    if kwargs.get("ephemeral"):
                        func._defer_ephemeral = True
                    try:
                        from . import defer as _defer_mod  # noqa: F401
                    except Exception:
                        pass
                _validate_command_name(kwargs["name"])
                resolved_options = kwargs["options"]
                if resolved_options is None:
                    resolved_options = options_from_signature(func)
                self.router.register_command(
                    kwargs["name"], func,
                    description=kwargs["description"],
                    options=resolved_options,
                    dm_permission=kwargs["dm_permission"],
                    default_member_permissions=kwargs.get("default_member_permissions"),
                    nsfw=kwargs.get("nsfw", False),
                )
            elif ctype == "button":
                if kwargs.get("defer"):
                    func._defer = True
                self.router.register_button(kwargs["custom_id"], func)
            elif ctype == "select":
                if kwargs.get("defer"):
                    func._defer = True
                self.router.register_select(kwargs["custom_id"], func)
            elif ctype == "modal":
                if kwargs.get("defer"):
                    func._defer = True
                self.router.register_modal(kwargs["custom_id"], func)
            elif ctype == "autocomplete":
                self.router.register_autocomplete(kwargs["cmd_name"], kwargs["option_name"], func)
            elif ctype == "user_command":
                self.router.register_command(
                    kwargs["name"], func,
                    description=None, options=[],
                    dm_permission=kwargs["dm_permission"],
                    cmd_type=2,
                )
            elif ctype == "message_command":
                self.router.register_command(
                    kwargs["name"], func,
                    description=None, options=[],
                    dm_permission=kwargs["dm_permission"],
                    cmd_type=3,
                )

    def sync_commands(self, bot_token=None, client_id=None, client_secret=None, guild_id=None):
        """Push this bot's registered commands to Discord.

        Authenticate with a bot token, or with client_id + client_secret via
        OAuth2 client credentials (no bot user required). Omit `guild_id`
        (the default) to register commands globally, for every guild that
        has authorized the app and every user in it. Run this from a deploy
        step, not from inside the Lambda handler, since it makes blocking network
        calls to Discord's API.
        """
        return sync_commands(
            self.router.command_definitions(),
            guild_id=guild_id,
            bot_token=bot_token,
            client_id=client_id,
            client_secret=client_secret,
        )


def _extract_body(event):
    body = event.get("body", "")

    if event.get("isBase64Encoded"):
        return base64.b64decode(body).decode()

    return body


def _get_header(headers, name):
    name = name.lower()

    for key, value in headers.items():
        if key.lower() == name:
            return value

    return None


def _json_response(status_code, payload):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload),
    }
