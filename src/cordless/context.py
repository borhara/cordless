class Context:
    def __init__(self, interaction, responder):
        self.interaction = interaction
        self.responder = responder

    @property
    def user(self):
        return self.interaction.get("member", {}).get("user")

    @property
    def guild_id(self):
        return self.interaction.get("guild_id")

    @property
    def channel_id(self):
        return self.interaction.get("channel_id")

    async def send(self, msg):
        return self.responder.send(msg)

    async def edit(self, msg):
        return self.responder.edit(msg)

    async def defer(self):
        return self.responder.defer()
