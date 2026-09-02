import base64
import json
from typing import Any, cast

from ._base import _wrap
from ._multipart import build_multipart_body
from ._payload import (
    _FLAG_EPHEMERAL,
    _FLAG_UI_KIT,
    _attach_files,
    _contains_uikit,
    _validate_content_length,
    _validate_uikit,
    _with_guild_id,
)
from .models import Attachment, Channel, Guild, Member, Message, Role, User

_CHANNEL_MESSAGE_WITH_SOURCE = 4
_UPDATE_MESSAGE = 7
_DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE = 5
_DEFERRED_UPDATE_MESSAGE = 6
_AUTOCOMPLETE_RESULT = 8
_MODAL = 9


def _leaf_options(data: Any) -> Any:
    """Descend through subcommand/group wrappers to the actual value options."""
    options = data.get("options", [])
    while options and options[0].get("type") in (1, 2):
        options = options[0].get("options", [])
    return options


def _build_message_data(
    msg: Any,
    content: Any,
    embeds: Any,
    components: Any,
    ephemeral: bool = False,
    allowed_mentions: Any = None,
) -> dict[str, Any]:
    _content = content if content is not None else msg
    is_uikit = _contains_uikit(components)
    if is_uikit:
        _validate_uikit(_content, embeds, components)
    else:
        _validate_content_length(_content)

    data: dict[str, Any] = {}
    if _content is not None:
        data["content"] = _content
    if embeds is not None:
        data["embeds"] = [e.to_dict() if hasattr(e, "to_dict") else e for e in embeds]
    if components is not None:
        data["components"] = [c.to_dict() if hasattr(c, "to_dict") else c for c in components]
    if allowed_mentions is not None:
        data["allowed_mentions"] = allowed_mentions

    flags = 0
    if ephemeral:
        flags |= _FLAG_EPHEMERAL
    if is_uikit:
        flags |= _FLAG_UI_KIT
    if flags:
        data["flags"] = flags
    return data


def _wrap_members(members: Any, users: Any, guild_id: str | None) -> dict[str, Member]:
    """Discord's resolved.members entries omit the nested `user` object
    that's normally embedded on a member payload - it lives separately in
    resolved.users instead. Stitch it back in so `.user` works on a
    resolved `Member` the same way it does everywhere else."""
    result: dict[str, Member] = {}
    for member_id, member_data in members.items():
        user_data = users.get(member_id)
        if user_data is not None and "user" not in member_data:
            member_data = {**member_data, "user": user_data}
        result[member_id] = Member(_with_guild_id(member_data, guild_id))
    return result


