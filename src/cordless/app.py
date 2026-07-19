import asyncio
import base64
import inspect
import json
import os
import re
import threading
from http.client import HTTPException, HTTPSConnection
from typing import Literal, Union, get_args, get_origin

from .context import _FLAG_UI_KIT, Context, _attach_files, _contains_uikit
from .errors import CordlessError
from .register import sync_commands
from .router import Router
from .verify import verify_signature

PING = 1

# How long _discord_request keeps retrying a 429 before giving up. Matches
# defer_worker's 30s default timeout - callers doing bursty sends from the
# main function's default 10s timeout should raise `timeout` in
# cordless.toml or move the work behind defer_worker.
_MAX_RETRY_SECONDS = 30.0

# Kept open across invocations in a warm Lambda container, so most requests
# skip the TLS handshake instead of paying for it every time.
_conn = None
_conn_lock = threading.Lock()


def _send_discord_request(method, path, body, headers):
    global _conn
    with _conn_lock:
        if _conn is None:
            _conn = HTTPSConnection("discord.com")
        try:
            _conn.request(method, path, body, headers)
            resp = _conn.getresponse()
            data = resp.read()
        except (HTTPException, OSError):
            # the other end closed the kept-alive connection, reconnect once
            _conn.close()
            _conn = HTTPSConnection("discord.com")
            _conn.request(method, path, body, headers)
            resp = _conn.getresponse()
            data = resp.read()
        return resp.status, resp.headers, data


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


def _prewarm_defer():
    """Import defer.py at decoration time (Lambda INIT) so boto3's Lambda client is
    constructed before Discord's 3-second response window opens, not synchronously
    during the first deferred invocation. Never called unconditionally at module
    scope: that would make every bot pay boto3's import cost, even ones that never
    use defer=True.
    """
    try:
        from . import defer as _defer_mod  # noqa: F401
    except Exception:
        pass


