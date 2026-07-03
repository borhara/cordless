import json

_CHANNEL_MESSAGE_WITH_SOURCE = 4
_UPDATE_MESSAGE = 7
_DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE = 5
_AUTOCOMPLETE_RESULT = 8
_MODAL = 9

_FLAG_EPHEMERAL = 64
_FLAG_UI_KIT = 32768


def _contains_uikit(components):
    if not components:
        return False
    for c in components:
        if getattr(c, "is_ui_kit", False):
            return True
        # recurse into ActionRow children
        if hasattr(c, "components") and not getattr(c, "is_ui_kit", False):
            if _contains_uikit(c.components):
                return True
    return False


class Context:
    def __init__(self, interaction):
        self.interaction = interaction
        self.response = None

        data = interaction.get("data", {})
        self.custom_id = data.get("custom_id")
        self.options = {opt["name"]: opt["value"] for opt in data.get("options", []) if "value" in opt}
        self.user = (interaction.get("member") or {}).get("user") or interaction.get("user")
        self.guild_id = interaction.get("guild_id")
        self.channel_id = interaction.get("channel_id")
        self.interaction_id = interaction.get("id")
        self.token = interaction.get("token")

        # Select menu resolved values
        self.values = data.get("values", [])

        # Autocomplete: the value of the focused option
        self.focused_value = None
        for opt in data.get("options", []):
            if opt.get("focused"):
                self.focused_value = opt.get("value")

        # Modal submission: flat dict of component custom_id → value
        self.modal_values = {}
        for row in data.get("components", []):
            for comp in row.get("components", []):
                if "custom_id" in comp:
                    self.modal_values[comp["custom_id"]] = comp.get("value", "")

    async def send(self, msg=None, *, content=None, ephemeral=False, embeds=None, components=None):
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

    async def edit(self, msg=None, *, content=None, embeds=None, components=None):
        _content = content if content is not None else msg
        data = {}
        if _content is not None:
            data["content"] = _content
        if embeds is not None:
            data["embeds"] = [e.to_dict() if hasattr(e, "to_dict") else e for e in embeds]
        if components is not None:
            data["components"] = [c.to_dict() if hasattr(c, "to_dict") else c for c in components]
        self.response = _response({"type": _UPDATE_MESSAGE, "data": data})
        return self.response

    async def defer(self):
        self.response = _response({"type": _DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE})
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
