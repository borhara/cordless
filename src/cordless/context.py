import base64
import json

from ._multipart import build_multipart_body
from .errors import MessageTooLongError
from .models import Attachment, Channel, Guild, Member, Message, Role, User, _wrap

_CHANNEL_MESSAGE_WITH_SOURCE = 4
_UPDATE_MESSAGE = 7
_DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE = 5
_DEFERRED_UPDATE_MESSAGE = 6
_AUTOCOMPLETE_RESULT = 8
_MODAL = 9

_FLAG_EPHEMERAL = 64
_FLAG_UI_KIT = 32768

_MAX_CONTENT_LENGTH = 2000
_MAX_UIKIT_COMPONENTS = 40
_MAX_UIKIT_TEXT_LENGTH = 4000


# Components v2 types: Section, TextDisplay, Thumbnail, MediaGallery, File, Separator, Container
_UI_KIT_TYPES = {9, 10, 11, 12, 13, 14, 17}


def _contains_uikit(components):
    if not components:
        return False
    for c in components:
        if getattr(c, "is_ui_kit", False):
            return True
        if isinstance(c, dict):
            if c.get("type") in _UI_KIT_TYPES:
                return True
            if _contains_uikit(c.get("components")):
                return True
        # recurse into ActionRow children
        elif hasattr(c, "components"):
            if _contains_uikit(c.components):
                return True
    return False


def _count_components(components):
    """Discord counts every component in the tree toward the 40-component
    cap, including ones nested inside a Container/Section/ActionRow and a
    Section's accessory."""
    if not components:
        return 0
    total = 0
    for c in components:
        total += 1
        if isinstance(c, dict):
            total += _count_components(c.get("components"))
            if c.get("accessory") is not None:
                total += 1
        else:
            if hasattr(c, "components"):
                total += _count_components(c.components)
            if getattr(c, "accessory", None) is not None:
                total += 1
    return total


def _uikit_text_length(components):
    """Sum of every TextDisplay's content, which Discord caps at 4000
    characters total across the whole message."""
    if not components:
        return 0
    total = 0
    for c in components:
        if isinstance(c, dict):
            if c.get("type") == 10:
                total += len(c.get("content") or "")
            total += _uikit_text_length(c.get("components"))
        else:
            if hasattr(c, "content") and not hasattr(c, "components"):
                total += len(c.content or "")
            if hasattr(c, "components"):
                total += _uikit_text_length(c.components)
    return total


def _leaf_options(data):
    """Descend through subcommand/group wrappers to the actual value options."""
    options = data.get("options", [])
    while options and options[0].get("type") in (1, 2):
        options = options[0].get("options", [])
    return options


def _validate_content_length(content):
    """Discord rejects the interaction response/followup outright when
    content is too long, but that rejection happens on Discord's end after
    we've already returned 200 to API Gateway, so we check upfront instead
    of failing invisibly."""
    if content is not None and len(content) > _MAX_CONTENT_LENGTH:
        raise MessageTooLongError(
            f"Message content is {len(content)} characters, which exceeds Discord's {_MAX_CONTENT_LENGTH}-character limit"
        )


def _validate_uikit(content, embeds, components):
    """Discord rejects a Components v2 message that also sets content or
    embeds, or that exceeds its component-count/text-length caps, but that
    rejection happens on Discord's end after we've already sent the request
    (an HTTP round trip for the REST layer, or after we've already returned
    200 to API Gateway for an interaction response), so check upfront
    instead of failing invisibly or late. Shared between the interaction
    path (_build_message_data below) and the REST layer's create_message/
    edit_channel_message, so both reject the same way instead of only one
    of them catching it locally and the other relying on Discord's own
    validation. content/embeds must already be normalized to None by the
    caller for "not being set in this call" (e.g. _rest/messages.py's
    UNSET sentinel), since None here specifically means "no conflict"."""
    if content is not None or embeds is not None:
        raise ValueError("Components v2 messages can't also set content or embeds, use TextDisplay/Container instead")
    count = _count_components(components)
    if count > _MAX_UIKIT_COMPONENTS:
        raise ValueError(
            f"Message has {count} components, which exceeds Discord's {_MAX_UIKIT_COMPONENTS}-component limit"
        )
    text_length = _uikit_text_length(components)
    if text_length > _MAX_UIKIT_TEXT_LENGTH:
        raise MessageTooLongError(
            f"Components v2 text totals {text_length} characters, which exceeds "
            f"Discord's {_MAX_UIKIT_TEXT_LENGTH}-character limit"
        )