def _validate_command_name(name):
    """Fail at decoration time instead of with a cryptic Discord API error at register time."""
    for part in name.split("/"):
        if not _NAME_RE.fullmatch(part):
            raise ValueError(f"Invalid command name {name!r}: Discord requires 1-32 lowercase letters, digits, - or _")


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
    Supports Literal["a", "b"] for choices, and Optional[int] / int | None to
    unwrap the inner type (the option is non-required only when a default is also given).
    """
    # eval_str resolves PEP 563 stringized annotations ("int" → int), which
    # `from __future__ import annotations` applies to the whole user module;
    # without it every option silently falls back to type 3 (string)
    try:
        sig = inspect.signature(func, eval_str=True)
    except NameError:
        sig = inspect.signature(func)  # unresolvable forward ref: keep the string, option stays type 3
    params = list(sig.parameters.values())[1:]  # skip ctx
    options = []
    for p in params:
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        annotation = p.annotation
        optional_from_default = p.default is not inspect.Parameter.empty

        annotation, _ = _unwrap_optional(annotation)
        is_optional = optional_from_default

        opt = {"name": p.name, "description": "No description provided."}

        if get_origin(annotation) is Literal:
            choices_vals = get_args(annotation)
            first = choices_vals[0] if choices_vals else None
            if isinstance(first, bool):
                raise ValueError(
                    f"Literal choices of type bool are not supported (parameter {p.name!r}): "
                    "Discord doesn't allow `choices` on boolean options"
                )
            elif isinstance(first, float):
                opt["type"] = 10
            elif isinstance(first, int):
                opt["type"] = 4
            else:
                opt["type"] = 3
            opt["choices"] = [{"name": str(v), "value": v} for v in choices_vals]
        else:
            opt["type"] = _ANNOTATION_TYPES.get(annotation, 3)

        if not is_optional:
            opt["required"] = True
        options.append(opt)
    return options


def option(
    name,
    description="No description provided.",
    *,
    type="string",
    required=False,
    autocomplete=False,
    choices=None,
    min_value=None,
    max_value=None,
    min_length=None,
    max_length=None,
):
    """Build a Discord application command option dict, for `@bot.command(options=[...])`.

    | Parameter | |
    |---|---|
    | `type` | `"string"`, `"integer"`, `"number"`, `"boolean"`, `"user"`, `"channel"`, `"role"`, `"attachment"` |
    | `required` | Default `False`, note this is the opposite default from inferred options, where a parameter without a default value is required |
    | `autocomplete` | Pair with `@bot.autocomplete` |
    | `choices` | List of `{"name": label, "value": value}` dicts; the user must pick one |
    | `min_value` / `max_value` | Bounds for `integer`/`number` options |
    | `min_length` / `max_length` | Length bounds for `string` options |
    """
    if isinstance(type, str) and type not in _OPTION_TYPES:
        raise ValueError(f"Unknown option type {type!r}: expected one of {', '.join(_OPTION_TYPES)}")
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
        """`public_key` is your app's hex-encoded public key from the Discord
        Developer Portal. Every request is verified against it (Ed25519) and
        rejected with a 401 on mismatch. Passing `None` **disables signature
        verification**, useful for local tests that post fake interactions,
        never for a deployed bot. An empty string is treated as a
        misconfiguration and rejects everything (fails closed rather than
        open)."""
        self.router = Router()
        self.public_key = public_key
        self.crons = {}
        if public_key is not None and not public_key:
            print("cordless: DISCORD_PUBLIC_KEY is empty - all requests will be rejected with 401 until it is set")

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
        user_installable=False,
    ):
        """Register a slash command.

        | Parameter | |
        |---|---|
        | `name` | 1-32 lowercase letters, digits, `-` or `_`; validated at decoration time. Use `parent/sub` or `parent/group/sub` paths for subcommands |
        | `description` | Shown in Discord's command picker |
        | `options` | List of option dicts (build with `option()`). When omitted, options are inferred from the handler's typed parameters: `str`, `int`, `float`, `bool`, `Literal[...]` for fixed choices, and `Optional[T]` / `T \\| None` (unwrapped to `T`; a default value is what makes the option optional) |
        | `defer` | Respond via the worker Lambda |
        | `dm_permission` | Set `False` to hide the command in DMs |
        | `default_member_permissions` | Permission bitfield members need to see the command |
        | `nsfw` | Restrict to age-verified channels |
        | `ephemeral` | Only meaningful with `defer=True`: makes the loading state and final reply private. For non-deferred commands, use `ctx.send(ephemeral=True)` instead |
        | `guild_ids` | Scope this command to specific guilds instead of registering it globally |
        """
        _validate_command_name(name)

        def decorator(func):
            _options = options if options is not None else options_from_signature(func)
            if defer:
                func._defer = True
                if ephemeral:
                    func._defer_ephemeral = True
                _prewarm_defer()
            self.router.register_command(
                name,
                func,
                description=description,
                options=_options,
                dm_permission=dm_permission,
                default_member_permissions=default_member_permissions,
                nsfw=nsfw,
                guild_ids=guild_ids,
                user_installable=user_installable,
            )
            return func

        return decorator

    def _discord_request(self, method, path, payload=None, files=None):
        import json
        import time
        from importlib.metadata import version as _ver

        from . import ratelimit

        token = os.environ["DISCORD_BOT_TOKEN"]
        if files:
            from ._multipart import build_multipart_body

            _attach_files(payload, files)
            body, content_type = build_multipart_body(payload, files)
        elif payload is not None:
            body, content_type = json.dumps(payload).encode(), "application/json"
        else:
            body, content_type = None, None
        headers = {
            "Authorization": f"Bot {token}",
            "User-Agent": f"DiscordBot (https://cordless.dev, {_ver('cordless')})",
            **({"Content-Type": content_type} if content_type else {}),
        }

        full_path = f"/api/v10{path}"
        deadline = time.monotonic() + _MAX_RETRY_SECONDS
        while True:
            ratelimit.wait_if_needed(method, path)
            status, resp_headers, data = _send_discord_request(method, full_path, body, headers)
            if status < 300:
                ratelimit.record_response(method, path, resp_headers)
                return data
            if status == 429 and time.monotonic() < deadline:
                try:
                    retry_after = float(json.loads(data).get("retry_after", 1))
                except (ValueError, AttributeError):
                    retry_after = 1.0
                ratelimit.note_blocked(method, path, retry_after)
                time.sleep(ratelimit.jittered_wait(retry_after))
                continue
            raise RuntimeError(f"Discord API error {status}: {data.decode(errors='replace')}")

    async def send_message(self, channel_id, content=None, *, embeds=None, components=None, files=None):
        """Send a message as the bot. Requires `DISCORD_BOT_TOKEN`, callable
        from anywhere with no interaction to respond to, typically cron
        handlers. `files` is a list of `(filename, bytes)` tuples, same as
        `ctx.send`/`ctx.edit`."""
        payload = {}
        if content is not None:
            payload["content"] = content
        if embeds is not None:
            payload["embeds"] = [e.to_dict() if hasattr(e, "to_dict") else e for e in embeds]
        if components is not None:
            payload["components"] = [c.to_dict() if hasattr(c, "to_dict") else c for c in components]
        if _contains_uikit(components):
            payload["flags"] = _FLAG_UI_KIT
        import asyncio

        await asyncio.get_event_loop().run_in_executor(
            None, self._discord_request, "POST", f"/channels/{channel_id}/messages", payload, files
        )

    async def edit_message(self, channel_id, message_id, content=None, *, embeds=None, components=None, files=None):
        """Edit a message the bot previously sent. Requires
        `DISCORD_BOT_TOKEN`. `files` is a list of `(filename, bytes)`
        tuples, same as `ctx.send`/`ctx.edit`."""
        payload = {}
        if content is not None:
            payload["content"] = content
        if embeds is not None:
            payload["embeds"] = [e.to_dict() if hasattr(e, "to_dict") else e for e in embeds]
        if components is not None:
            payload["components"] = [c.to_dict() if hasattr(c, "to_dict") else c for c in components]
        if _contains_uikit(components):
            payload["flags"] = _FLAG_UI_KIT
        import asyncio

        await asyncio.get_event_loop().run_in_executor(
            None, self._discord_request, "PATCH", f"/channels/{channel_id}/messages/{message_id}", payload, files
        )

    async def delete_message(self, channel_id, message_id):
        """Delete a message. Requires `DISCORD_BOT_TOKEN`."""
        import asyncio

        await asyncio.get_event_loop().run_in_executor(
            None, self._discord_request, "DELETE", f"/channels/{channel_id}/messages/{message_id}"
        )

    async def execute_webhook(
        self,
        webhook_id,
        webhook_token=None,
        content=None,
        *,
        embeds=None,
        components=None,
        files=None,
        username=None,
        avatar_url=None,
        tts=False,
        allowed_mentions=None,
        wait=False,
        thread_id=None,
    ):
        """Send a message through a Discord webhook. No bot token required.

        Pass a full webhook URL as `webhook_id` (leave `webhook_token` unset),
        or the id and token separately.
        """
        from . import webhook as _webhook

        if webhook_token is None:
            webhook_id, webhook_token = _webhook.parse_webhook_url(webhook_id)

        payload = _webhook.build_payload(
            content,
            embeds,
            components,
            username=username,
            avatar_url=avatar_url,
            tts=tts,
            allowed_mentions=allowed_mentions,
        )

        _, body = await asyncio.get_event_loop().run_in_executor(
            None, _webhook.execute, webhook_id, webhook_token, payload, files, wait, thread_id
        )
        if wait and body:
            return json.loads(body)

    async def edit_webhook_message(
        self,
        webhook_id,
        webhook_token=None,
        message_id="@original",
        content=None,
        *,
        embeds=None,
        components=None,
        files=None,
        allowed_mentions=None,
    ):
        """Edit a message previously sent through a webhook. No bot token required."""
        from . import webhook as _webhook

        if webhook_token is None:
            webhook_id, webhook_token = _webhook.parse_webhook_url(webhook_id)

        payload = _webhook.build_payload(content, embeds, components, allowed_mentions=allowed_mentions)

        await asyncio.get_event_loop().run_in_executor(
            None, _webhook.edit_message, webhook_id, webhook_token, message_id, payload, files
        )

    async def delete_webhook_message(self, webhook_id, webhook_token=None, message_id="@original"):
        """Delete a message previously sent through a webhook. No bot token required."""
        from . import webhook as _webhook

        if webhook_token is None:
            webhook_id, webhook_token = _webhook.parse_webhook_url(webhook_id)

        await asyncio.get_event_loop().run_in_executor(
            None, _webhook.delete_message, webhook_id, webhook_token, message_id
        )

    async def add_role(self, guild_id, user_id, role_id):
        """Grant a role to a guild member. Requires `DISCORD_BOT_TOKEN`."""
        import asyncio

        await asyncio.get_event_loop().run_in_executor(
            None, self._discord_request, "PUT", f"/guilds/{guild_id}/members/{user_id}/roles/{role_id}"
        )

    async def remove_role(self, guild_id, user_id, role_id):
        """Remove a role from a guild member. Requires `DISCORD_BOT_TOKEN`."""
        import asyncio

        await asyncio.get_event_loop().run_in_executor(
            None, self._discord_request, "DELETE", f"/guilds/{guild_id}/members/{user_id}/roles/{role_id}"
        )

    async def create_webhook(self, channel_id, name, avatar=None):
        """Create a webhook in a channel. Requires DISCORD_BOT_TOKEN. Returns the
        webhook object, including the id/token pair execute_webhook needs."""
        payload = {"name": name}
        if avatar is not None:
            payload["avatar"] = avatar

        body = await asyncio.get_event_loop().run_in_executor(
            None, self._discord_request, "POST", f"/channels/{channel_id}/webhooks", payload
        )
        return json.loads(body)

    async def get_channel_webhooks(self, channel_id):
        """List a channel's webhooks. Requires DISCORD_BOT_TOKEN."""
        body = await asyncio.get_event_loop().run_in_executor(
            None, self._discord_request, "GET", f"/channels/{channel_id}/webhooks"
        )
        return json.loads(body)

    async def delete_webhook(self, webhook_id, webhook_token=None):
        """Delete a webhook. With webhook_token, authenticates with the webhook's
        own token (no bot token needed); otherwise uses DISCORD_BOT_TOKEN."""
        if webhook_token is not None:
            from . import webhook as _webhook

            await asyncio.get_event_loop().run_in_executor(None, _webhook.delete_webhook, webhook_id, webhook_token)
            return

        await asyncio.get_event_loop().run_in_executor(None, self._discord_request, "DELETE", f"/webhooks/{webhook_id}")

    @property
    def worker_handler(self):
        """The worker Lambda's entrypoint, required when `defer_worker` is
        set in `cordless.toml`. Assign at module level in `lambda_function.py`:
        `worker_handler = bot.worker_handler`. If any command uses
        `defer=True`, deploying without this assignment fails the worker
        with "Handler 'worker_handler' missing"."""
        from .worker import make_worker_handler

        return make_worker_handler(self)

    def handler(self):
        """Returns the main Lambda entrypoint. Assign at module level in
        `lambda_function.py`: `handler = bot.handler()`. Wraps `handle()`
        plus keep-warm pings and `@bot.cron` dispatch."""

        def _handler(event, context=None):
            event = event or {}
            if event.get("_cordless_keepwarm"):
                return None  # just here to keep the container warm, nothing to do
            cron_name = event.get("_cordless_cron")
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
        """Run a registered `@bot.cron` handler by name, synchronously. Used
        by `cordless cron NAME` and the deployed EventBridge target; you
        don't normally call this yourself."""
        entry = self.crons.get(name)
        if entry is None:
            raise CordlessError(f"Unknown cron: {name}")
        return asyncio.run(entry["handler"]())

    def button(self, custom_id, defer=False):
        """Register a handler for a button click. Prefix matching applies:
        `custom_id="shop"` also matches `"shop:item1:2"`, with the suffix
        segments landing on `ctx.custom_id_args`."""

        def decorator(func):
            if defer:
                func._defer = True
                _prewarm_defer()
            self.router.register_button(custom_id, func)
            return func

        return decorator

    def select(self, custom_id, defer=False):
        """Register a handler for a select menu. Prefix matching applies:
        `custom_id="shop"` also matches `"shop:item1:2"`, with the suffix
        segments landing on `ctx.custom_id_args`. Selected values are on
        `ctx.values`."""

        def decorator(func):
            if defer:
                func._defer = True
                _prewarm_defer()
            self.router.register_select(custom_id, func)
            return func

        return decorator

    def modal(self, custom_id, defer=False):
        """Register a handler for a modal submission. Prefix matching
        applies: `custom_id="shop"` also matches `"shop:item1:2"`, with the
        suffix segments landing on `ctx.custom_id_args`. Submitted field
        values are on `ctx.modal_values`."""

        def decorator(func):
            if defer:
                func._defer = True
                _prewarm_defer()
            self.router.register_modal(custom_id, func)
            return func

        return decorator

    def user_command(self, name, dm_permission=True, guild_ids=None, user_installable=False):
        """Register a User context menu command (right-click → Apps → name)."""

        def decorator(func):
            self.router.register_command(
                name,
                func,
                description=None,
                options=[],
                dm_permission=dm_permission,
                cmd_type=2,
                guild_ids=guild_ids,
                user_installable=user_installable,
            )
            return func

        return decorator

    def message_command(self, name, dm_permission=True, guild_ids=None, user_installable=False):
        """Register a Message context menu command (right-click message → Apps → name)."""

        def decorator(func):
            self.router.register_command(
                name,
                func,
                description=None,
                options=[],
                dm_permission=dm_permission,
                cmd_type=3,
                guild_ids=guild_ids,
                user_installable=user_installable,
            )
            return func

        return decorator

    def autocomplete(self, cmd_name, option_name):
        """Handler for an option marked `autocomplete=True`. Return a list of
        strings (filtered against the typed value for you) or choice dicts
        (sent as-is)."""

        def decorator(func):
            self.router.register_autocomplete(cmd_name, option_name, func)
            return func

        return decorator

    def error(self, func):
        """Register the error handler, called as `(ctx, exc)`. If it sends a
        response (or returns one), that becomes the interaction's response;
        otherwise the exception propagates."""
        self.router.register_error_handler(func)
        return func

    def guard(self, fn):
        """Attach a guard that runs before the handler. Guards reject by
        **raising**: a falsy return value is ignored, not treated as a
        rejection. Can be sync or async; runs for commands, buttons, selects,
        and modals alike."""

        def decorator(handler):
            handler._guard = fn
            return handler

        return decorator

    def handle(self, event, context=None):
        """Process one raw Lambda event dict: verifies the signature and
        dispatches it to the right registered handler. Most bots use
        `handler()` instead, which wraps this plus keep-warm pings and
        `@bot.cron` dispatch, call this directly only if you're building a
        custom Lambda entrypoint."""
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
        Alternatively, define a plain (non-async) setup(bot) for manual control."""
        import importlib
        import inspect

        from .cog import Cog as _Cog

        module = importlib.import_module(name)
        setup_fn = getattr(module, "setup", None)
        # a coroutine function named `setup` is a command handler that
        # collided with the hook's name, not the hook itself - setup(bot)
        # is always called synchronously, so an async one could never have
        # actually run
        if callable(setup_fn) and not inspect.iscoroutinefunction(setup_fn):
            setup_fn(self)
            return
        seen = set()
        cogs = []
        for v in vars(module).values():
            if isinstance(v, _Cog) and id(v) not in seen:
                seen.add(id(v))
                cogs.append(v)
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
                    _prewarm_defer()
                _validate_command_name(kwargs["name"])
                resolved_options = kwargs["options"]
                if resolved_options is None:
                    resolved_options = options_from_signature(func)
                self.router.register_command(
                    kwargs["name"],
                    func,
                    description=kwargs["description"],
                    options=resolved_options,
                    dm_permission=kwargs["dm_permission"],
                    default_member_permissions=kwargs.get("default_member_permissions"),
                    nsfw=kwargs.get("nsfw", False),
                    guild_ids=kwargs.get("guild_ids"),
                    user_installable=kwargs.get("user_installable", False),
                )
            elif ctype == "button":
                if kwargs.get("defer"):
                    func._defer = True
                    _prewarm_defer()
                self.router.register_button(kwargs["custom_id"], func)
            elif ctype == "select":
                if kwargs.get("defer"):
                    func._defer = True
                    _prewarm_defer()
                self.router.register_select(kwargs["custom_id"], func)
            elif ctype == "modal":
                if kwargs.get("defer"):
                    func._defer = True
                    _prewarm_defer()
                self.router.register_modal(kwargs["custom_id"], func)
            elif ctype == "autocomplete":
                self.router.register_autocomplete(kwargs["cmd_name"], kwargs["option_name"], func)
            elif ctype == "user_command":
                self.router.register_command(
                    kwargs["name"],
                    func,
                    description=None,
                    options=[],
                    dm_permission=kwargs["dm_permission"],
                    cmd_type=2,
                    guild_ids=kwargs.get("guild_ids"),
                    user_installable=kwargs.get("user_installable", False),
                )
            elif ctype == "message_command":
                self.router.register_command(
                    kwargs["name"],
                    func,
                    description=None,
                    options=[],
                    dm_permission=kwargs["dm_permission"],
                    cmd_type=3,
                    guild_ids=kwargs.get("guild_ids"),
                    user_installable=kwargs.get("user_installable", False),
                )

    def sync_commands(self, bot_token=None, client_id=None, client_secret=None, guild_id=None):
        """Push this bot's registered commands to Discord.

        Authenticate with a bot token, or with client_id + client_secret via
        OAuth2 client credentials (no bot user required). Run this from a
        deploy step, not from inside the Lambda handler, since it makes
        blocking network calls to Discord's API.

        Omit `guild_id` (the default) to sync each command to its own scope:
        global by default, or whichever guild(s) `@bot.command(guild_ids=...)`
        named, all in this one call. Pass `guild_id` to override every
        command's own scope and push the full set to just that guild
        instead, for instant updates during development.
        """
        if guild_id:
            return sync_commands(
                self.router.command_definitions(),
                guild_id=guild_id,
                bot_token=bot_token,
                client_id=client_id,
                client_secret=client_secret,
            )

        registered = sync_commands(
            self.router.scoped_command_definitions(None),
            guild_id=None,
            bot_token=bot_token,
            client_id=client_id,
            client_secret=client_secret,
        )
        for gid in self.router.guild_ids():
            registered += sync_commands(
                self.router.scoped_command_definitions(gid),
                guild_id=gid,
                bot_token=bot_token,
                client_id=client_id,
                client_secret=client_secret,
            )
        return registered


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
