"""Test helpers for cordless bots: build interaction payloads and dispatch
them through the real router - the same code path a deployed bot runs on -
without a live Discord round-trip or HTTP signature verification."""

import json

from .context import Context

_APPLICATION_COMMAND = 2
_MESSAGE_COMPONENT = 3

_SUB_COMMAND = 1
_SUB_COMMAND_GROUP = 2

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


def _shell(
    itype,
    data,
    *,
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
    user = {"id": user_id, "username": username}
    shell = {
        "id": interaction_id,
        "type": itype,
        "token": token,
        "data": data,
        "member": {"user": user} if guild_id else None,
        "user": None if guild_id else user,
        "guild_id": guild_id,
        "guild": (guild or {"id": guild_id}) if guild_id else None,
        "channel_id": channel_id,
        "locale": locale,
    }
    if message is not None:
        shell["message"] = message
    return shell


def make_command_interaction(
    name,
    options=None,
    *,
    target_id=None,
    target_type=None,
    resolved=None,
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

    Pass `target_id` (and optionally `resolved`, Discord's target object
    block) to build a user/message context menu command instead of a slash
    command - `target_type` picks user (2, default) vs message (3).

    When `guild_id` is set, `ctx.guild` is populated too: pass `guild` to
    supply Discord's partial guild object (only `id`, `locale`, and
    `features` are ever present there - see `ctx.guild`'s docstring), or
    leave it unset for a minimal `{"id": guild_id}` default.
    """
    parts = name.split("/")
    leaf_options = _options_list(options)

    data = {"name": parts[0]}
    if leaf_options or len(parts) > 1:
        data["options"] = _nest_command_path(parts, leaf_options)

    if target_id is not None:
        data["target_id"] = target_id
        data["resolved"] = resolved or {}
        data["type"] = target_type or 2
    else:
        data["type"] = 1

    return _shell(
        _APPLICATION_COMMAND,
        data,
        user_id=user_id,
        username=username,
        guild_id=guild_id,
        guild=guild,
        channel_id=channel_id,
        locale=locale,
        interaction_id=interaction_id,
        token=token,
    )


def make_component_interaction(
    custom_id,
    values=None,
    component_type=2,
    *,
    message=None,
    user_id="1",
    username="shiv",
    guild_id=None,
    guild=None,
    channel_id="1",
    locale="en-US",
    interaction_id="1",
    token="test-token",
):
    """Build a raw MESSAGE_COMPONENT interaction payload, as if a user
    clicked a button or picked from a select with this `custom_id`.

    `component_type` follows Discord's numbering: 2 is a button (the
    default), 3 a string select, 5/6/7/8 user/role/mentionable/channel
    selects. Pass `values` for a select (the picked ids or strings) - it
    lands on `ctx.values`. Prefix-matched custom ids ("shop:item1") work the
    same as in production: the handler is looked up by the part before the
    first ":".

    Pass `message` (Discord's message object the component sits on) to make
    it available as `ctx.message`.
    """
    data = {"custom_id": custom_id, "component_type": component_type}
    if values is not None:
        data["values"] = values

    return _shell(
        _MESSAGE_COMPONENT,
        data,
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


async def invoke(bot, interaction_or_name, options=None, **kwargs):
    """Dispatch an interaction through `bot`'s real router - the same
    dispatch call a deployed Lambda makes - and return the decoded response
    Discord would receive (e.g. `{"type": 4, "data": {"content": "pong"}}`),
    so assertions run against your actual handler code, not a mock of it.

    `interaction_or_name` is either a command name, built into an
    interaction via `make_command_interaction` (forwarding `options` and any
    other keyword args), or a fully custom interaction dict from
    `make_command_interaction` or `make_component_interaction`, for anything
    the shorthand doesn't cover (buttons, selects, context menu commands, a
    specific guild/user, ...).

    There's no HTTP request here, so signature verification never runs -
    this works the same whether or not the bot was constructed with a real
    DISCORD_PUBLIC_KEY.
    """
    if isinstance(interaction_or_name, str):
        interaction = make_command_interaction(interaction_or_name, options, **kwargs)
    else:
        interaction = interaction_or_name

    ctx = Context(interaction)
    response = await bot.router.dispatch(interaction, ctx)
    if response is None:
        return None
    return json.loads(response["body"])
