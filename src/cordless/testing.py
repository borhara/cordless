"""Test helpers for cordless bots: build interaction payloads and dispatch
them through the real router - the same code path a deployed bot runs on -
without a live Discord round-trip or HTTP signature verification.

Import the module and use it as a namespace, e.g.:

    from cordless import testing

    response, ctx = await testing.invoke(bot, testing.command("ping"))
"""

import base64
import json
import urllib.parse
from typing import Any, NamedTuple, cast

from ._multipart import parse_multipart_payload
from .context import Context
from .routes import build_response, normalize_path


class RouteResponse(NamedTuple):
    status: int
    body: Any
    headers: Any


_APPLICATION_COMMAND = 2
_MESSAGE_COMPONENT = 3
_APPLICATION_COMMAND_AUTOCOMPLETE = 4
_MODAL_SUBMIT = 5

_SUB_COMMAND = 1
_SUB_COMMAND_GROUP = 2

_SELECT_KINDS = {"string": 3, "user": 5, "role": 6, "mentionable": 7, "channel": 8}
_SELECT_RESOLVED_KEYS = {"user": "users", "role": "roles", "channel": "channels"}

# order matters: bool must be checked before int (bool is an int subclass)
_ANNOTATION_TYPES = [(bool, 5), (int, 4), (float, 10), (str, 3)]


def _option_type(value: Any) -> int:
    for py_type, discord_type in _ANNOTATION_TYPES:
        if type(value) is py_type:
            return discord_type
    return 3


def _options_list(options: Any) -> list[dict[str, Any]]:
    src: dict[str, Any] = cast("dict[str, Any]", options or {})
    return [{"name": name, "type": _option_type(value), "value": value} for name, value in src.items()]


def _nest_command_path(parts: list[str], leaf_options: Any) -> Any:
    """ "name", "parent/sub", "parent/group/sub" -> nested SUB_COMMAND(_GROUP)
    option trees, matching what router.resolve_command_key expects."""
    if len(parts) == 1:
        return leaf_options
    if len(parts) == 2:
        return [{"name": parts[1], "type": _SUB_COMMAND, "options": leaf_options}]
    if len(parts) == 3:
        return [
            {
                "name": parts[1],
                "type": _SUB_COMMAND_GROUP,
                "options": [{"name": parts[2], "type": _SUB_COMMAND, "options": leaf_options}],
            }
        ]
    raise ValueError(f"Command path {'/'.join(parts)!r} is too deep: expected name, name/sub, or name/group/sub")


def member(
    user_id: str = "1",
    username: str = "test-user",
    roles: Any = None,
    permissions: Any = None,
    nick: str | None = None,
) -> dict[str, Any]:
    """Build a partial guild member object for the `member` kwarg on the
    other builders below, so `ctx.member.roles`/`ctx.member.permissions`
    are populated instead of just `ctx.user`.

    `roles` is a list of role ids. `permissions` is a `Permissions`
    instance (or a raw integer bitfield) - see `cordless.Permissions`.
    """
    data: dict[str, Any] = {"user": {"id": user_id, "username": username}, "roles": roles or []}
    if permissions is not None:
        data["permissions"] = str(int(permissions))
    if nick is not None:
        data["nick"] = nick
    return data


def _shell(
    itype: int,
    data: dict[str, Any],
    *,
    member: Any = None,
    user_id: str,
    username: str,
    guild_id: str | None,
    guild: Any,
    channel_id: str,
    locale: str,
    interaction_id: str,
    token: str,
    message: Any = None,
) -> dict[str, Any]:
    """The fields common to every interaction type, regardless of what's in `data`."""
    if member is not None and guild_id is None:
        guild_id = "1"
    user = {"id": user_id, "username": username}
    shell: dict[str, Any] = {
        "id": interaction_id,
        "type": itype,
        "token": token,
        "data": data,
        "member": member if member is not None else ({"user": user} if guild_id else None),
        "user": None if guild_id else user,
        "guild_id": guild_id,
        "guild": (guild or {"id": guild_id}) if guild_id else None,
        "channel_id": channel_id,
        "locale": locale,
    }
    if message is not None:
        shell["message"] = message
    return shell


