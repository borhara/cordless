"""Test helpers for cordless bots: build interaction payloads and dispatch
them through the real router - the same code path a deployed bot runs on -
without a live Discord round-trip or HTTP signature verification.

Import the module and use it as a namespace, e.g.:

    from cordless import testing

    response, ctx = await testing.invoke(bot, testing.command("ping"))
"""

import json

from .context import Context

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


def _option_type(value):
    for py_type, discord_type in _ANNOTATION_TYPES:
        if type(value) is py_type:
            return discord_type
    return 3


def _options_list(options):
    return [{"name": name, "type": _option_type(value), "value": value} for name, value in (options or {}).items()]


def _nest_command_path(parts, leaf_options):
    """ "name", "parent/sub", "parent/group/sub" -> nested SUB_COMMAND(_GROUP)
    option trees, matching what router._resolve_command_key expects."""
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


def member(user_id="1", username="shiv", roles=None, permissions=None, nick=None):
    """Build a partial guild member object for the `member` kwarg on the
    other builders below, so `ctx.member.roles`/`ctx.member.permissions`
    are populated instead of just `ctx.user`.

    `roles` is a list of role ids. `permissions` is a `Permissions`
    instance (or a raw integer bitfield) - see `cordless.Permissions`.
    """
    data = {"user": {"id": user_id, "username": username}, "roles": roles or []}
    if permissions is not None:
        data["permissions"] = str(int(permissions))
    if nick is not None:
        data["nick"] = nick
    return data


def _shell(
    itype,
    data,
    *,
    member=None,
    user_id,
    username,
    guild_id,
    guild,
    channel_id,
    locale,
    interaction_id,
    token,
    message=None,
):
    """The fields common to every interaction type, regardless of what's in `data`."""
    if member is not None and guild_id is None:
        guild_id = "1"
    user = {"id": user_id, "username": username}
    shell = {
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
    name,
    options=None,
    *,
    target=None,
    target_type=None,
    member=None,
    user_id="1",
    username="shiv",
    guild_id=None,
    guild=None,
    channel_id="1",
    locale="en-US",
    interaction_id="1",
    token="test-token",
):
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

    data = {"name": parts[0]}
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
    custom_id,
    component_type,
    *,
    values=None,
    resolved=None,
    message=None,
    member=None,
    user_id="1",
    username="shiv",
    guild_id=None,
    guild=None,
    channel_id="1",
    locale="en-US",
    interaction_id="1",
    token="test-token",
):
    data = {"custom_id": custom_id, "component_type": component_type}
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


def button(custom_id, **kwargs):
    """Build a raw MESSAGE_COMPONENT interaction payload, as if a user
    clicked a button with this `custom_id`. Prefix-matched custom ids
    ("shop:item1") work the same as in production: the handler is looked up
    by the part before the first ":".

    Pass `message` (Discord's message object the button sits on) to make it
    available as `ctx.message`, and `member` (see `member()`) for a member
    with roles/permissions.
    """
    return _component(custom_id, 2, **kwargs)


def select(custom_id, values=None, kind="string", **kwargs):
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
    ids = []
    resolved = {}
    for value in values or []:
        if isinstance(value, dict) and resolved_key:
            ids.append(value["id"])
            resolved.setdefault(resolved_key, {})[value["id"]] = value
        else:
            ids.append(value)

    return _component(custom_id, _SELECT_KINDS[kind], values=ids, resolved=resolved or None, **kwargs)


def modal(
    custom_id,
    values=None,
    *,
    member=None,
    user_id="1",
    username="shiv",
    guild_id=None,
    guild=None,
    channel_id="1",
    locale="en-US",
    interaction_id="1",
    token="test-token",
):
    """Build a raw MODAL_SUBMIT interaction payload, as if a user filled in
    and submitted a modal with this `custom_id`.

    `values` is a plain {component_custom_id: text} dict - one action row
    per component, matching how `ctx.modal_values` flattens them regardless
    of the actual row layout.
    """
    components = [
        {"type": 1, "components": [{"type": 4, "custom_id": cid, "value": value}]}
        for cid, value in (values or {}).items()
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
    name,
    options=None,
    focused=None,
    *,
    member=None,
    user_id="1",
    username="shiv",
    guild_id=None,
    guild=None,
    channel_id="1",
    locale="en-US",
    interaction_id="1",
    token="test-token",
):
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

    data = {"name": parts[0], "type": 1}
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


async def invoke(bot, interaction_or_name, options=None, **kwargs):
    """Dispatch an interaction through `bot`'s real router - the same
    dispatch call a deployed Lambda makes - and return `(response, ctx)`:
    the decoded response Discord would receive (e.g. `{"type": 4, "data":
    {"content": "pong"}}`), and the `Context` the handler ran with, so
    assertions can check `ctx.member.permissions`, `ctx.custom_id_args`, and
    so on, not just the response.

    `interaction_or_name` is either a command name, built into an
    interaction via `command()` (forwarding `options` and any other keyword
    args), or a fully custom interaction dict from `command()`, `button()`,
    `select()`, `modal()`, or `autocomplete()`, for anything the shorthand
    doesn't cover.

    There's no HTTP request here, so signature verification never runs -
    this works the same whether or not the bot was constructed with a real
    DISCORD_PUBLIC_KEY.
    """
    if isinstance(interaction_or_name, str):
        interaction = command(interaction_or_name, options, **kwargs)
    else:
        interaction = interaction_or_name

    ctx = Context(interaction)
    raw = await bot.router.dispatch(interaction, ctx)
    if raw is None or "body" not in raw:
        return raw, ctx
    return json.loads(raw["body"]), ctx
