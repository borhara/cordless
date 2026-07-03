class Context:
    def __init__(self, interaction, responder):
        self.interaction = interaction
        self.responder = responder
        self.response = None

        data = interaction.get("data", {})
        self.options = {opt["name"]: opt["value"] for opt in data.get("options", []) if "value" in opt}
        self.user = (interaction.get("member") or {}).get("user") or interaction.get("user")
        self.guild_id = interaction.get("guild_id")
        self.channel_id = interaction.get("channel_id")

    async def send(self, msg):
        self.response = self.responder.send(msg)
        return self.response

    async def edit(self, msg):
        self.response = self.responder.edit(msg)
        return self.response

    async def defer(self):
        self.response = self.responder.defer()
        return self.response