def command(
    name: str,
    options: Any = None,
    *,
    target: Any = None,
    target_type: Any = None,
    member: Any = None,
    user_id: str = "1",
    username: str = "test-user",
    guild_id: str | None = None,
    guild: Any = None,
    channel_id: str = "1",
    locale: str = "en-US",
    interaction_id: str = "1",
    token: str = "test-token",
) -> dict[str, Any]:
    """Build a raw APPLICATION_COMMAND interaction payload, as if a user
    typed `name` with `options` in Discord.

    `name` accepts the same "name", "parent/sub", and "parent/group/sub"
    paths @bot.command does. `options` is a plain {name: value} dict; the
    Discord option type is inferred from each value's Python type (str,
    int, bool, float).

    Pass `target` (the actual user or message object you want resolved) to
    build a context menu command instead of a slash command - its `id` and
    the object itself are wired into `data.target_id`/`data.resolved`
    automatically. `target_type` picks user (2, default) vs message (3).

    Pass `member` (see `member()`) for a member with roles/permissions
    instead of the plain `user_id`/`username` default.

    When `guild_id` is set (or implied by `member`), `ctx.guild` is
    populated too: pass `guild` to supply Discord's partial guild object
    (only `id`, `locale`, and `features` are ever present there - see
    `ctx.guild`'s docstring), or leave it unset for a minimal
    `{"id": guild_id}` default.
    """
    parts = name.split("/")
    leaf_options = _options_list(options)

    data: dict[str, Any] = {"name": parts[0]}
    if leaf_options or len(parts) > 1:
        data["options"] = _nest_command_path(parts, leaf_options)

    if target is not None:
        target_id = target["id"]
        ttype = target_type or 2
        data["type"] = ttype
        data["target_id"] = target_id
        data["resolved"] = {"messages" if ttype == 3 else "users": {target_id: target}}
    else:
        data["type"] = 1

    return _shell(
        _APPLICATION_COMMAND,
        data,
        member=member,
        user_id=user_id,
        username=username,
        guild_id=guild_id,
        guild=guild,
        channel_id=channel_id,
        locale=locale,
        interaction_id=interaction_id,
        token=token,
    )


def _component(
    custom_id: str,
    component_type: int,
    *,
    values: Any = None,
    resolved: Any = None,
    message: Any = None,
    member: Any = None,
    user_id: str = "1",
    username: str = "test-user",
    guild_id: str | None = None,
    guild: Any = None,
    channel_id: str = "1",
    locale: str = "en-US",
    interaction_id: str = "1",
    token: str = "test-token",
) -> dict[str, Any]:
    data: dict[str, Any] = {"custom_id": custom_id, "component_type": component_type}
    if values is not None:
        data["values"] = values
    if resolved:
        data["resolved"] = resolved

    return _shell(
        _MESSAGE_COMPONENT,
        data,
        member=member,
        user_id=user_id,
        username=username,
        guild_id=guild_id,
        guild=guild,
        channel_id=channel_id,
        locale=locale,
        interaction_id=interaction_id,
        token=token,
        message=message,
    )


def button(custom_id: str, **kwargs: Any) -> dict[str, Any]:
    """Build a raw MESSAGE_COMPONENT interaction payload, as if a user
    clicked a button with this `custom_id`. Prefix-matched custom ids
    ("shop:item1") work the same as in production: the handler is looked up
    by the part before the first ":".

    Pass `message` (Discord's message object the button sits on) to make it
    available as `ctx.message`, and `member` (see `member()`) for a member
    with roles/permissions.
    """
    return _component(custom_id, 2, **kwargs)


