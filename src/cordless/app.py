import asyncio
import base64
import inspect
import json
import os
import re
from typing import Literal, Union, get_args, get_origin

from ._rest._mixin import RESTMixin
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


_MAX_OPTIONS = 25
_MAX_CHOICES = 25


def _validate_command_name(name):
    """Fail at decoration time instead of with a cryptic Discord API error at register time."""
    for part in name.split("/"):
        if not _NAME_RE.fullmatch(part):
            raise ValueError(f"Invalid command name {name!r}: Discord requires 1-32 lowercase letters, digits, - or _")


def _check_description(where, text):
    """Discord requires a 1 to 100 character description on chat-input
    commands and every option. An empty or overlong one is otherwise only
    caught by a positional Invalid Form Body error at register time."""
    length = 0 if text is None else len(text)
    if not 1 <= length <= 100:
        raise ValueError(f"{where}: description must be 1 to 100 characters, got {length}")


def _validate_command_shape(name, description, options, group_description=None):
    """Decoration-time checks for the static limits that produce opaque
    Discord errors: description lengths, option names, and the 25-item caps
    on options and choices. Every message names the command."""
    _check_description(f"Command {name!r}", description)
    if group_description is not None:
        _check_description(f"Command {name!r} group", group_description)

    if len(options) > _MAX_OPTIONS:
        raise ValueError(f"Command {name!r} has {len(options)} options, Discord allows at most {_MAX_OPTIONS}")

    for opt in options:
        opt_name = opt.get("name", "")
        if not _NAME_RE.fullmatch(opt_name):
            raise ValueError(
                f"Command {name!r}: invalid option name {opt_name!r}, "
                "Discord requires 1-32 lowercase letters, digits, - or _"
            )
        _check_description(f"Command {name!r} option {opt_name!r}", opt.get("description"))

        choices = opt.get("choices") or []
        if len(choices) > _MAX_CHOICES:
            raise ValueError(
                f"Command {name!r} option {opt_name!r} has {len(choices)} choices, "
                f"Discord allows at most {_MAX_CHOICES}"
            )
        for ch in choices:
            ch_name = ch.get("name")
            if ch_name is None or not 1 <= len(str(ch_name)) <= 100:
                raise ValueError(
                    f"Command {name!r} option {opt_name!r}: choice name must be 1 to 100 characters, got {ch_name!r}"
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

        opt: dict = {"name": p.name, "description": "No description provided."}

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


def choice(name, value, name_localizations=None):
    """Build a single choice dict for `option(choices=[...])`.
    `name_localizations` is a `{locale: name}` dict, e.g. `{"es-ES": "Rojo"}`
    - choices have no description, so there's no `description_localizations`."""
    c = {"name": name, "value": value}
    if name_localizations is not None:
        c["name_localizations"] = name_localizations
    return c


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
    channel_types=None,
    name_localizations=None,
    description_localizations=None,
):
    """Build a Discord application command option dict, for `@bot.command(options=[...])`.

    | Parameter | |
    |---|---|
    | `type` | `"string"`, `"integer"`, `"number"`, `"boolean"`, `"user"`, `"channel"`, `"role"`, `"attachment"` |
    | `required` | Default `False`, note this is the opposite default from inferred options, where a parameter without a default value is required |
    | `autocomplete` | Pair with `@bot.autocomplete` |
    | `choices` | List of `{"name": label, "value": value}` dicts (build with `choice()` for per-choice localization); the user must pick one |
    | `min_value` / `max_value` | Bounds for `integer`/`number` options |
    | `min_length` / `max_length` | Length bounds for `string` options |
    | `channel_types` | Restrict a `channel` option to specific Discord channel type ints, e.g. `[0, 2]` for text + voice |
    | `name_localizations` | `{locale: name}` dict for this option's per-locale name, e.g. `{"es-ES": "cantidad"}` |
    | `description_localizations` | `{locale: description}` dict, same shape as `name_localizations` |
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
    if channel_types is not None:
        opt["channel_types"] = channel_types
    if name_localizations is not None:
        opt["name_localizations"] = name_localizations
    if description_localizations is not None:
        opt["description_localizations"] = description_localizations
    return opt


class Cordless(RESTMixin):
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
        name_localizations=None,
        description_localizations=None,
        group_description=None,
        group_name_localizations=None,
        group_description_localizations=None,
        parent_name_localizations=None,
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
        | `user_installable` | `True` lets users install this command to their own account and run it in any server or DM, alongside the normal guild install. `"only"` drops the guild install, so it's never a server-wide command, only usable by users who've installed it themselves |
        | `name_localizations` | `{locale: name}` dict for Discord's per-locale command picker, e.g. `{"es-ES": "comprar"}` |
        | `description_localizations` | `{locale: description}` dict, same shape as `name_localizations` |
        | `group_description` | For a `parent/group/sub` path, the description shown on the auto-created group. Only the first subcommand registered under a given group needs to set it |
        | `group_name_localizations` | `{locale: name}` dict for the auto-created group's name. Only the first subcommand registered under a given group needs to set it |
        | `group_description_localizations` | `{locale: description}` dict for the auto-created group's description, same rule as `group_name_localizations` |
        | `parent_name_localizations` | For a `parent/sub` or `parent/group/sub` path, `{locale: name}` for the auto-created parent's name. Doesn't leak in from a subcommand's own `name_localizations`, so set it explicitly; only the first subcommand registered needs to set it |
        """
        _validate_command_name(name)

        def decorator(func):
            _options = options if options is not None else options_from_signature(func)
            _validate_command_shape(name, description, _options, group_description)
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
                name_localizations=name_localizations,
                description_localizations=description_localizations,
                group_description=group_description,
                group_name_localizations=group_name_localizations,
                group_description_localizations=group_description_localizations,
                parent_name_localizations=parent_name_localizations,
            )
            return func

        return decorator

    async def _discord_request(self, method, path, payload=None, files=None):
        from ._rest import _client

        return await _client.request_raw(method, path, payload, files, token=os.environ["DISCORD_BOT_TOKEN"])

    async def send_message(self, channel_id, content=None, *, embeds=None, components=None, files=None):
        """Send a message as the bot. Requires `DISCORD_BOT_TOKEN`, callable
        from anywhere with no interaction to respond to, typically cron
        handlers. `files` is a list of `(filename, bytes)` tuples, same as
        `ctx.send`/`ctx.edit`. Returns the sent `Message`. For replies,
        polls, stickers or other fields Create Message supports, use
        `channel.send()` instead."""
        from ._rest import messages

        return await messages.create_message(
            channel_id, content=content, embeds=embeds, components=components, files=files
        )

    async def edit_message(self, channel_id, message_id, content=None, *, embeds=None, components=None, files=None):
        """Edit a message the bot previously sent. Requires
        `DISCORD_BOT_TOKEN`. `files` is a list of `(filename, bytes)`
        tuples, same as `ctx.send`/`ctx.edit`. Returns the edited `Message`.
        `content`/`embeds`/`components` left at their default here just
        leave that field untouched, they can't be cleared through this
        method, use `message.edit(field=None)` for that."""
        from ._rest import messages
        from ._rest._client import UNSET

        return await messages.edit_channel_message(
            channel_id,
            message_id,
            content=content if content is not None else UNSET,
            embeds=embeds if embeds is not None else UNSET,
            components=components if components is not None else UNSET,
            files=files,
        )

    async def delete_message(self, channel_id, message_id):
        """Delete a message. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import messages

        await messages.delete_channel_message(channel_id, message_id)

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

    async def fetch_webhook_message(self, webhook_id, webhook_token=None, message_id="@original"):
        """Fetch a message previously sent through a webhook. No bot token required."""
        from . import webhook as _webhook
        from .models import Message

        if webhook_token is None:
            webhook_id, webhook_token = _webhook.parse_webhook_url(webhook_id)

        _, body = await asyncio.get_event_loop().run_in_executor(
            None, _webhook.get_message, webhook_id, webhook_token, message_id
        )
        return Message(json.loads(body))

    async def fetch_webhook_with_token(self, webhook_id, webhook_token=None):
        """Fetch a webhook using its own token rather than DISCORD_BOT_TOKEN.
        The returned object omits the owning user, unlike `fetch_webhook`."""
        from . import webhook as _webhook
        from ._rest.models import Webhook

        if webhook_token is None:
            webhook_id, webhook_token = _webhook.parse_webhook_url(webhook_id)

        _, body = await asyncio.get_event_loop().run_in_executor(None, _webhook.get_webhook, webhook_id, webhook_token)
        return Webhook(json.loads(body))

    async def edit_webhook_with_token(self, webhook_id, webhook_token=None, *, name=..., avatar=...):
        """Rename a webhook or change its avatar using its own token rather
        than DISCORD_BOT_TOKEN. Unlike `edit_webhook`, this can't move it to
        a different channel. avatar can be cleared by passing None."""
        from . import webhook as _webhook
        from ._rest.models import Webhook

        if webhook_token is None:
            webhook_id, webhook_token = _webhook.parse_webhook_url(webhook_id)

        _, body = await asyncio.get_event_loop().run_in_executor(
            None,
            _webhook.edit_webhook,
            webhook_id,
            webhook_token,
            _webhook.UNSET if name is ... else name,
            _webhook.UNSET if avatar is ... else avatar,
        )
        return Webhook(json.loads(body))

    async def execute_slack_webhook(self, webhook_id, webhook_token=None, payload=None, *, wait=False, thread_id=None):
        """Post a Slack-formatted payload through a webhook. No bot token
        required. Discord's Slack-compatible endpoint replies with the plain
        text "ok" rather than a message body, so unlike execute_webhook this
        returns that raw text with wait=True, not a parsed message."""
        from . import webhook as _webhook

        if webhook_token is None:
            webhook_id, webhook_token = _webhook.parse_webhook_url(webhook_id)

        _, body = await asyncio.get_event_loop().run_in_executor(
            None, _webhook.execute_slack_compatible, webhook_id, webhook_token, payload, wait, thread_id
        )
        if wait and body:
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return body.decode()

    async def execute_github_webhook(self, webhook_id, webhook_token=None, payload=None, *, wait=False, thread_id=None):
        """Post a GitHub-formatted payload through a webhook. No bot token required."""
        from . import webhook as _webhook

        if webhook_token is None:
            webhook_id, webhook_token = _webhook.parse_webhook_url(webhook_id)

        _, body = await asyncio.get_event_loop().run_in_executor(
            None, _webhook.execute_github_compatible, webhook_id, webhook_token, payload, wait, thread_id
        )
        if wait and body:
            return json.loads(body)

    async def add_role(self, guild_id, user_id, role_id, *, reason=None):
        """Grant a role to a guild member. Requires `DISCORD_BOT_TOKEN`.
        Same as `add_guild_member_role`, kept under its older name."""
        from ._rest import members

        await members.add_guild_member_role(guild_id, user_id, role_id, reason=reason)

    async def remove_role(self, guild_id, user_id, role_id, *, reason=None):
        """Remove a role from a guild member. Requires `DISCORD_BOT_TOKEN`.
        Same as `remove_guild_member_role`, kept under its older name."""
        from ._rest import members

        await members.remove_guild_member_role(guild_id, user_id, role_id, reason=reason)

    async def create_webhook(self, channel_id, name, avatar=None, *, reason=None):
        """Create a webhook in a channel. Requires DISCORD_BOT_TOKEN. Returns the
        webhook object, including the id/token pair execute_webhook needs."""
        from ._rest import webhooks
        from ._rest._client import UNSET

        webhook = await webhooks.create_webhook(
            channel_id, name, avatar=avatar if avatar is not None else UNSET, reason=reason
        )
        return webhook._data

    async def get_channel_webhooks(self, channel_id):
        """List a channel's webhooks. Requires DISCORD_BOT_TOKEN."""
        from ._rest import webhooks

        result = await webhooks.fetch_channel_webhooks(channel_id)
        return [webhook._data for webhook in result]

    async def delete_webhook(self, webhook_id, webhook_token=None, *, reason=None):
        """Delete a webhook. With webhook_token, authenticates with the webhook's
        own token (no bot token needed); otherwise uses DISCORD_BOT_TOKEN.
        reason only takes effect on the bot-token path - webhook.py's
        token-authenticated request helper doesn't send that header at all."""
        if webhook_token is not None:
            from . import webhook as _webhook

            await asyncio.get_event_loop().run_in_executor(None, _webhook.delete_webhook, webhook_id, webhook_token)
            return

        from ._rest import webhooks

        await webhooks.delete_webhook(webhook_id, reason=reason)

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

    def user_command(
        self,
        name,
        dm_permission=True,
        default_member_permissions=None,
        nsfw=False,
        guild_ids=None,
        user_installable=False,
        name_localizations=None,
    ):
        """Register a User context menu command (right-click → Apps → name).

        `name_localizations` is a `{locale: name}` dict, e.g. `{"es-ES": "inspeccionar"}`
        - context menu commands have no description, so there is no `description_localizations`.
        """

        def decorator(func):
            self.router.register_command(
                name,
                func,
                description=None,
                options=[],
                dm_permission=dm_permission,
                default_member_permissions=default_member_permissions,
                nsfw=nsfw,
                cmd_type=2,
                guild_ids=guild_ids,
                user_installable=user_installable,
                name_localizations=name_localizations,
            )
            return func

        return decorator

    def message_command(
        self,
        name,
        dm_permission=True,
        default_member_permissions=None,
        nsfw=False,
        guild_ids=None,
        user_installable=False,
        name_localizations=None,
    ):
        """Register a Message context menu command (right-click message → Apps → name).

        `name_localizations` is a `{locale: name}` dict, e.g. `{"es-ES": "inspeccionar"}`
        - context menu commands have no description, so there is no `description_localizations`.
        """

        def decorator(func):
            self.router.register_command(
                name,
                func,
                description=None,
                options=[],
                dm_permission=dm_permission,
                default_member_permissions=default_member_permissions,
                nsfw=nsfw,
                cmd_type=3,
                guild_ids=guild_ids,
                user_installable=user_installable,
                name_localizations=name_localizations,
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

    def route(self, method, path):
        """Register a raw HTTP handler on the same Lambda, outside the
        Discord interaction flow.

        Use it for requests that must reach this function without Discord
        signature verification: incoming webhooks from other services, OAuth
        redirect callbacks, health checks. The handler is called as
        `handler(event, bot)` with the raw Lambda event and this instance,
        so it can reuse `send_message`, `execute_webhook`, and the rest.

        `path` may contain `{name}` segments; matched values arrive on
        `event["pathParameters"]`. A trailing `{name+}` captures the rest of
        the path. The handler may return a string, a dict or list (sent as
        JSON), a status int, a `(status, body)` or `(status, body, headers)`
        tuple, or a full Lambda proxy dict.

        Works on either endpoint. On the default Function URL every path
        reaches the function and cordless does the matching. Setting
        `endpoint = "api_gateway"` adds edge 404s for unknown paths and
        makes `cordless deploy` sync these routes onto the API alongside the
        Discord commands.
        """

        def decorator(func):
            self.router.register_route(method, path, func)
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
        if self.router.routes:
            response = self._try_route(event)
            if response is not None:
                return response

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
            print(f"[cordless] {exc.__class__.__name__}: {exc}")
            return _json_response(400, {"error": str(exc)})

    def _try_route(self, event):
        """Dispatch `event` to a matching `@bot.route` handler. Returns the
        response dict, or `None` when the event is a Discord interaction and
        should fall through to the normal path."""
        from .routes import build_response, request_method_path

        method, path = request_method_path(event)
        if method is None or (method == "POST" and path == "/"):
            return None

        match = self.router.match_route(method, path)
        if match is None:
            return _json_response(404, {"error": f"no route for {method} {path}"})

        handler, params = match
        route_event = dict(event)
        route_event["pathParameters"] = {**(event.get("pathParameters") or {}), **params}
        try:
            result = asyncio.run(handler(route_event, self))
        except CordlessError as exc:
            print(f"[cordless] {exc.__class__.__name__}: {exc}")
            return _json_response(400, {"error": str(exc)})
        except Exception:
            import traceback

            traceback.print_exc()
            return _json_response(500, {"error": "route handler raised an exception"})
        return build_response(result)

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
                _validate_command_shape(
                    kwargs["name"], kwargs["description"], resolved_options, kwargs.get("group_description")
                )
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
                    name_localizations=kwargs.get("name_localizations"),
                    description_localizations=kwargs.get("description_localizations"),
                    group_description=kwargs.get("group_description"),
                    group_name_localizations=kwargs.get("group_name_localizations"),
                    group_description_localizations=kwargs.get("group_description_localizations"),
                    parent_name_localizations=kwargs.get("parent_name_localizations"),
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
            elif ctype == "route":
                self.router.register_route(kwargs["method"], kwargs["path"], func)
            elif ctype == "user_command":
                self.router.register_command(
                    kwargs["name"],
                    func,
                    description=None,
                    options=[],
                    dm_permission=kwargs["dm_permission"],
                    default_member_permissions=kwargs.get("default_member_permissions"),
                    nsfw=kwargs.get("nsfw", False),
                    cmd_type=2,
                    guild_ids=kwargs.get("guild_ids"),
                    user_installable=kwargs.get("user_installable", False),
                    name_localizations=kwargs.get("name_localizations"),
                )
            elif ctype == "message_command":
                self.router.register_command(
                    kwargs["name"],
                    func,
                    description=None,
                    options=[],
                    dm_permission=kwargs["dm_permission"],
                    default_member_permissions=kwargs.get("default_member_permissions"),
                    nsfw=kwargs.get("nsfw", False),
                    cmd_type=3,
                    guild_ids=kwargs.get("guild_ids"),
                    user_installable=kwargs.get("user_installable", False),
                    name_localizations=kwargs.get("name_localizations"),
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
