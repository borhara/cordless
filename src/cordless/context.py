import base64
import json

from ._multipart import build_multipart_body
from .models import Attachment, Channel, Member, Message, User, _wrap

_CHANNEL_MESSAGE_WITH_SOURCE = 4
_UPDATE_MESSAGE = 7
_DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE = 5
_DEFERRED_UPDATE_MESSAGE = 6
_AUTOCOMPLETE_RESULT = 8
_MODAL = 9

_FLAG_EPHEMERAL = 64
_FLAG_UI_KIT = 32768


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


def _leaf_options(data):
    """Descend through subcommand/group wrappers to the actual value options."""
    options = data.get("options", [])
    while options and options[0].get("type") in (1, 2):
        options = options[0].get("options", [])
    return options


def _build_message_data(msg, content, embeds, components, ephemeral=False, allowed_mentions=None):
    _content = content if content is not None else msg
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
    if _contains_uikit(components):
        flags |= _FLAG_UI_KIT
    if flags:
        data["flags"] = flags
    return data


def _attach_files(data, files):
    """Add the attachments metadata array Discord expects alongside a multipart body."""
    data["attachments"] = [{"id": i, "filename": name} for i, (name, _) in enumerate(files)]


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
    | `ctx.message` | The `Message` the component sits on (component interactions) |
    | `ctx.locale` | The invoking user's locale, e.g. `"en-US"` |
    | `ctx.options` | Dict of option name to value for the invoked (sub)command |
    | `ctx.attachments` | Dict of attachment id to `Attachment` for `attachment` options |
    | `ctx.custom_id` | The component/modal's full custom_id |
    | `ctx.custom_id_args` | Suffix segments when a handler matched by prefix (`"shop:item1"` becomes `["item1"]`) |
    | `ctx.values` | Selected values/ids for select menus (always a list) |
    | `ctx.modal_values` | Dict of field custom_id to submitted value (modal submissions) |
    | `ctx.focused_value` | What the user has typed so far (autocomplete) |
    | `ctx.target_user` / `ctx.target_member` | Target `User` / `Member` of a user context menu command |
    | `ctx.target_message` | Target `Message` of a message context menu command |
    | `ctx.interaction_id` / `ctx.token` | The interaction's id and token |
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
        self._worker_mode = _worker_mode

        data = interaction.get("data", {})
        self.custom_id = data.get("custom_id")
        # Suffix segments when a handler matched by prefix, e.g. "shop:item1" → ["item1"]
        self.custom_id_args = []
        self.options = {opt["name"]: opt["value"] for opt in _leaf_options(data) if "value" in opt}
        self.user = _wrap(User, (interaction.get("member") or {}).get("user") or interaction.get("user"))
        self.member = _wrap(Member, interaction.get("member"))
        self.message = _wrap(Message, interaction.get("message"))
        self.channel = _wrap(Channel, interaction.get("channel"))
        self.locale = interaction.get("locale")
        self.guild_id = interaction.get("guild_id")
        self.channel_id = interaction.get("channel_id")
        self.interaction_id = interaction.get("id")
        self.token = interaction.get("token")

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

        # Context menu commands (type 2/3): resolved target
        resolved = data.get("resolved", {})
        # Attachment options (type 11): ctx.options holds the id,
        # ctx.attachments[id] holds the filename/url/size metadata
        self.attachments = {att_id: Attachment(att) for att_id, att in resolved.get("attachments", {}).items()}
        target_id = data.get("target_id")
        self.target_user = _wrap(User, resolved.get("users", {}).get(target_id)) if target_id else None
        self.target_member = _wrap(Member, resolved.get("members", {}).get(target_id)) if target_id else None
        self.target_message = _wrap(Message, resolved.get("messages", {}).get(target_id)) if target_id else None

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
        data = {"type": _DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE}
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
