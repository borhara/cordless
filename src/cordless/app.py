import asyncio
import base64
import inspect
import json
import re

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


def options_from_signature(func):
    """Infer Discord option dicts from a handler's type hints.

    async def buy(ctx, item: str, qty: int = 1) →
    a required string option "item" and an optional integer option "qty".
    """
    params = list(inspect.signature(func).parameters.values())[1:]  # skip ctx
    options = []
    for p in params:
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        opt = {
            "name": p.name,
            "description": "No description provided.",
            "type": _ANNOTATION_TYPES.get(p.annotation, 3),
        }
        if p.default is inspect.Parameter.empty:
            opt["required"] = True
        options.append(opt)
    return options


def option(name, description="No description provided.", *, type="string", required=False,
           autocomplete=False, choices=None, min_value=None, max_value=None,
           min_length=None, max_length=None):
    """Build a Discord application command option dict."""
    opt = {
        "name": name,
        "description": description,
        "type": _OPTION_TYPES.get(type, type) if isinstance(type, str) else type,
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

    def command(self, name, description="No description provided.", options=None, defer=False, dm_permission=True):
        _validate_command_name(name)

        def decorator(func):
            _options = options if options is not None else options_from_signature(func)
            if defer:
                func._defer = True
                # Importing defer.py here (at decorator-application time, i.e. Lambda INIT)
                # causes boto3 to be imported and the Lambda client pre-created before
                # Discord's 3-second response window opens on the first invocation.
                try:
                    from . import defer as _defer_mod  # noqa: F401
                except Exception:
                    pass
            self.router.register_command(name, func, description=description, options=_options, dm_permission=dm_permission)
            return func

        return decorator

    @property
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

    def select(self, custom_id):
        def decorator(func):
            self.router.register_select(custom_id, func)
            return func

        return decorator

    def modal(self, custom_id):
        def decorator(func):
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

        if self.public_key:
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
        """Load a cog extension by dotted module path (e.g. 'cogs.game').
        The module must define a setup(bot) function that calls bot.add_cog()."""
        import importlib
        module = importlib.import_module(name)
        if not hasattr(module, "setup"):
            raise ValueError(f"Extension '{name}' is missing a setup(bot) function")
        module.setup(self)

    def add_cog(self, cog):
        """Register all decorated handlers from a Cog instance."""
        for _, method in inspect.getmembers(cog, predicate=inspect.ismethod):
            ctype = getattr(method, "_cog_type", None)
            if ctype is None:
                continue
            if ctype == "command":
                if method._cog_defer:
                    method.__func__._defer = True
                    try:
                        from . import defer as _defer_mod  # noqa: F401
                    except Exception:
                        pass
                _validate_command_name(method._cog_name)
                cog_options = method._cog_options
                if cog_options is None:
                    cog_options = options_from_signature(method)
                self.router.register_command(
                    method._cog_name, method,
                    description=method._cog_description,
                    options=cog_options,
                    dm_permission=method._cog_dm_permission,
                )
            elif ctype == "button":
                if getattr(method, "_cog_defer", False):
                    method.__func__._defer = True
                self.router.register_button(method._cog_custom_id, method)
            elif ctype == "select":
                self.router.register_select(method._cog_custom_id, method)
            elif ctype == "modal":
                self.router.register_modal(method._cog_custom_id, method)
            elif ctype == "autocomplete":
                self.router.register_autocomplete(method._cog_cmd_name, method._cog_option_name, method)
            elif ctype == "user_command":
                self.router.register_command(
                    method._cog_name, method,
                    description=None, options=[],
                    dm_permission=method._cog_dm_permission,
                    cmd_type=2,
                )
            elif ctype == "message_command":
                self.router.register_command(
                    method._cog_name, method,
                    description=None, options=[],
                    dm_permission=method._cog_dm_permission,
                    cmd_type=3,
                )

    def sync_commands(self, bot_token=None, client_id=None, client_secret=None, guild_id=None):
        """Push this bot's registered commands to Discord.

        Authenticate with a bot token, or with client_id + client_secret via
        OAuth2 client credentials (no bot user required). Omit `guild_id`
        (the default) to register commands globally, for every guild that
        has authorized the app and every user in it. Run this from a deploy
        step, not from inside the Lambda handler — it makes blocking network
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