def select(custom_id: str, values: Any = None, kind: str = "string", **kwargs: Any) -> dict[str, Any]:
    """Build a raw MESSAGE_COMPONENT interaction payload, as if a user
    picked from a select menu with this `custom_id`.

    `kind` picks the select type: "string" (default), "user", "role",
    "mentionable", or "channel". `values` is the picked ids as plain
    strings, matching `ctx.values` - or, for kind "user"/"role"/"channel",
    the actual resolved objects themselves, which get stitched into the
    payload's resolved block automatically (their `id` is pulled out for
    the plain-id list Discord itself sends). For "mentionable" (mixed users
    and roles), pass plain ids and build `resolved` yourself if you need it.
    """
    if kind not in _SELECT_KINDS:
        raise ValueError(f"Unknown select kind {kind!r}: expected one of {', '.join(_SELECT_KINDS)}")

    resolved_key = _SELECT_RESOLVED_KEYS.get(kind)
    ids: list[Any] = []
    resolved: dict[str, Any] = {}
    for value in cast("list[Any]", values or []):
        if isinstance(value, dict) and resolved_key:
            ids.append(value["id"])
            resolved.setdefault(resolved_key, {})[value["id"]] = value
        else:
            ids.append(value)

    return _component(custom_id, _SELECT_KINDS[kind], values=ids, resolved=resolved or None, **kwargs)


def modal(
    custom_id: str,
    values: Any = None,
    *,
    member: Any = None,
    user_id: str = "1",
    username: str = "test-user",
    guild_id: str | None = None,
    guild: Any = None,
    channel_id: str = "1",
    locale: str = "en-US",
    interaction_id: str = "1",
    token: str = "test-token",
) -> dict[str, Any]:
    """Build a raw MODAL_SUBMIT interaction payload, as if a user filled in
    and submitted a modal with this `custom_id`.

    `values` is a plain {component_custom_id: text} dict - one action row
    per component, matching how `ctx.modal_values` flattens them regardless
    of the actual row layout.
    """
    components = [
        {"type": 1, "components": [{"type": 4, "custom_id": cid, "value": value}]}
        for cid, value in cast("dict[str, Any]", values or {}).items()
    ]

    return _shell(
        _MODAL_SUBMIT,
        {"custom_id": custom_id, "components": components},
        member=member,
        user_id=user_id,
        username=username,
        guild_id=guild_id,
        guild=guild,
        channel_id=channel_id,
        locale=locale,
        interaction_id=interaction_id,
        token=token,
    )


def autocomplete(
    name: str,
    options: Any = None,
    focused: str | None = None,
    *,
    member: Any = None,
    user_id: str = "1",
    username: str = "test-user",
    guild_id: str | None = None,
    guild: Any = None,
    channel_id: str = "1",
    locale: str = "en-US",
    interaction_id: str = "1",
    token: str = "test-token",
) -> dict[str, Any]:
    """Build a raw APPLICATION_COMMAND_AUTOCOMPLETE interaction payload, as
    if a user is typing into an option's autocomplete field.

    `name` accepts the same "name", "parent/sub", and "parent/group/sub"
    paths as `command()`. `options` is a plain {name: value} dict, with the
    same type inference. `focused` names which option is currently being
    typed into - its value lands on `ctx.focused_value`.
    """
    parts = name.split("/")
    leaf_options = _options_list(options)
    if focused is not None:
        for opt in leaf_options:
            if opt["name"] == focused:
                opt["focused"] = True

    data: dict[str, Any] = {"name": parts[0], "type": 1}
    if leaf_options or len(parts) > 1:
        data["options"] = _nest_command_path(parts, leaf_options)

    return _shell(
        _APPLICATION_COMMAND_AUTOCOMPLETE,
        data,
        member=member,
        user_id=user_id,
        username=username,
        guild_id=guild_id,
        guild=guild,
        channel_id=channel_id,
        locale=locale,
        interaction_id=interaction_id,
        token=token,
    )