def _build_message_data(msg, content, embeds, components, ephemeral=False, allowed_mentions=None):
    _content = content if content is not None else msg
    is_uikit = _contains_uikit(components)
    if is_uikit:
        _validate_uikit(_content, embeds, components)
    else:
        _validate_content_length(_content)

    data = {}
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


def _attach_files(data, files):
    """Add the attachments metadata array Discord expects alongside a multipart body.

    Appended after whatever's already in data["attachments"] (e.g. an edit's
    retained-attachment list), rather than replacing it: the new entries'
    "id" is the file's index, matching the "files[n]" part build_multipart_body
    gives it, while retained attachments keep their own real snowflake id."""
    existing = data.get("attachments") or []
    data["attachments"] = existing + [{"id": i, "filename": name} for i, (name, _) in enumerate(files)]


def _with_guild_id(data, guild_id):
    """Discord's member and role payloads never carry their own guild_id -
    it's implied by the endpoint you fetched them from. Stitch it in so
    member.add_role()/role.edit() and friends know which guild to act on."""
    if data is None or guild_id is None:
        return data
    return {**data, "guild_id": guild_id}


def _wrap_members(members, users, guild_id):
    """Discord's resolved.members entries omit the nested `user` object
    that's normally embedded on a member payload - it lives separately in
    resolved.users instead. Stitch it back in so `.user` works on a
    resolved `Member` the same way it does everywhere else."""
    result = {}
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

    def __init__(self, interaction, *, _worker_mode=False):
        self.interaction = interaction
        self.response = None
        self._response_kind = None
        self._worker_mode = _worker_mode

        data = interaction.get("data", {})
        self.custom_id = data.get("custom_id")
        # Suffix segments when a handler matched by prefix, e.g. "shop:item1" → ["item1"]
        self.custom_id_args = []
        self.options = {opt["name"]: opt["value"] for opt in _leaf_options(data) if "value" in opt}
        guild_id = interaction.get("guild_id")
        self.user = _wrap(User, (interaction.get("member") or {}).get("user") or interaction.get("user"))
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
        self.modal_values = {}
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
        msg=None,
        *,
        content=None,
        ephemeral=False,
        embeds=None,
        components=None,
        files=None,
        allowed_mentions=None,
    ):
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
        msg=None,
        *,
        content=None,
        ephemeral=False,
        embeds=None,
        components=None,
        files=None,
        allowed_mentions=None,
    ):
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
        self, msg=None, *, content=None, ephemeral=False, embeds=None, components=None, allowed_mentions=None
    ):
        """Deferred handlers only: post an additional, separate message
        (doesn't touch the original loading message)."""
        from .defer import post_followup

        data = _build_message_data(msg, content, embeds, components, ephemeral, allowed_mentions)
        post_followup(self.interaction.get("application_id"), self.token, data)
        return {"_cordless_followup": True}

    async def delete_original(self):
        """Deferred handlers only: delete the original loading message."""
        from .defer import delete_original as _delete

        _delete(self.interaction.get("application_id"), self.token)

    async def edit(self, msg=None, *, content=None, embeds=None, components=None, files=None, allowed_mentions=None):
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

    async def defer(self, ephemeral=False):
        """Loading state, for commands/modals. You don't normally call this
        yourself; decorator `defer=True` handles the ack and runs your
        handler on the worker."""
        data: dict = {"type": _DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE}
        if ephemeral:
            data["data"] = {"flags": _FLAG_EPHEMERAL}
        self.response = _response(data)
        return self.response

    async def defer_edit(self):
        """Defer a component interaction: tells Discord we'll update this message async (type 6)."""
        self.response = _response({"type": _DEFERRED_UPDATE_MESSAGE})
        return self.response

    async def send_modal(self, modal):
        """Show a `Modal`. Must be the first response; you can't defer, then
        open a modal."""
        self.response = _response({"type": _MODAL, "data": modal.to_dict()})
        return self.response

    async def respond_autocomplete(self, choices):
        """The manual piece underneath an `@bot.autocomplete` handler's
        returned list. You don't normally call this yourself."""
        self.response = _response({"type": _AUTOCOMPLETE_RESULT, "data": {"choices": choices}})
        self._response_kind = "autocomplete"
        return self.response


def _response(payload):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload),
    }


def _multipart_response(payload, files):
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