class Context:
    """Every handler receives one of these as `ctx`. Fields not applicable
    to the current interaction are `None` (or empty). Constructed by
    cordless itself, not something you instantiate directly.

    | Attribute | |
    |---|---|
    | `ctx.user` | The invoking `User` (resolved from the member in guilds, direct in DMs) |
    | `ctx.member` | Guild `Member` (roles, nick, permissions); `None` in DMs |
    | `ctx.guild_id` / `ctx.channel_id` | Where the interaction happened |
    | `ctx.channel` | Partial `Channel` |
    | `ctx.guild` | Partial `Guild` (`None` in DMs); only `.id`, `.locale`, `.features` are populated |
    | `ctx.message` | The `Message` the component sits on (component interactions) |
    | `ctx.locale` | The invoking user's locale, e.g. `"en-US"` |
    | `ctx.options` | Dict of option name to value for the invoked (sub)command |
    | `ctx.attachments` | Dict of attachment id to `Attachment` for `attachment` options |
    | `ctx.resolved_users` / `ctx.resolved_members` | Dict of id to resolved `User`/`Member`, for `UserSelect`/`MentionableSelect` picks |
    | `ctx.resolved_roles` | Dict of id to resolved `Role`, for `RoleSelect`/`MentionableSelect` picks |
    | `ctx.resolved_channels` | Dict of id to resolved `Channel`, for `ChannelSelect` picks |
    | `ctx.custom_id` | The component/modal's full custom_id |
    | `ctx.custom_id_args` | Suffix segments when a handler matched by prefix (`"shop:item1"` becomes `["item1"]`) |
    | `ctx.values` | Selected values/ids for select menus (always a list) |
    | `ctx.modal_values` | Dict of field custom_id to submitted value (modal submissions) |
    | `ctx.focused_value` | What the user has typed so far (autocomplete) |
    | `ctx.target_user` / `ctx.target_member` | Target `User` / `Member` of a user context menu command |
    | `ctx.target_message` | Target `Message` of a message context menu command |
    | `ctx.interaction_id` / `ctx.token` | The interaction's id and token |
    | `ctx.entitlements` | List of entitlement dicts the invoking user/guild holds, for gating premium features |
    | `ctx.interaction` | The full raw interaction payload, for anything not surfaced above |

    `User`, `Member`, `Message`, `Channel`, and `Attachment` are thin
    wrappers around Discord's raw object, not dicts. Every field Discord
    sends is available as an attribute, e.g. `ctx.user.username`. Fields not
    on the underlying payload raise `AttributeError` rather than silently
    returning `None`.
    """

    def __init__(self, interaction: Any, *, _worker_mode: bool = False) -> None:
        self.interaction = interaction
        self.response: dict[str, Any] | None = None
        self._response_kind = None
        self._worker_mode = _worker_mode

        data = interaction.get("data", {})
        self.custom_id = data.get("custom_id")
        # Suffix segments when a handler matched by prefix, e.g. "shop:item1" → ["item1"]
        self.custom_id_args = []
        self.options = {opt["name"]: opt["value"] for opt in _leaf_options(data) if "value" in opt}
        guild_id = interaction.get("guild_id")
        self.user = _wrap(
            User, cast("dict[str, Any]", interaction.get("member") or {}).get("user") or interaction.get("user")
        )
        self.member = _wrap(Member, _with_guild_id(interaction.get("member"), guild_id))
        self.message = _wrap(Message, interaction.get("message"))
        self.channel = _wrap(Channel, interaction.get("channel"))
        self.guild = _wrap(Guild, interaction.get("guild"))
        self.locale = interaction.get("locale")
        self.guild_id = guild_id
        self.channel_id = interaction.get("channel_id")
        self.interaction_id = interaction.get("id")
        self.token = interaction.get("token")
        self.entitlements = interaction.get("entitlements", [])

        # Select menu resolved values
        self.values = data.get("values", [])

        # Autocomplete: the value of the focused option
        self.focused_value = None
        for opt in _leaf_options(data):
            if opt.get("focused"):
                self.focused_value = opt.get("value")

        # Modal submission: flat dict of component custom_id → value
        self.modal_values: dict[str, Any] = {}
        for row in data.get("components", []):
            for comp in row.get("components", []):
                if "custom_id" in comp:
                    self.modal_values[comp["custom_id"]] = comp.get("value", "")

        # Context menu commands (type 2/3) and entity-select components (UserSelect,
        # RoleSelect, ChannelSelect, MentionableSelect) both hand back a "resolved"
        # block: full objects for whatever ids are involved, alongside the bare ids
        # (data.target_id, or ctx.values for selects).
        resolved = data.get("resolved", {})
        resolved_users = resolved.get("users", {})
        resolved_members = _wrap_members(resolved.get("members", {}), resolved_users, guild_id)

        # Attachment options (type 11): ctx.options holds the id,
        # ctx.attachments[id] holds the filename/url/size metadata
        self.attachments = {att_id: Attachment(att) for att_id, att in resolved.get("attachments", {}).items()}
        target_id = data.get("target_id")
        self.target_user = _wrap(User, resolved_users.get(target_id)) if target_id else None
        self.target_member = resolved_members.get(target_id) if target_id else None
        self.target_message = _wrap(Message, resolved.get("messages", {}).get(target_id)) if target_id else None

        self.resolved_users = {uid: User(u) for uid, u in resolved_users.items()}
        self.resolved_members = resolved_members
        self.resolved_roles = {rid: Role(_with_guild_id(r, guild_id)) for rid, r in resolved.get("roles", {}).items()}
        self.resolved_channels = {cid: Channel(c) for cid, c in resolved.get("channels", {}).items()}

    async def send(
        self,
        msg: Any = None,
        *,
        content: Any = None,
        ephemeral: bool = False,
        embeds: Any = None,
        components: Any = None,
        files: Any = None,
        allowed_mentions: Any = None,
    ) -> dict[str, Any]:
        """Send the response. `msg` and `content` are interchangeable
        (positional vs keyword). `files` is a list of `(filename, bytes)`
        tuples. In a deferred handler, `send` edits the loading message
        instead of creating a new one."""
        if self._worker_mode:
            return await self.followup(
                msg,
                content=content,
                ephemeral=ephemeral,
                embeds=embeds,
                components=components,
                files=files,
                allowed_mentions=allowed_mentions,
            )

        data = _build_message_data(msg, content, embeds, components, ephemeral, allowed_mentions)
        payload = {"type": _CHANNEL_MESSAGE_WITH_SOURCE, "data": data}
        if files:
            _attach_files(data, files)
            self.response = _multipart_response(payload, files)
        else:
            self.response = _response(payload)
        return self.response

    async def followup(
        self,
        msg: Any = None,
        *,
        content: Any = None,
        ephemeral: bool = False,
        embeds: Any = None,
        components: Any = None,
        files: Any = None,
        allowed_mentions: Any = None,
    ) -> dict[str, Any]:
        """Manual replica of what decorator `defer=True` sends automatically:
        same shape as `send`. You normally don't call this yourself, it's
        what `send`/`edit` fall through to in worker mode."""
        from .defer import patch_followup, patch_followup_with_files

        data = _build_message_data(msg, content, embeds, components, ephemeral, allowed_mentions)
        app_id = self.interaction.get("application_id")

        if files:
            _attach_files(data, files)
            patch_followup_with_files(app_id, self.token, data, files)
        else:
            patch_followup(app_id, self.token, data)

        self.response = {"_cordless_followup": True}
        return self.response

    async def send_followup(
        self,
        msg: Any = None,
        *,
        content: Any = None,
        ephemeral: bool = False,
        embeds: Any = None,
        components: Any = None,
        allowed_mentions: Any = None,
    ) -> dict[str, Any]:
        """Deferred handlers only: post an additional, separate message
        (doesn't touch the original loading message)."""
        from .defer import post_followup

        data = _build_message_data(msg, content, embeds, components, ephemeral, allowed_mentions)
        post_followup(self.interaction.get("application_id"), self.token, data)
        return {"_cordless_followup": True}

    async def delete_original(self) -> None:
        """Deferred handlers only: delete the original loading message."""
        from .defer import delete_original as _delete

        _delete(self.interaction.get("application_id"), self.token)

    async def edit(
        self,
        msg: Any = None,
        *,
        content: Any = None,
        embeds: Any = None,
        components: Any = None,
        files: Any = None,
        allowed_mentions: Any = None,
    ) -> dict[str, Any]:
        """Update the message the component sits on (buttons/selects). No
        `ephemeral`: a message's visibility can't change after creation."""
        if self._worker_mode:
            return await self.followup(
                msg,
                content=content,
                embeds=embeds,
                components=components,
                files=files,
                allowed_mentions=allowed_mentions,
            )
        data = _build_message_data(msg, content, embeds, components, allowed_mentions=allowed_mentions)
        payload = {"type": _UPDATE_MESSAGE, "data": data}
        if files:
            _attach_files(data, files)
            self.response = _multipart_response(payload, files)
        else:
            self.response = _response(payload)
        return self.response

    async def defer(self, ephemeral: bool = False) -> dict[str, Any]:
        """Loading state, for commands/modals. You don't normally call this
        yourself; decorator `defer=True` handles the ack and runs your
        handler on the worker."""
        data: dict[str, Any] = {"type": _DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE}
        if ephemeral:
            data["data"] = {"flags": _FLAG_EPHEMERAL}
        self.response = _response(data)
        return self.response

    async def defer_edit(self) -> dict[str, Any]:
        """Defer a component interaction: tells Discord we'll update this message async (type 6)."""
        self.response = _response({"type": _DEFERRED_UPDATE_MESSAGE})
        return self.response

    async def send_modal(self, modal: Any) -> dict[str, Any]:
        """Show a `Modal`. Must be the first response; you can't defer, then
        open a modal."""
        self.response = _response({"type": _MODAL, "data": modal.to_dict()})
        return self.response

    async def respond_autocomplete(self, choices: Any) -> dict[str, Any]:
        """The manual piece underneath an `@bot.autocomplete` handler's
        returned list. You don't normally call this yourself."""
        self.response = _response({"type": _AUTOCOMPLETE_RESULT, "data": {"choices": choices}})
        self._response_kind = "autocomplete"
        return self.response


def _response(payload: Any) -> dict[str, Any]:
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload),
    }


def _multipart_response(payload: Any, files: Any) -> dict[str, Any]:
    """Like _response(), but for an interaction response that carries file
    attachments. Discord accepts multipart/form-data for the initial response,
    same as followup messages; API Gateway needs the body base64-encoded plus
    isBase64Encoded=True to pass binary data through untouched.
    """
    body, content_type = build_multipart_body(payload, files)
    return {
        "statusCode": 200,
        "headers": {"Content-Type": content_type},
        "body": base64.b64encode(body).decode(),
        "isBase64Encoded": True,
    }
