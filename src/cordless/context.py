import json

_CHANNEL_MESSAGE_WITH_SOURCE = 4
_UPDATE_MESSAGE = 7
_DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE = 5


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

    async def send(self, msg, *, ephemeral=False):
        data = {"content": msg}
        if ephemeral:
            data["flags"] = 64
        self.response = _response({"type": _CHANNEL_MESSAGE_WITH_SOURCE, "data": data})
        return self.response

    async def edit(self, msg):
        self.response = _response({"type": _UPDATE_MESSAGE, "data": {"content": msg}})
        return self.response

    async def defer(self):
        self.response = _response({"type": _DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE})
        return self.response


def _response(payload):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload),
    }
