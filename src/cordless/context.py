import json

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


class Context:
    def __init__(self, interaction, *, _worker_mode=False):
        self.interaction = interaction
        self.response = None
        self._worker_mode = _worker_mode

        data = interaction.get("data", {})
        self.custom_id = data.get("custom_id")
        # Suffix segments when a handler matched by prefix, e.g. "shop:item1" → ["item1"]
        self.custom_id_args = []
        self.options = {opt["name"]: opt["value"] for opt in _leaf_options(data) if "value" in opt}
        self.user = (interaction.get("member") or {}).get("user") or interaction.get("user")
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
        self.attachments = resolved.get("attachments", {})
        target_id = data.get("target_id")
        self.target_user = resolved.get("users", {}).get(target_id) if target_id else None
        self.target_member = resolved.get("members", {}).get(target_id) if target_id else None
        self.target_message = resolved.get("messages", {}).get(target_id) if target_id else None

    async def send(self, msg=None, *, content=None, ephemeral=False, embeds=None, components=None, files=None):
        if self._worker_mode:
            return await self.followup(msg, content=content, ephemeral=ephemeral, embeds=embeds, components=components, files=files)

        _content = content if content is not None else msg
        data = {}
        if _content is not None:
            data["content"] = _content
        if embeds is not None:
            data["embeds"] = [e.to_dict() if hasattr(e, "to_dict") else e for e in embeds]
        if components is not None:
            data["components"] = [c.to_dict() if hasattr(c, "to_dict") else c for c in components]

        flags = 0
        if ephemeral:
            flags |= _FLAG_EPHEMERAL
        if _contains_uikit(components):
            flags |= _FLAG_UI_KIT
        if flags:
            data["flags"] = flags

        self.response = _response({"type": _CHANNEL_MESSAGE_WITH_SOURCE, "data": data})
        return self.response

    async def followup(self, msg=None, *, content=None, ephemeral=False, embeds=None, components=None, files=None):
        from .defer import patch_followup, patch_followup_with_files

        _content = content if content is not None else msg
        data = {}
        if _content is not None:
            data["content"] = _content
        if embeds is not None:
            data["embeds"] = [e.to_dict() if hasattr(e, "to_dict") else e for e in embeds]
        if components is not None:
            data["components"] = [c.to_dict() if hasattr(c, "to_dict") else c for c in components]

        flags = 0
        if ephemeral:
            flags |= _FLAG_EPHEMERAL
        if _contains_uikit(components):
            flags |= _FLAG_UI_KIT
        if flags:
            data["flags"] = flags

        app_id = self.interaction.get("application_id")

        if files:
            data["attachments"] = [{"id": i, "filename": name} for i, (name, _) in enumerate(files)]
            patch_followup_with_files(app_id, self.token, data, files)
        else:
            patch_followup(app_id, self.token, data)

        self.response = {"_cordless_followup": True}
        return self.response

    async def edit(self, msg=None, *, content=None, embeds=None, components=None, files=None):
        if self._worker_mode:
            return await self.followup(msg, content=content, embeds=embeds, components=components, files=files)
        _content = content if content is not None else msg
        data = {}
        if _content is not None:
            data["content"] = _content
        if embeds is not None:
            data["embeds"] = [e.to_dict() if hasattr(e, "to_dict") else e for e in embeds]
        if components is not None:
            data["components"] = [c.to_dict() if hasattr(c, "to_dict") else c for c in components]
        if _contains_uikit(components):
            data["flags"] = _FLAG_UI_KIT
        self.response = _response({"type": _UPDATE_MESSAGE, "data": data})
        return self.response

    async def defer(self, ephemeral=False):
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
        self.response = _response({"type": _MODAL, "data": modal.to_dict()})
        return self.response

    async def respond_autocomplete(self, choices):
        self.response = _response({"type": _AUTOCOMPLETE_RESULT, "data": {"choices": choices}})
        return self.response


def _response(payload):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload),
    }