async def invoke(
    bot: Any, interaction_or_name: Any, options: Any = None, *, worker_mode: bool = False, **kwargs: Any
) -> tuple[dict[str, Any] | None, Context]:
    """Dispatch an interaction through `bot`'s real router - the same
    dispatch call a deployed Lambda makes - and return `(response, ctx)`:
    the decoded response Discord would receive (e.g. `{"type": 4, "data":
    {"content": "pong"}}`), and the `Context` the handler ran with, so
    assertions can check `ctx.member.permissions`, `ctx.custom_id_args`, and
    so on, not just the response. A handler that calls `ctx.send`/`ctx.edit`
    with `files=` gets its multipart response decoded back to the same
    plain dict shape, so `response["data"]` looks the same either way.

    `interaction_or_name` is either a command name, built into an
    interaction via `command()` (forwarding `options` and any other keyword
    args), or a fully custom interaction dict from `command()`, `button()`,
    `select()`, `modal()`, or `autocomplete()`, for anything the shorthand
    doesn't cover.

    Pass `worker_mode=True` to dispatch the way the worker Lambda does for a
    `defer=True` handler: the defer-to-worker step is skipped and the
    handler's real body runs directly, same as `cordless.worker.make_worker_
    handler` does in production. In this mode, a handler that calls
    `ctx.send`/`ctx.edit` makes a genuine followup PATCH request to Discord
    (`cordless.defer.patch_followup`) - patch that (or `post_followup`,
    `delete_original`) with `monkeypatch` if you want to assert on it
    without a live network call, the same way cordless's own test suite
    does for `defer.py`.

    There's no HTTP request for the initial dispatch itself, so signature
    verification never runs - this works the same whether or not the bot
    was constructed with a real DISCORD_PUBLIC_KEY.

    `@bot.cron` handlers aren't interaction-driven, so there's nothing to
    build here for them - call `bot.run_cron("name")` directly instead.
    """
    if isinstance(interaction_or_name, str):
        interaction = command(interaction_or_name, options, **kwargs)
    else:
        interaction = interaction_or_name

    ctx = Context(interaction, _worker_mode=worker_mode)
    raw = await bot.router.dispatch(interaction, ctx)
    if raw is None or "body" not in raw:
        return raw, ctx
    if raw.get("isBase64Encoded"):
        return parse_multipart_payload(base64.b64decode(raw["body"])), ctx
    return json.loads(raw["body"]), ctx


async def invoke_route(
    bot: Any, method: str, path: str, *, body: str = "", headers: Any = None, query: Any = None
) -> Any:
    """Dispatch a `@bot.route` handler and return a
    `RouteResponse(status, body, headers)`.

    The handler runs against the bot's real router, the same match a
    deployed Lambda makes, with no HTTP layer or signature check. `body` is
    decoded from JSON when the response content type is JSON, otherwise
    returned as text. An unmatched route yields a 404, matching the
    deployed behaviour.
    """
    method = method.upper()
    norm = normalize_path(path)
    match = bot.router.match_route(method, norm)
    if match is None:
        return RouteResponse(404, {"error": f"no route for {method} {norm}"}, {})

    handler, params = match
    query = dict(query or {})
    event = {
        "body": body,
        "headers": dict(headers or {}),
        "rawPath": norm,
        "rawQueryString": urllib.parse.urlencode(query),
        "queryStringParameters": query or None,
        "pathParameters": params,
        "requestContext": {"http": {"method": method, "path": norm}},
        "isBase64Encoded": False,
    }
    result = build_response(await handler(event, bot))
    out_headers = result.get("headers", {})
    raw = result.get("body", "")
    if result.get("isBase64Encoded"):
        decoded = base64.b64decode(raw)
    else:
        content_type = next((v for k, v in out_headers.items() if k.lower() == "content-type"), "")
        decoded = json.loads(raw) if raw and "application/json" in content_type else raw
    return RouteResponse(result["statusCode"], decoded, out_headers)
